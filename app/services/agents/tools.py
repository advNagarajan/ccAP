import json
import logging
from uuid import UUID
from sqlalchemy import select
from google.adk.tools import ToolContext

from app.core.settings import settings
from app.models.db.target_catalog import TargetCatalog
from app.models.db.llm_feedback_loop import LlmFeedbackLoop
from app.services.metadata_service import generate_target_llm_optimized_json
from app.constants.compatibility import COMPATIBILITY_MATRIX

logger = logging.getLogger("landing_inference.tools")


def search_candidate_targets(
    source_summary: str,
    tool_context: ToolContext
) -> str:
    """
    Search the target catalog for candidate landing zones matching the source dataset.
    Returns a summary list of candidates (IDs, names, types, domains, similarity scores).
    Does NOT return full schema field details — use 'get_target_schema_details' for that.

    Args:
        source_summary: Natural language description of the source dataset including
            column names, observed data types, and approximate row count.
        tool_context: Runtime context injected by the ADK framework.

    Returns:
        JSON string with a list of candidate objects containing:
        target_id, target_name, target_type, business_domain, description,
        similarity_score, field_count.
    """
    db = tool_context.state["db"]
    predefined_ids = tool_context.state.get("predefined_target_ids", [])
    
    db_targets = []
    
    # Resolve predefined targets if config contains any
    if predefined_ids:
        logger.info(f"Resolving {len(predefined_ids)} predefined targets in tool search.")
        target_uuids = []
        for tid in predefined_ids:
            try:
                target_uuids.append(UUID(str(tid)))
            except ValueError:
                pass
        if target_uuids:
            stmt = select(TargetCatalog).where(TargetCatalog.target_id.in_(target_uuids))
            db_targets = list(db.scalars(stmt).all())
            
    candidates = []
    
    if db_targets:
        # Case A / B: Predefined target IDs resolved from database
        for target in db_targets:
            fields_len = 0
            schema_def = target.schema_definition or {}
            if isinstance(schema_def, dict):
                fields_len = len(schema_def.get("fields", schema_def))
            elif isinstance(schema_def, list):
                fields_len = len(schema_def)
                
            candidates.append({
                "target_id": str(target.target_id),
                "target_name": target.target_name,
                "target_type": target.target_type,
                "business_domain": target.business_domain,
                "description": target.description,
                "similarity_score": 1.0,  # Predefined defaults to max confidence
                "field_count": fields_len
            })
    else:
        # Case C: No predefined targets -> run pgvector search using injected source_embedding
        source_embedding = tool_context.state.get("source_embedding")
        if source_embedding is None:
            logger.warning("No source embedding available in context state.")
            return json.dumps({"error": "Cannot perform semantic search: source embedding is missing."})
            
        logger.info("Executing pgvector cosine search for candidate targets in tool search.")
        distance_expr = TargetCatalog.target_embedding.cosine_distance(source_embedding)
        stmt = (
            select(TargetCatalog, (1.0 - distance_expr).label("similarity"))
            .where(TargetCatalog.target_embedding.is_not(None))
            .order_by(distance_expr)
            .limit(settings.TARGET_INFERENCE_TOP_K)
        )
        search_results = db.execute(stmt).all()
        
        for target, similarity in search_results:
            fields_len = 0
            schema_def = target.schema_definition or {}
            if isinstance(schema_def, dict):
                fields_len = len(schema_def.get("fields", schema_def))
            elif isinstance(schema_def, list):
                fields_len = len(schema_def)
                
            candidates.append({
                "target_id": str(target.target_id),
                "target_name": target.target_name,
                "target_type": target.target_type,
                "business_domain": target.business_domain,
                "description": target.description,
                "similarity_score": float(similarity),
                "field_count": fields_len
            })
            
    return json.dumps(candidates, indent=2)


