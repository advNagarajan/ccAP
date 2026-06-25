from pydantic import BaseModel, Field

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
