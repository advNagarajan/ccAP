import json
import logging
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.core.settings import settings
from app.services.agents.schemas import InferenceAgentOutput
from app.services.agents.tools import (
    search_candidate_targets,
    get_target_schema_details,
    check_type_compatibility,
    get_feedback_guidelines,
)

from functools import cached_property
from google.adk.models.google_llm import Gemini
from google.genai import Client

logger = logging.getLogger("landing_inference.agent")


import asyncio

class VertexGemini(Gemini):
    @property
    def api_client(self) -> Client:
        if not hasattr(self, "_clients_by_loop"):
            self._clients_by_loop = {}
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            if loop not in self._clients_by_loop:
                self._clients_by_loop[loop] = self._create_api_client()
            return self._clients_by_loop[loop]
        return self._create_api_client()

    def _create_api_client(self) -> Client:
        from google.genai import Client
        base_url, api_version = self._base_url_and_api_version
        kwargs_for_http_options = {
            'headers': self._tracking_headers(),
            'retry_options': self.retry_options,
            'base_url': base_url,
            'timeout': 60,
        }
        if api_version:
            kwargs_for_http_options['api_version'] = api_version

        kwargs = {
            'http_options': types.HttpOptions(**kwargs_for_http_options),
            'vertexai': True,
            'project': settings.GCP_PROJECT_ID,
            'location': settings.GCP_LOCATION,
        }
        return Client(**kwargs)

    @property
    def _live_api_client(self) -> Client:
        if not hasattr(self, "_live_clients_by_loop"):
            self._live_clients_by_loop = {}
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            if loop not in self._live_clients_by_loop:
                self._live_clients_by_loop[loop] = self._create_live_api_client()
            return self._live_clients_by_loop[loop]
        return self._create_live_api_client()

    def _create_live_api_client(self) -> Client:
        from google.genai import Client
        base_url, _ = self._base_url_and_api_version
        kwargs = {
            'http_options': types.HttpOptions(
                headers=self._tracking_headers(),
                api_version=self._live_api_version,
                base_url=base_url,
                timeout=60,
            ),
            'vertexai': True,
            'project': settings.GCP_PROJECT_ID,
            'location': settings.GCP_LOCATION,
        }
        return Client(**kwargs)


# Define the Inference Agent
# NOTE: output_schema is intentionally NOT set here.
# ADK enforces a hard constraint: when output_schema is set, the LLM cannot
# also call tools — it enters an infinite tool-call loop. Instead we validate
# the free-text JSON response with Pydantic after the run loop finishes.
inference_agent = LlmAgent(
    name="InferenceAgent",
    model=VertexGemini(model=settings.VERTEX_GENERATIVE_MODEL or "gemini-2.5-flash"),
    description="Selects the optimal target landing zone and maps source schema fields.",
    instruction="""You are an expert data engineer on a schema intelligence platform.

Your task: Given a source dataset's metadata, find the best target landing zone
from the catalog and produce a complete column-level mapping with partitioning
recommendations.

WORKFLOW:
1. Call 'search_candidate_targets' with a summary of the source dataset.
   This returns candidate targets with IDs, names, types, domains, and similarity scores.
2. Review the candidates. If one stands out, call 'get_target_schema_details'
   to inspect its full field definitions.
3. If multiple candidates look similar, inspect 2-3 of them before deciding.
4. If no candidate is a reasonable match, set selected_target_id to null.
5. Once you select a target, map every source column to a target column (or null).
   For any mapping where source and target types look different, call
   'check_type_compatibility' to verify.
6. Recommend partitioning ONLY if a date, timestamp, or high-cardinality unique
   ID column exists in the source. Include the column name and strategy, aligning
   with the target database platform (target_type, e.g., POSTGRESQL, BIGQUERY, SNOWFLAKE, GCS, S3, DELTA).
7. Suggest naming convention adjustments if source names don't follow the
   target's conventions (e.g., camelCase source -> snake_case target), taking the target's
   database platform casing rules into account.
8. Optionally call 'get_feedback_guidelines' to check if engineers left notes
   about past inference decisions for this job.

CONSTRAINTS:
- You MUST use tools to gather data. Do NOT guess schemas from memory.
- selected_target_id must be a valid UUID from the candidates, or null.
- Explain your reasoning concisely (under 5 sentences).
- When you have finished your analysis, respond with ONLY a valid JSON object
  matching this exact schema — no markdown fences, no extra keys:
  {
    "selected_target_id": "<uuid or null>",
    "confidence_score": <0.0-1.0>,
    "reasoning": "<string>",
    "column_mapping": {"<source_col>": "<target_col or null>"},
    "unmapped_source_columns": ["<col>", ...],
    "missing_target_columns": ["<col>", ...],
    "partitioning_recommendation": "<string or null>",
    "naming_convention_suggestions": {"<old>": "<new>"} or null
  }
""",
    tools=[
        search_candidate_targets,
        get_target_schema_details,
        check_type_compatibility,
        get_feedback_guidelines,
    ],
    max_turns=10,
)


