import json
import logging
from app.models.db.target_catalog import TargetCatalog
from app.models.domain.recommendation_schema import SchemaRecommendationOutput
from app.services.llm import get_llm_provider

logger = logging.getLogger("recommendation_service")


def extract_deterministic_findings(validation_report: dict | None, drift_report: dict | None) -> dict:
    """
    Programmatically extracts raw findings from validation and drift reports.
    """
    val_rep = validation_report or {}
    dr_rep = drift_report or {}
    
    findings = {
        "missing_target_columns": val_rep.get("missing_target_columns", []),
        "additional_source_columns": val_rep.get("additional_source_columns", []),
        "datatype_mismatches": [],
        "renamed_columns": []
    }
    
    # Extract datatype issues from validation
    for issue in val_rep.get("datatype_issues", []):
        findings["datatype_mismatches"].append({
            "source_column": issue.get("source_column"),
            "target_column": issue.get("target_column"),
            "source_type": issue.get("source_type"),
            "target_type": issue.get("target_type"),
            "reason": issue.get("reason")
        })
        
    # Extract renamed columns from drift
    drift_summary = dr_rep.get("drift_summary", {})
    for rename in drift_summary.get("renamed_columns", []):
        findings["renamed_columns"].append({
            "source_column": rename.get("source_column"),
            "target_column": rename.get("target_column")
        })
        
    return findings


async def generate_schema_recommendations(
    findings: dict,
    target_catalog: TargetCatalog,
    partitioning_rec: str | None,
    feedback_str: str | None = None
) -> SchemaRecommendationOutput:
    """
    Calls the LLM provider to enrich the deterministic findings into sequenced recommendations.
    """
    llm = get_llm_provider()
    
    target_name = target_catalog.target_name
    target_type = target_catalog.target_type
    target_schema = target_catalog.schema_definition
    
    target_schema_str = json.dumps(target_schema, indent=2) if target_schema else "{}"
    findings_str = json.dumps(findings, indent=2)
    partitioning_rec_str = partitioning_rec or "None"
    
    feedback_context = f"\n6. Human Engineering Feedback Guidelines:\n{feedback_str}" if feedback_str else ""
    
    prompt = f"""You are an expert database administrator and data engineer.
Your task is to analyze schema validation and drift findings between a source dataset and a target data store, and generate a sequence of recommended alignment operations.

---
INPUT CONTEXT:
1. Target Name: {target_name}
2. Target Type: {target_type}
3. Target Schema: {target_schema_str}
4. Deterministic Findings: {findings_str}
5. Prior Partitioning Recommendation: {partitioning_rec_str}{feedback_context}

---
CRITICAL RULES & CONSTRAINTS:
1. Hard Constraint: You must derive recommendations EXCLUSIVELY from the deterministic findings provided. Do not invent, assume, or suggest additional schema issues, governance rules, naming conventions, or generic optimizations.
2. Prefer Least Disruptive Remediation: Recommend the simplest, least invasive change that successfully resolves the specific discrepancy.
3. Prefer Source-First Alignment: Prioritize transforming the incoming source dataset. If a finding can be resolved by either transforming the source or modifying the target, prefer the source transformation unless there is clear evidence that the target schema should evolve (e.g. the target cannot represent legitimate source business data).
4. If no action is required, return an empty recommendations list and explain in the overall explanation why no remediation is necessary.
5. Strategy Separation:
   - For SQL/Relational Targets: Use operations like ALTER TABLE, datatype modifications, nullable handling, and column additions. Provide the exact SQL DDL in the suggested_action.
   - For NoSQL/Semi-structured Targets: Focus on field mapping, document normalization, schema evolution guidance, and application-level transformations. Do NOT suggest SQL DDL commands.

For each individual recommendation, you must include a confidence_score between 0.0 (no confidence) and 1.0 (absolute certainty).

Format your response strictly as JSON matching the requested response schema."""

    try:
        response_str = await llm.generate_response(
            prompt=prompt,
            response_schema=SchemaRecommendationOutput
        )
        output_data = json.loads(response_str)
        return SchemaRecommendationOutput.model_validate(output_data)
    except Exception as e:
        logger.error(f"Failed to generate schema recommendations: {e}")
        return SchemaRecommendationOutput(
            recommendations=[],
            explanation=f"Error generating AI recommendations: {str(e)}"
        )
