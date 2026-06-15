"""
A Pydantic schema model.
Used by the Inference Worker to enforce a structured JSON response from the LLM when selecting a target landing zone.
"""
from pydantic import BaseModel, Field

class InferenceResponseSchema(BaseModel):
    selected_target_id: str | None = Field(
        default=None,
        description="The UUID string of the selected target database table, or null if no candidate is sufficiently compatible."
    )
    confidence_score: float = Field(
        description="A value between 0.0 and 1.0 reflecting actual confidence in this selection."
    )
    reasoning: str = Field(
        description="Concise rationale for audit/debugging explaining choice, major schema/datatype compatibility concerns, or coverage gaps."
    )
    column_mapping: dict[str, str | None] | None = Field(
        default=None,
        description="Dictionary mapping each source column name to the matching target column name (or null if unmatched)."
    )
    unmapped_source_columns: list[str] = Field(
        default_factory=list,
        description="List of source column names that could not be mapped to any target column."
    )
    missing_target_columns: list[str] = Field(
        default_factory=list,
        description="List of target column names that are missing from the source dataset schema."
    )
    partitioning_recommendation: str | None = Field(
        default=None,
        description="Recommended column and strategy for partitioning the target table (e.g. partition by transaction_date MONTHLY), or null if not applicable."
    )
    naming_convention_suggestions: dict[str, str] | None = Field(
        default=None,
        description="Suggestions for renaming source columns to follow target naming conventions (e.g., lowercase snake_case for PostgreSQL)."
    )
