"""
A Pydantic schema model.
Used by the Recommendation Service to enforce a structured JSON response from the LLM when generating recommendations.
"""
from pydantic import BaseModel, Field


class RecommendationOp(BaseModel):
    sequence_order: int = Field(
        description="The 1-based index ordering of the recommendation execution sequence."
    )
    action_type: str = Field(
        description="Type of recommendation, e.g., 'ADD_COLUMN', 'REMOVE_COLUMN', 'RENAME_COLUMN', 'MODIFY_TYPE', 'ADD_NULLABLE_HANDLING', 'CREATE_PARTITION'."
    )
    target: str = Field(
        description="Whether the recommendation applies to the 'source' dataset ingestion pipeline or the 'target' catalog storage schema."
    )
    column_name: str = Field(
        description="The affected column/field name."
    )
    new_column_name: str | None = Field(
        default=None,
        description="The new column name if action_type is RENAME_COLUMN."
    )
    data_type: str | None = Field(
        default=None,
        description="The target data type if action_type is ADD_COLUMN or MODIFY_TYPE."
    )
    priority: str = Field(
        description="Priority level: HIGH, MEDIUM, or LOW."
    )
    reason: str = Field(
        description="Concise reasoning for why this remediation action is recommended."
    )
    suggested_action: str = Field(
        description="Specific implementation instructions (e.g., exact SQL DDL ALTER TABLE command for Relational, or schema transformation rules for NoSQL)."
    )
    confidence_score: float = Field(
        description="A value between 0.0 and 1.0 reflecting confidence in this recommendation.",
        ge=0.0,
        le=1.0
    )


class SchemaRecommendationOutput(BaseModel):
    recommendations: list[RecommendationOp] = Field(
        description="Sequenced list of recommended actions. Must be empty if no action/remediation is required."
    )
    explanation: str = Field(
        description="Overall summary or explanation of the remediation plan. If no action is required, this explains why."
    )
