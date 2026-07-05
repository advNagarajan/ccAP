import json
import asyncio
import logging

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.google_llm import Gemini
from google.genai import types, Client

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

logger = logging.getLogger("schema_recommendation.agent")

# Agent instruction — kept at module level (pure data, no event-loop resources).
_RECOMMENDATION_INSTRUCTION = """You are an expert database administrator and data engineer on a schema intelligence platform.

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

    The genai.Client, _VertexGemini, LlmAgent, and Runner are all created
    inside this function — NOT at module level. This is intentional:

    The subscriber calls asyncio.run() per Pub/Sub message. Each asyncio.run()
    creates a new event loop and tears it down when done. httpx.AsyncClient is
    bound to the event loop that created it. Any Client created outside the
    current asyncio.run() will have a closed httpx session on the second
    message, producing "Cannot send a request, as the client has been closed."

    Creating everything fresh per invocation ensures all resources belong to
    the current event loop.
    """
    logger.info(f"Running ADK Recommendation Agent for job_id: {job_id}")

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
        name="RecommendationAgent",
        model=_VertexGemini(model=settings.VERTEX_GENERATIVE_MODEL or "gemini-2.5-flash"),
        description="Analyzes validation and drift findings to propose database/ingestion schema recommendations.",
        instruction=_RECOMMENDATION_INSTRUCTION,
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
    )

    # 3. Create session service and pre-load state.
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

    # 4. Create the Runner.
    runner = Runner(
        app_name="schema_recommendation",
        agent=agent,
        session_service=session_service,
    )

    # 5. Build the input message.
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

    # 6. Run the agent with a hard wall-clock timeout.
    agent_timeout = settings.RECOMMENDATION_AGENT_TIMEOUT_SECONDS
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
                    logger.info("ADK Recommendation Agent completed with final response.")

    try:
        await asyncio.wait_for(_run_agent(), timeout=agent_timeout)
    except asyncio.TimeoutError:
        logger.error(f"ADK Recommendation Agent timed out after {agent_timeout}s for job_id={job_id}.")
        raise RuntimeError(
            f"ADK Recommendation Agent timed out after {agent_timeout}s — "
            "the LLM did not return a final response within the allowed window."
        )

    # 7. Validate and parse structured output via Pydantic, then return as dict.
    if final_response:
        cleaned_response = _extract_json_block(final_response)
        try:
            parsed = RecommendationAgentOutput.model_validate_json(cleaned_response)
            return parsed.model_dump()
        except Exception:
            try:
                return json.loads(cleaned_response)
            except Exception as e:
                logger.error(
                    f"Failed to parse Recommendation Agent JSON output: {e}. "
                    f"Output was: {final_response}"
                )
                raise
    else:
        if agent_event_count == 0:
            raise RuntimeError(
                "ADK Recommendation Agent emitted no events — likely a network or "
                "infrastructure failure connecting to the model endpoint."
            )
        raise RuntimeError(
            f"ADK Recommendation Agent terminated after {agent_event_count} events "
            "without producing a final response. Check ADK node runner logs above for the root cause."
        )
