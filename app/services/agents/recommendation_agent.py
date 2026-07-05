import json
import logging
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.core.settings import settings
from app.services.agents.schemas import RecommendationAgentOutput
from app.services.agents.tools import (
    get_target_schema_details,
    check_type_compatibility,
    get_validation_report,
    get_drift_report,
    get_source_metadata,
    get_data_quality_report,
    get_historical_recommendations,
    get_recommendation_feedback,
)

from functools import cached_property
from google.adk.models.google_llm import Gemini
from google.genai import Client

logger = logging.getLogger("schema_recommendation.agent")


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


# Define the Recommendation Agent
# NOTE: output_schema is intentionally NOT set here.
# ADK enforces a hard constraint: when output_schema is set, the LLM cannot
# also call tools — it enters an infinite tool-call loop. Instead we validate
# the free-text JSON response with Pydantic after the run loop finishes.
recommendation_agent = LlmAgent(
    name="RecommendationAgent",
    model=VertexGemini(model=settings.VERTEX_GENERATIVE_MODEL or "gemini-2.5-flash"),
    description="Analyzes validation and drift findings to propose database/ingestion schema recommendations.",
    instruction="""You are an expert database administrator and data engineer on a schema intelligence platform.

Your task: Given validation and drift findings for a source-to-target schema mapping,
produce the most comprehensive remediation plan possible.

IMPORTANT: The target_type determines your remediation language:
- POSTGRESQL/MYSQL: SQL DDL (ALTER TABLE, CREATE INDEX)
- BIGQUERY: BigQuery DDL + partitioning/clustering directives
- SNOWFLAKE: Snowflake DDL + VARIANT handling for semi-structured
- GCS/S3: File schema evolution rules (Parquet/Avro additive changes)
- DELTA: Delta Lake schema evolution + merge strategies

WORKFLOW:
1. Call 'get_validation_report' to inspect validation health (coverage %, type issues,
   invalid mappings, missing/additional columns).
2. Call 'get_drift_report' to inspect drift analysis (new/removed/renamed columns,
   datatype changes, drift severity score).
3. Call 'get_target_schema_details' with the target_id to see full target field
   definitions (types, constraints, primary keys, nullable flags) AND the target_type.
4. Call 'get_source_metadata' to inspect actual source data characteristics:
   - Column statistics: null ratios, distinct counts, sample values, min/max,
     uniqueness, numeric statistics.
   - Structure metadata: nested_fields, array_fields, flattened_paths, max_depth.
   - Use ALL of this to make evidence-based recommendations.
5. Call 'get_data_quality_report' to check if data quality rules flagged issues.
   This may return info/null if DQ is not enabled or unavailable. Handle gracefully.
6. For any datatype mismatch you plan to recommend, call 'check_type_compatibility'
   to verify the conversion is valid before suggesting it.
7. Call 'get_historical_recommendations' with target_id to see past completed recommendations
   for this target — maintain consistency and avoid redundant recommendations.
8. Call 'get_recommendation_feedback' to read stage feedback guidelines left by engineers.

STRUCTURAL TRANSFORMATION RULES (critical for NoSQL/semi-structured sources):
- If source has nested_fields (e.g., 'address' with paths 'address.city', 'address.zip')
  and target is SQL: recommend FLATTEN_NESTED with explicit target column names.
- If source has array_fields (e.g., 'tags') and target is SQL:
  recommend UNNEST_ARRAY into a join table, or SERIALIZE_TO_JSON if the array is opaque.
- If source field presence/presence_percentage shows a path appears in <80% of records and target column is NOT NULL:
  recommend SET_DEFAULT or ADD_NULLABLE_HANDLING.
- If source max_depth > 1 and target is flat SQL: recommend multi-level flattening
  with parent_child naming conventions.
- If target is BIGQUERY: use STRUCT/ARRAY types instead of flattening when appropriate.
- If target is SNOWFLAKE: use VARIANT for deeply nested data.

OUTPUT REQUIREMENTS:
- recommendations[]: Sequenced list. Valid action_types:
  ADD_COLUMN, REMOVE_COLUMN, RENAME_COLUMN, MODIFY_TYPE, CREATE_PARTITION,
  ADD_NULLABLE_HANDLING, FLATTEN_NESTED, UNNEST_ARRAY, SERIALIZE_TO_JSON,
  APPLY_CAST, SET_DEFAULT, ADD_CLUSTERING.
  Each must have: sequence_order, action_type, target (source|target), column_name,
  priority (HIGH|MEDIUM|LOW), reason, suggested_action, confidence_score.

- explanation: Overall remediation plan summary.

- impact_assessment: {
    breaking_changes: list of changes that alter existing column semantics,
    non_breaking_changes: list of additive/nullable changes,
    structural_transforms: list of flattening/unnesting operations,
    affected_column_count: total columns impacted,
    estimated_downstream_impact: "LOW" | "MEDIUM" | "HIGH"
  }

- transformation_plan: Target-type-aware execution plan.
  For SQL targets: { target_type, ddl_statements[], pre_load_transforms[] }
  For BigQuery: add partitioning{} and clustering[].
  For GCS/S3: { schema_evolution[], recommended_format, pre_load_transforms[] }
  For Delta: { schema_evolution[], merge_strategy{}, z_order_columns[] }

- data_quality_flags: DQ-informed column-level warnings. Null if DQ unavailable.

- risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"

- estimated_effort: "TRIVIAL" | "LOW" | "MEDIUM" | "HIGH"
  HIGH = structural redesign (nested flattening, array unnesting, schema rewrite).

CONSTRAINTS:
- Derive recommendations EXCLUSIVELY from tool outputs. Do NOT invent issues.
- Prefer least disruptive remediation (source transforms > target alterations).
- Use sample values, statistics, and structure metadata as evidence in reasoning.
- If a DQ rule flagged column X, your recommendation for column X must acknowledge it.
- Match suggested_action format to the target_type:
  SQL targets: include exact DDL.
  File targets: describe schema evolution rules.
  NoSQL targets: describe document transformation operations.
- If no action is needed, return empty recommendations with explanation.
- When you have finished your analysis, respond with ONLY a valid JSON object
  matching the RecommendationAgentOutput schema — no markdown fences, no extra keys.
""",
    tools=[
        get_target_schema_details,
        check_type_compatibility,
        get_validation_report,
        get_drift_report,
        get_source_metadata,
        get_data_quality_report,
        get_historical_recommendations,
        get_recommendation_feedback,
    ],
    max_turns=12,
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


async def run_recommendation_agent(
    job_id: str,
    target_id: str,
    validation_id: str,
    drift_id: str,
    partitioning_recommendation: str | None,
    db,  # SQLAlchemy Session
) -> dict:
    """
    Initializes and executes the Recommendation Agent via ADK Runner.
    Returns a dict matching the RecommendationAgentOutput schema shape.
    """
    logger.info(f"Running ADK Recommendation Agent for job_id: {job_id}")

    # 1. Create session service and pre-load state
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="schema_recommendation",
        user_id="system",
        state={
            "db": SessionProxy(db),
            "job_id": job_id,
            "target_id": target_id,
            "validation_id": validation_id,
            "drift_id": drift_id,
        }
    )

    # 2. Create the Runner
    runner = Runner(
        app_name="schema_recommendation",
        agent=recommendation_agent,
        session_service=session_service,
    )

    # 3. Build the input message
    input_text = (
        f"Analyze validation and drift findings to produce a remediation plan.\n\n"
        f"Context details:\n"
        f"- Target ID: {target_id}\n"
        f"- Validation ID: {validation_id}\n"
        f"- Drift ID: {drift_id}\n"
        f"- Partitioning Recommendation from Inference: {partitioning_recommendation or 'None'}"
    )
    content = types.Content(
        role="user",
        parts=[types.Part(text=input_text)]
    )

    # 4. Run the agent with a hard wall-clock timeout.
    # asyncio.wait_for cancels the coroutine if the agent stalls, preventing
    # indefinite hangs when Vertex AI does not return a final response.
    agent_timeout = settings.RECOMMENDATION_AGENT_TIMEOUT_SECONDS
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
                    logger.info("ADK Recommendation Agent completed with final response.")

    try:
        await asyncio.wait_for(_run_agent(), timeout=agent_timeout)
    except asyncio.TimeoutError:
        logger.error(
            f"ADK Recommendation Agent timed out after {agent_timeout}s for job_id={job_id}. "
            "Returning fallback response."
        )
        return {
            "recommendations": [],
            "explanation": f"Agent timed out after {agent_timeout} seconds.",
            "impact_assessment": {},
            "transformation_plan": None,
            "data_quality_flags": None,
            "risk_level": "LOW",
            "estimated_effort": None,
        }

    # 5. Validate and parse structured output via Pydantic, then return as dict.
    # We validate with the schema here rather than in the LlmAgent constructor
    # because ADK does not support output_schema when tools are also present.
    if final_response:
        try:
            parsed = RecommendationAgentOutput.model_validate_json(final_response)
            return parsed.model_dump()
        except Exception:
            # Fall back to raw JSON parse if Pydantic validation fails
            try:
                return json.loads(final_response)
            except Exception as e:
                logger.error(
                    f"Failed to parse Recommendation Agent JSON output: {e}. "
                    f"Output was: {final_response}"
                )
                raise
    else:
        logger.warning("ADK Recommendation Agent did not emit a final response.")
        return {
            "recommendations": [],
            "explanation": "Agent did not produce a final response.",
            "impact_assessment": {},
            "transformation_plan": None,
            "data_quality_flags": None,
            "risk_level": "LOW",
            "estimated_effort": None,
        }
