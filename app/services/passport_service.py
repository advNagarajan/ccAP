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
    fields = schema_def.get("fields", [])

    if fields:
        passport_parts.append("Structure Schema Fields:")
        
        # Grouping by parent/logical structures if available, default to "General"
        grouped_fields = {}
        for f in fields:
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
    Retrieves dense vector representation from Google GenAI embedding model (text-embedding-004).
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning("No GEMINI_API_KEY found in settings. Falling back to mock vector.")
        # Return a deterministic mock vector of 768 dimensions for testing/fallback
        return [0.0] * 768

    try:
        # Initialize the GenAI Client with settings API key
        client = genai.Client(api_key=api_key)
        
        # Execute the call in an executor to keep it async friendly
        response = await asyncio.to_thread(
            client.models.embed_content,
            model="text-embedding-004",
            contents=text
        )
        
        if not response or not response.embeddings:
            raise ValueError("No embeddings returned from Gemini API.")
            
        return response.embeddings[0].values
    except Exception as e:
        logger.error(f"Error fetching vector embedding from Gemini API: {e}")
        # Return fallback or reraise
        raise
