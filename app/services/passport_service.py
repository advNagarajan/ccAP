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
    (passport) for a target catalog row optimized for vector search.
    """
    passport_parts = []

    # 1. Semantic Summary
    target_name_title = target.target_name.replace('_', ' ').title()
    domain_str = f" in the {target.business_domain} domain" if target.business_domain else ""
    if target.description:
        desc_clean = target.description.rstrip('.')
        # Lowercase the first letter of description if it starts a sentence
        if len(desc_clean) > 0:
            desc_clean = desc_clean[0].lower() + desc_clean[1:]
        summary_line = f"Semantic Summary: Stores {target_name_title} records{domain_str} primarily used for {desc_clean}."
    else:
        summary_line = f"Semantic Summary: Stores and manages {target_name_title} database records{domain_str}."
    passport_parts.append(summary_line)

    # 2. Business Concepts
    concepts = []
    if target.business_domain:
        concepts.append(target.business_domain.lower())
    concepts.extend(target.target_name.lower().split('_'))
    if target.description:
        # Extract keywords longer than 3 characters, stripping punctuation
        words = [w.strip(".,()\"';:") for w in target.description.lower().split() if len(w) > 3]
        stopwords = {"used", "from", "with", "that", "this", "were", "been", "have", "metadata", "schema", "table"}
        for w in words:
            if w not in concepts and w not in stopwords:
                concepts.append(w)
    business_concepts = ", ".join(c.title() for c in concepts[:15])
    passport_parts.append(f"Business Concepts: {business_concepts}")

    # 3. Identity Context
    passport_parts.append(f"Target Database Asset: {target_name_title}")
    passport_parts.append(f"Target System Type: {target.target_type}")
    
    if target.business_domain:
        passport_parts.append(f"Business Domain: {target.business_domain}")
    
    if target.description:
        passport_parts.append(f"Description: {target.description}")

    # 4. Schema Fields
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
                        "type": col_type.get("type", "UNKNOWN")
                    })
    elif isinstance(schema_def, list):
        fields = schema_def

    if fields:
        passport_parts.append("Schema Fields:")
        
        # Grouping by parent/logical structures if available, default to "General Schema Columns"
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
                # Strip parenthetical precision/scale details (e.g., VARCHAR(255) -> VARCHAR)
                base_type = col_type.split("(")[0].strip().upper()
                passport_parts.append(f"    - Field: {col_name} ({base_type})")

    # 5. Connection context (stripping credential syntax noise)
    conn_details = target.connection_details or {}
    conn_keys = [k for k in conn_details.keys() if "password" not in k.lower() and "secret" not in k.lower() and "key" not in k.lower()]
    if conn_keys:
        conn_info = ", ".join(f"{k.replace('_', ' ').title()}: {conn_details[k]}" for k in conn_keys)
        passport_parts.append(f"Connection Information: {conn_info}")

    # 6. Human Engineering Feedback Logs
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
