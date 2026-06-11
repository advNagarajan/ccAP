import asyncio
import os
import logging
from typing import List, Optional
from google import genai

from app.models.target_catalog import TargetCatalog
from app.models.llm_feedback_loop import LlmFeedbackLoop
from app.core.settings import settings

logger = logging.getLogger("vector_sync")


def generate_target_passport_text(
    target: TargetCatalog,
    feedback_logs: List[LlmFeedbackLoop]
) -> str:
    """
    Compiles a deterministic, embedding-optimized natural language description
    (passport) for a target catalog row.
    """
    passport_parts = []

    # 1. Identity Context
    passport_parts.append(f"Target Database Asset: {target.target_name.replace('_', ' ').title()}")
    passport_parts.append(f"Target System Type: {target.target_type}")
    
    if target.business_domain:
        passport_parts.append(f"Business Domain: {target.business_domain}")
    
    if target.description:
        passport_parts.append(f"Description: {target.description}")

    # 2. Schema Structure
    schema_def = target.schema_definition or {}
    fields = []
    if isinstance(schema_def, dict):
        if "fields" in schema_def and isinstance(schema_def["fields"], list):
            fields = schema_def["fields"]
        else:
            # Handle key-value columns structure
            for col_name, col_type in schema_def.items():
                if isinstance(col_type, str):
                    fields.append({
                        "name": col_name,
                        "type": col_type
                    })
                elif isinstance(col_type, dict):
                    fields.append({
                        "name": col_name,
                        "type": col_type.get("type", "UNKNOWN"),
                        "primary_key": col_type.get("primary_key", False),
                        "nullable": col_type.get("nullable", True)
                    })
    elif isinstance(schema_def, list):
        fields = schema_def

    if fields:
        passport_parts.append("Structure Schema Fields:")
        
        # Grouping by parent/logical structures if available, default to "General"
        grouped_fields = {}
        for f in fields:
            if not isinstance(f, dict):
                continue
            parent = f.get("parent") or "General Schema Columns"
            parent_title = parent.replace("_", " ").title()
            grouped_fields.setdefault(parent_title, []).append(f)

        for parent_title, col_list in grouped_fields.items():
            passport_parts.append(f"  Under {parent_title}:")
            for col in col_list:
                col_name = col.get("name", "").replace("_", " ").title()
                col_type = col.get("type", "UNKNOWN")
                
                tags = []
                # Check for primary key / unique tags
                if col.get("primary_key") or col.get("is_unique") or "unique" in str(col.get("constraints", "")).lower():
                    tags.append("(unique identifier)")
                
                # Check for non-nullable/required tags
                if col.get("nullable") is False or col.get("required") is True or "not null" in str(col.get("constraints", "")).lower():
                    tags.append("(present in 100% of records)")

                tag_suffix = " " + " ".join(tags) if tags else ""
                passport_parts.append(f"    - Column Name: {col_name}, Data Type: {col_type}{tag_suffix}")

    # 3. Connection context (stripping credential syntax noise)
    conn_details = target.connection_details or {}
    conn_keys = [k for k in conn_details.keys() if "password" not in k.lower() and "secret" not in k.lower() and "key" not in k.lower()]
    if conn_keys:
        conn_info = ", ".join(f"{k.replace('_', ' ').title()}: {conn_details[k]}" for k in conn_keys)
        passport_parts.append(f"Connection Information: {conn_info}")

    # 4. Human Engineering Feedback Logs
    if feedback_logs:
        passport_parts.append("Historical Human Engineering Feedback Guidelines:")
        for log in feedback_logs:
            paths = ", ".join(log.observed_flattened_paths)
            passport_parts.append(
                f"  - Action Taken: {log.user_action} for Ingested Paths: [{paths}]. "
                f"Engineer Notes: {log.engineer_notes or 'No notes left.'}"
            )

    return "\n".join(passport_parts)


async def get_vector_embedding(text: str) -> List[float]:
    """
    Retrieves dense vector representation from the configured embedding provider.
    """
    from app.services.llm import get_embedding_provider

    try:
        provider = get_embedding_provider()
        return await provider.get_embedding(text)
    except Exception as e:
        logger.error(f"Error fetching vector embedding: {e}")
        raise