def get_target_schema_details(
    target_id: str,
    tool_context: ToolContext
) -> str:
    """
    Retrieve the complete schema definition for a specific target table/collection/file.
    Returns column/field names, data types, primary key flags, nullable flags,
    uniqueness constraints, descriptions, and the target's connection type.

    Args:
        target_id: UUID string of the target catalog entry to inspect.
        tool_context: Runtime context injected by the ADK framework.

    Returns:
        JSON string with target_name, target_type, business_domain, description,
        and a 'fields' array of {name, type, primary_key, nullable, is_unique, description}.
        Returns an error message if target_id is not found.
    """
    db = tool_context.state["db"]
    try:
        target_uuid = UUID(target_id)
    except ValueError:
        return json.dumps({"error": f"Invalid UUID format: {target_id}"})
        
    target = db.get(TargetCatalog, target_uuid)
    if target is None:
        return json.dumps({"error": f"Target catalog entry with ID {target_id} not found."})
        
    optimized_json = generate_target_llm_optimized_json(target)
    return json.dumps(optimized_json, indent=2)


def check_type_compatibility(
    source_type: str,
    target_type: str
) -> str:
    """
    Check whether a source data type is compatible with a target column/field type
    using the platform's centralized compatibility matrix.

    Args:
        source_type: The observed Python type from the source dataset
            (e.g., 'int', 'str', 'float', 'bool', 'dict', 'list', 'date', 'datetime').
        target_type: The declared type of the target column
            (e.g., 'VARCHAR', 'INTEGER', 'TIMESTAMP', 'JSONB', 'BOOLEAN').
            For NoSQL or file targets, pass the schema-declared type as-is.

    Returns:
        JSON string with: status ('COMPATIBLE'|'WARNING'|'INCOMPATIBLE'|'DEFERRED'),
        source_type, target_type, and explanation.
    """
    if not source_type or not target_type:
        return json.dumps({"error": "Missing source_type or target_type argument."})
        
    src_type = source_type.strip().lower()
    tgt_type_raw = target_type.strip()
    tgt_type = tgt_type_raw.upper().split("(")[0].strip()
    
    if tgt_type in COMPATIBILITY_MATRIX:
        rules = COMPATIBILITY_MATRIX[tgt_type]
        if src_type in rules["compatible"]:
            status = "COMPATIBLE"
            explanation = f"Type '{source_type}' maps cleanly to target type '{target_type}'."
        elif src_type in rules["warning"]:
            status = "WARNING"
            explanation = f"Mapping '{source_type}' to '{target_type}' is allowed but may trigger conversion warnings or require explicit casting."
        else:
            status = "INCOMPATIBLE"
            explanation = f"Observed type '{source_type}' cannot be safely converted to target column type '{target_type}'."
    else:
        status = "DEFERRED"
        explanation = f"Target data type '{tgt_type_raw}' is not checked by the relational compatibility matrix (applicable for NoSQL/files)."
        
    return json.dumps({
        "status": status,
        "source_type": source_type,
        "target_type": target_type,
        "explanation": explanation
    }, indent=2)


def get_feedback_guidelines(
    tool_context: ToolContext
) -> str:
    """
    Retrieve global engineering feedback guidelines relevant to the inference stage.
    These are human-written notes about how schema selection and mapping decisions
    should be adjusted based on past experience. Target-specific feedback is already
    reflected in the target catalog embeddings and does not need separate retrieval.

    Args:
        tool_context: Runtime context injected by the ADK framework.

    Returns:
        JSON string with a list of feedback entries containing engineer_notes
        and the user_action taken. Returns an empty list if no global inference
        feedback exists.
    """
    db = tool_context.state["db"]
    
    # Query database for global stage-specific feedback
    feedback_records = db.scalars(
        select(LlmFeedbackLoop)
        .where(
            LlmFeedbackLoop.stage.ilike("%inference%")
        )
        .order_by(LlmFeedbackLoop.created_at.desc())
        .limit(20)
    ).all()
    
    guidelines = []
    for record in feedback_records:
        if record.engineer_notes:
            guidelines.append({
                "engineer_notes": record.engineer_notes,
                "user_action": record.user_action or "No action recorded"
            })
            
    return json.dumps(guidelines, indent=2)