class SessionProxy:
    """
    Lightweight proxy wrapper for SQLAlchemy Session.
    Bypasses deepcopy/pickling issues in Google's ADK Session Service.
    """
    def __init__(self, session):
        object.__setattr__(self, "_session", session)

    def __getattr__(self, name):
        return getattr(self._session, name)

    def __setattr__(self, name, value):
        setattr(self._session, name, value)

    def __deepcopy__(self, memo):
        return self


async def run_inference_agent(
    job_id: str,
    source_json: dict,
    source_embedding: list[float] | None,
    predefined_target_ids: list[str],
    db,  # SQLAlchemy Session
    connector_metadata: dict | None = None,
) -> dict:
    """
    Initializes and executes the Inference Agent via ADK Runner.
    Returns a dict matching the legacy generate_target_inference() output shape.
    """
    logger.info(f"Running ADK Inference Agent for job_id: {job_id}")

    # 1. Create session service and pre-load state
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="schema_intelligence",
        user_id="system",
        state={
            "db": SessionProxy(db),
            "source_embedding": source_embedding,
            "predefined_target_ids": predefined_target_ids,
            "job_id": job_id,
        }
    )

    # 2. Create the Runner
    runner = Runner(
        app_name="schema_intelligence",
        agent=inference_agent,
        session_service=session_service,
    )

    # 3. Build the input message with the source schema and metadata
    input_text = "Analyze this source dataset and find the best target landing zone.\n\n"
    if connector_metadata:
        obj_name = connector_metadata.get("object_name", "Unknown")
        fmt_type = connector_metadata.get("format_type", "Unknown")
        input_text += f"Source Dataset Identity: {obj_name} (Format: {fmt_type})\n\n"
    
    input_text += f"Source Schema:\n{json.dumps(source_json, indent=2)}"

    content = types.Content(
        role="user",
        parts=[types.Part(text=input_text)]
    )

    # 4. Run the agent with a hard wall-clock timeout.
    # asyncio.wait_for cancels the coroutine if the agent stalls, preventing
    # indefinite hangs when Vertex AI does not return a final response.
    agent_timeout = settings.INFERENCE_AGENT_TIMEOUT_SECONDS
    final_response = None

    async def _run_agent() -> None:
        nonlocal final_response
        async for event in runner.run_async(
            session_id=session.id,
            user_id="system",
            new_message=content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response = "".join(
                        part.text for part in event.content.parts
                        if part.text and not part.thought
                    )
                    logger.info("ADK Inference Agent completed with final response.")

    try:
        await asyncio.wait_for(_run_agent(), timeout=agent_timeout)
    except asyncio.TimeoutError:
        logger.error(
            f"ADK Inference Agent timed out after {agent_timeout}s for job_id={job_id}. "
            "Returning fallback response."
        )
        return {
            "selected_target_id": None,
            "confidence_score": 0.0,
            "reasoning": f"Agent timed out after {agent_timeout} seconds.",
            "column_mapping": None,
            "unmapped_source_columns": [],
            "missing_target_columns": [],
            "partitioning_recommendation": None,
            "naming_convention_suggestions": None,
        }

    # 5. Validate and parse structured output via Pydantic, then return as dict.
    # We validate with the schema here rather than in the LlmAgent constructor
    # because ADK does not support output_schema when tools are also present.
    if final_response:
        try:
            parsed = InferenceAgentOutput.model_validate_json(final_response)
            return parsed.model_dump()
        except Exception:
            # Fall back to raw JSON parse if Pydantic validation fails
            try:
                return json.loads(final_response)
            except Exception as e:
                logger.error(
                    f"Failed to parse Inference Agent JSON output: {e}. "
                    f"Output was: {final_response}"
                )
                raise
    else:
        logger.warning("ADK Inference Agent did not emit a final response.")
        return {
            "selected_target_id": None,
            "confidence_score": 0.0,
            "reasoning": "Agent did not produce a final response.",
            "column_mapping": None,
            "unmapped_source_columns": [],
            "missing_target_columns": [],
            "partitioning_recommendation": None,
            "naming_convention_suggestions": None,
        }
