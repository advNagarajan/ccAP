import json
import asyncio
import logging

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.google_llm import Gemini
from google.genai import types, Client

from app.core.settings import settings
from app.services.agents.schemas import InferenceAgentOutput
from app.services.agents.tools import (
    search_candidate_targets,
    get_target_schema_details,
    check_type_compatibility,
    get_feedback_guidelines,
)

logger = logging.getLogger("landing_inference.agent")

# Agent instruction — kept at module level (pure data, no event-loop resources).
_INFERENCE_INSTRUCTION = """You are an expert data engineer on a schema intelligence platform.

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
"""


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


def _extract_json_block(text: str) -> str:
    """Extracts the first JSON object block bounded by '{' and '}' from the text."""
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text


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

    The genai.Client, VertexGemini, LlmAgent, and Runner are all created
    inside this function — NOT at module level. This is intentional:

    The subscriber calls asyncio.run() per Pub/Sub message. Each asyncio.run()
    creates a new event loop and tears it down when done. httpx.AsyncClient is
    bound to the event loop that created it. Any Client created outside the
    current asyncio.run() will have a closed httpx session on the second
    message, producing "Cannot send a request, as the client has been closed."

    Creating everything fresh per invocation ensures all resources belong to
    the current event loop.
    """
    logger.info(f"Running ADK Inference Agent for job_id: {job_id}")

    # 1. Build the Vertex AI client scoped to THIS event loop invocation.
    _client = Client(
        vertexai=True,
        project=settings.GCP_PROJECT_ID,
        location=settings.GCP_LOCATION,
        http_options=types.HttpOptions(timeout=60000),
    )

    class _VertexGemini(Gemini):
        """Routes to Vertex AI using the client created for this event loop."""
        @property
        def api_client(self) -> Client:
            return _client

    # 2. Build the LlmAgent for this invocation.
    # NOTE: output_schema is intentionally NOT set.
    # ADK enforces a hard constraint: when output_schema is set, the LLM
    # cannot also call tools — it enters an infinite tool-call loop. We
    # validate the free-text JSON response with Pydantic after the run.
    agent = LlmAgent(
        name="InferenceAgent",
        model=_VertexGemini(model=settings.VERTEX_GENERATIVE_MODEL or "gemini-2.5-flash"),
        description="Selects the optimal target landing zone and maps source schema fields.",
        instruction=_INFERENCE_INSTRUCTION,
        tools=[
            search_candidate_targets,
            get_target_schema_details,
            check_type_compatibility,
            get_feedback_guidelines,
        ],
    )

    # 3. Create session service and pre-load state.
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

    # 4. Create the Runner.
    runner = Runner(
        app_name="schema_intelligence",
        agent=agent,
        session_service=session_service,
    )

    # 5. Build the input message.
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

    # 6. Run the agent with a hard wall-clock timeout.
    # asyncio.wait_for cancels the coroutine if the agent stalls, preventing
    # indefinite hangs when Vertex AI does not return a final response.
    agent_timeout = settings.INFERENCE_AGENT_TIMEOUT_SECONDS
    final_response = None
    agent_event_count = 0

    async def _run_agent() -> None:
        nonlocal final_response, agent_event_count
        async for event in runner.run_async(
            session_id=session.id,
            user_id="system",
            new_message=content,
        ):
            agent_event_count += 1
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response = "".join(
                        part.text for part in event.content.parts
                        if part.text and not (getattr(part, "thought", None) is True)
                    )
                    logger.info("ADK Inference Agent completed with final response.")

    try:
        await asyncio.wait_for(_run_agent(), timeout=agent_timeout)
    except asyncio.TimeoutError:
        logger.error(f"ADK Inference Agent timed out after {agent_timeout}s for job_id={job_id}.")
        raise RuntimeError(
            f"ADK Inference Agent timed out after {agent_timeout}s — "
            "the LLM did not return a final response within the allowed window."
        )

    # 7. Validate and parse structured output via Pydantic, then return as dict.
    if final_response:
        cleaned_response = _extract_json_block(final_response)
        try:
            parsed = InferenceAgentOutput.model_validate_json(cleaned_response)
            return parsed.model_dump()
        except Exception:
            try:
                return json.loads(cleaned_response)
            except Exception as e:
                logger.error(
                    f"Failed to parse Inference Agent JSON output: {e}. "
                    f"Output was: {final_response}"
                )
                raise
    else:
        if agent_event_count == 0:
            raise RuntimeError(
                "ADK Inference Agent emitted no events — likely a network or "
                "infrastructure failure connecting to the model endpoint."
            )
        raise RuntimeError(
            f"ADK Inference Agent terminated after {agent_event_count} events "
            "without producing a final response. Check ADK node runner logs above for the root cause."
        )
