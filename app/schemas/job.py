from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class JobResponse(BaseModel):
    job_id: UUID
    source_id: UUID
    status: str
    current_stage: str | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    retry_count: int
    parent_job_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    job_type: str | None = "INGESTION"

    class Config:
        from_attributes = True


class StageHistoryResponse(BaseModel):
    stage_history_id: UUID
    job_id: UUID
    stage_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

    class Config:
        from_attributes = True


class ParentJobSummary(BaseModel):
    job_id: UUID
    status: str
    parent_job_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    stages: list[StageHistoryResponse] | None = None
    parent_job: Optional[ParentJobSummary] = None

    class Config:
        from_attributes = True


class TargetCatalogSummary(BaseModel):
    target_id: UUID
    target_name: str
    target_type: str
    schema_definition: dict | list | None = None

    class Config:
        from_attributes = True


class LandingInferenceSummary(BaseModel):
    inference_id: UUID
    confidence_score: float
    column_mapping: dict | list | None = None
    unmapped_source_columns: list[str] | None = None
    missing_target_columns: list[str] | None = None
    partitioning_recommendation: str | None = None
    reasoning: str
    requires_review: bool
    created_at: datetime | None = None
    matched_target_table: str | None = None
    matched_target_id: UUID | None = None

    class Config:
        from_attributes = True


class SchemaValidationSummary(BaseModel):
    validation_id: UUID
    validation_status: str
    coverage_percentage: float
    target_match_percentage: float
    mapped_column_count: int
    source_column_count: int
    target_column_count: int
    report_json: dict | list | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class SchemaDriftSummary(BaseModel):
    drift_id: UUID
    drift_status: str
    drift_score: float
    drift_summary: dict | list | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class SchemaRecommendationSummary(BaseModel):
    recommendation_id: UUID
    recommendation_status: str
    deterministic_findings: dict | list | None = None
    recommendations_list: dict | list | None = None
    partitioning_recommendation: str | None = None
    explanation: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class SchemaFallbackSummary(BaseModel):
    request_id: UUID
    request_reason: str
    request_status: str
    backup_table_name: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None
    review_notes: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class DataQualityReportSummary(BaseModel):
    report_id: UUID
    job_id: UUID
    status: str
    rules_executed: int
    rules_failed: int
    report_json: dict
    created_at: datetime

    class Config:
        from_attributes = True


class ArtifactLineageDetails(BaseModel):
    artifact_id: UUID
    source_id: UUID
    external_artifact_id: str
    artifact_name: str
    status: str
    processed_at: datetime | None = None
    discovered_at: datetime | None = None
    failure_reason: str | None = None
    artifact_metadata: dict | list | None = None
    inference: LandingInferenceSummary | None = None
    validation: SchemaValidationSummary | None = None
    drift: SchemaDriftSummary | None = None
    recommendation: SchemaRecommendationSummary | None = None
    fallback: SchemaFallbackSummary | None = None
    target: TargetCatalogSummary | None = None
    data_quality: DataQualityReportSummary | None = None

    class Config:
        from_attributes = True


class JobDetailsResponse(BaseModel):
    job: JobResponse
    stages: list[StageHistoryResponse]
    parent_job: ParentJobSummary | None = None
    artifacts: list[ArtifactLineageDetails]
    source_schema: dict | list | None = None
    target_schema: dict | list | None = None

    class Config:
        from_attributes = True


# Rebuild recursive typing model references
ParentJobSummary.model_rebuild()