import json
import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.db.target_catalog import TargetCatalog
from app.models.domain.inference_schema import (
    TargetSelectionSchema,
    TargetMappingSchema
)
from app.services.llm import get_llm_provider
from app.services.metadata_service import generate_target_llm_optimized_json

logger = logging.getLogger("inference_service")


async def generate_target_inference(
    db: Session,
    source_json: dict,
    candidates: list[TargetCatalog],
    predefined_single: bool,
    feedback_prompt_part: str = ""
) -> dict:
    """
    Executes the two-pass target inference logic using the LLM provider.
    - Pass 1: Selects the best candidate target database table.
    - Pass 2: Maps columns, provides naming suggestions and partitioning strategy recommendations.

    If predefined_single is True, target selection is bypassed and confidence is forced to 1.0.
    If a selected target ID is returned but cannot be verified as a valid UUID or does not exist
    in the database catalog, a RuntimeError (representing LLM hallucination) is raised.
    """
    llm_provider = get_llm_provider()

    # Case 1: Predefined Single Target - Bypass selection, go straight to mapping pass
    if predefined_single:
        if not candidates:
            raise ValueError("Predefined single target case selected but no candidates provided.")
        selected_target = candidates[0]
        selected_target_id_str = str(selected_target.target_id)
        confidence = 1.0
        selection_reasoning = "Using predefined single target candidate from configuration."
        logger.info(f"Case 1: Single predefined target candidate used: {selected_target_id_str}")

        target_json = generate_target_llm_optimized_json(selected_target)
        prompt_mapping = (
            "Map the incoming source dataset schema to the selected target database table schema.\n\n"
            "Source Schema:\n"
            f"{json.dumps(source_json, indent=2)}\n\n"
            "Selected Target Table:\n"
            f"Target ID: {selected_target.target_id}\n"
            f"Target Name: {selected_target.target_name}\n"
            f"Description: {selected_target.description or 'No description'}\n"
            f"Schema Fields:\n{json.dumps(target_json['fields'], indent=2)}\n"
            f"{feedback_prompt_part}\n\n"
            "Instructions & Constraints:\n"
            "1. Column Mapping: Map source columns to target columns. Map to null if unmatched. Only use explicitly defined target schema fields.\n"
            "2. Coverage: Identify unmapped source columns ('unmapped_source_columns') and missing target columns ('missing_target_columns').\n"
            "3. Partitioning: Recommend column/strategy ONLY if a date, timestamp, or high-cardinality ID field exists in source. Otherwise return null.\n"
            "4. Casing: Suggest standard naming adjustments to reconcile source names with target conventions (e.g. lowercase snake_case for PostgreSQL).\n"
            "5. STRICT BOUNDARIES: Do NOT perform target selection or compare tables. Assume the provided target is correct. Explain mapping/partition decisions in 'reasoning' in under 3 sentences.\n"
            "6. Your response MUST be valid JSON adhering exactly to the TargetMappingSchema."
        )

        logger.info(f"Sending mapping pass prompt to LLM:\n{prompt_mapping}")
        mapping_response = await llm_provider.generate_response(
            prompt=prompt_mapping,
            response_schema=TargetMappingSchema
        )
        logger.info(f"Raw LLM Structured Mapping Response:\n{mapping_response}")
        mapping_json = json.loads(mapping_response)

        return {
            "selected_target_id": selected_target_id_str,
            "confidence_score": confidence,
            "reasoning": f"Selection Reason: {selection_reasoning}\nMapping Details: {mapping_json.get('reasoning', '')}",
            "column_mapping": mapping_json.get("column_mapping"),
            "unmapped_source_columns": mapping_json.get("unmapped_source_columns", []),
            "missing_target_columns": mapping_json.get("missing_target_columns", []),
            "partitioning_recommendation": mapping_json.get("partitioning_recommendation"),
            "naming_convention_suggestions": mapping_json.get("naming_convention_suggestions")
        }

    else:
        # Pass 1: Selection Prompt
        candidates_context = []
        for idx, target in enumerate(candidates, 1):
            target_json = generate_target_llm_optimized_json(target)
            candidates_context.append(
                f"Candidate {idx}\n"
                f"Target ID: {target.target_id}\n"
                f"Target Name: {target.target_name}\n"
                f"Business Domain: {target.business_domain or 'General'}\n"
                f"Description: {target.description or 'No description'}\n"
                f"Schema Fields:\n{json.dumps(target_json['fields'], indent=2)}\n"
                f"----------------------------------------"
            )
        candidates_str = "\n".join(candidates_context)

        prompt_selection = (
            "Evaluate candidate database tables and select the most apt target landing zone for the incoming source dataset schema.\n\n"
            "Source Schema:\n"
            f"{json.dumps(source_json, indent=2)}\n\n"
            "Candidate Target Tables:\n"
            f"{candidates_str}"
            f"{feedback_prompt_part}\n\n"
            "Instructions & Constraints:\n"
            "1. Evaluate by: semantic meaning, column name alignment, schema coverage, data type compatibility, and similarity score to select the most apt target table.\n"
            "2. Retrieval-Awareness: Candidates are pre-selected via vector similarity. Consider scores as supporting evidence, not the sole decision factor.\n"
            "3. No-Match Handling: If no candidate is compatible, return selected_target_id = null. Do not force a match.\n"
            "4. STRICT BOUNDARIES: Do NOT generate column mappings, unmapped/missing column lists, partitioning recommendations, or casing suggestions. Explain your selection in 'reasoning' in under 3 sentences.\n"
            "5. Your response MUST be valid JSON adhering exactly to the TargetSelectionSchema."
        )

        logger.info(f"Sending selection pass prompt to LLM:\n{prompt_selection}")
        selection_response = await llm_provider.generate_response(
            prompt=prompt_selection,
            response_schema=TargetSelectionSchema
        )
        logger.info(f"Raw LLM Structured Selection Response:\n{selection_response}")
        selection_json = json.loads(selection_response)

        selected_target_id_str = selection_json.get("selected_target_id")
        if selected_target_id_str in (None, "", "null", "None"):
            selected_target_id_str = None

        confidence = float(selection_json.get("confidence_score", 0.0))
        selection_reasoning = selection_json.get("reasoning", "No selection reasoning provided.")

        selected_target = None
        if selected_target_id_str:
            try:
                selected_uuid = UUID(selected_target_id_str)
            except ValueError:
                raise RuntimeError(f"LLM Hallucination: selected target ID '{selected_target_id_str}' is not a valid UUID format.")

            selected_target = next((t for t in candidates if t.target_id == selected_uuid), None)
            if not selected_target:
                selected_target = db.get(TargetCatalog, selected_uuid)
                if not selected_target:
                    raise RuntimeError(f"LLM Hallucination: selected target ID '{selected_target_id_str}' was not found in the database catalog.")

        if selected_target:
            # Pass 2: Mapping prompt
            target_json = generate_target_llm_optimized_json(selected_target)
            prompt_mapping = (
                "Map the incoming source dataset schema to the selected target database table schema.\n\n"
                "Source Schema:\n"
                f"{json.dumps(source_json, indent=2)}\n\n"
                "Selected Target Table:\n"
                f"Target ID: {selected_target.target_id}\n"
                f"Target Name: {selected_target.target_name}\n"
                f"Description: {selected_target.description or 'No description'}\n"
                f"Schema Fields:\n{json.dumps(target_json['fields'], indent=2)}\n"
                f"{feedback_prompt_part}\n\n"
                "Instructions & Constraints:\n"
                "1. Column Mapping: Map source columns to target columns. Map to null if unmatched. Only use explicitly defined target schema fields.\n"
                "2. Coverage: Identify unmapped source columns ('unmapped_source_columns') and missing target columns ('missing_target_columns').\n"
                "3. Partitioning: Recommend column/strategy ONLY if a date, timestamp, or high-cardinality ID field exists in source. Otherwise return null.\n"
                "4. Casing: Suggest standard naming adjustments to reconcile source names with target conventions (e.g. lowercase snake_case for PostgreSQL).\n"
                "5. STRICT BOUNDARIES: Do NOT perform target selection or compare tables. Assume the provided target is correct. Explain mapping/partition decisions in 'reasoning' in under 3 sentences.\n"
                "6. Your response MUST be valid JSON adhering exactly to the TargetMappingSchema."
            )

            logger.info(f"Sending mapping pass prompt to LLM:\n{prompt_mapping}")
            mapping_response = await llm_provider.generate_response(
                prompt=prompt_mapping,
                response_schema=TargetMappingSchema
            )
            logger.info(f"Raw LLM Structured Mapping Response:\n{mapping_response}")
            mapping_json = json.loads(mapping_response)

            return {
                "selected_target_id": selected_target_id_str,
                "confidence_score": confidence,
                "reasoning": f"Selection Reason: {selection_reasoning}\nMapping Details: {mapping_json.get('reasoning', '')}",
                "column_mapping": mapping_json.get("column_mapping"),
                "unmapped_source_columns": mapping_json.get("unmapped_source_columns", []),
                "missing_target_columns": mapping_json.get("missing_target_columns", []),
                "partitioning_recommendation": mapping_json.get("partitioning_recommendation"),
                "naming_convention_suggestions": mapping_json.get("naming_convention_suggestions")
            }
        else:
            # Target selection returned null or target not found
            return {
                "selected_target_id": None,
                "confidence_score": confidence,
                "reasoning": f"Selection Reason: {selection_reasoning}",
                "column_mapping": None,
                "unmapped_source_columns": [],
                "missing_target_columns": [],
                "partitioning_recommendation": None,
                "naming_convention_suggestions": None
            }
