from pydantic import BaseModel, Field
from app.models.domain.recommendation_schema import RecommendationOp

class InferenceAgentOutput(BaseModel):
    """Structured output matching LandingInference DB columns exactly."""
    selected_target_id: str | None = Field(
        default=None,
        description="UUID of the selected target, or null if no match found."
    )
    confidence_score: float = Field(
        description="0.0 to 1.0 confidence in the selection and mapping."
    )
    reasoning: str = Field(
        description="Combined selection and mapping rationale (under 5 sentences)."
    )
    column_mapping: dict[str, str | None] | None = Field(
        default=None,
        description="Source column name -> target column name (or null if unmapped)."
    )
    unmapped_source_columns: list[str] = Field(
        default_factory=list,
        description="Source columns that could not be mapped to any target column."
    )
    missing_target_columns: list[str] = Field(
        default_factory=list,
        description="Target columns with no corresponding source column."
    )
    partitioning_recommendation: str | None = Field(
        default=None,
        description="Recommended partitioning column and strategy (e.g., 'partition by created_at MONTHLY'), or null."
    )
    naming_convention_suggestions: dict[str, str] | None = Field(
        default=None,
        description="Suggested renames for source columns to match target naming conventions."
    )


class RecommendationAgentOutput(BaseModel):
    """Structured output for the Recommendation Agent, capturing rich metrics & execution plans."""

    recommendations: list[RecommendationOp] = Field(
        description="Sequenced list of recommended actions. Must be empty if no action/remediation is required."
    )
    explanation: str = Field(
        description="Overall summary or explanation of the remediation plan. If no action is required, this explains why."
    )
    impact_assessment: dict = Field(
        default_factory=dict,
        description="Impact breakdown: breaking_changes, non_breaking_changes, structural_transforms, affected_column_count, estimated_downstream_impact."
    )
    transformation_plan: dict | None = Field(
        default=None,
        description="Target-type-aware execution plan (ddl_statements, pre_load_transforms, partitioning, clustering, schema_evolution, etc.)."
    )
    data_quality_flags: list[dict] | None = Field(
        default=None,
        description="Column-level warnings informed by recent DQ metrics."
    )
    risk_level: str = Field(
        default="LOW",
        description="Overall migration risk level: LOW, MEDIUM, HIGH, CRITICAL."
    )
    estimated_effort: str | None = Field(
        default=None,
        description="Estimated effort: TRIVIAL, LOW, MEDIUM, HIGH."
    )

