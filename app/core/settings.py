from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    CLOUD_SQL_CONNECTION_NAME: str | None = None

    # GCP Core
    GCP_PROJECT_ID: str
    GCP_LOCATION: str = "us-central1"

    # GCP Pub/Sub Topics
    PUBSUB_TOPIC_INGESTION_REQUESTED: str = "ingestion-requested"
    PUBSUB_TOPIC_DATASET_RECEIVED: str = "dataset-received"
    PUBSUB_TOPIC_METADATA_EXTRACTED: str = "metadata-extracted"
    PUBSUB_TOPIC_METADATA_VECTORIZED: str = "metadata-vectorized"
    PUBSUB_TOPIC_TARGET_INFERRED: str = "target-inferred"
    PUBSUB_TOPIC_SCHEMA_VALIDATED: str = "schema-validated"
    PUBSUB_TOPIC_DRIFT_DETECTED: str = "drift-detected"
    PUBSUB_TOPIC_TARGET_MUTATED: str = "target-mutated"
    PUBSUB_TOPIC_FEEDBACK_SUBMITTED: str = "feedback-submitted"
    PUBSUB_TOPIC_JOB_COMPLETED: str = "job-completed"
    PUBSUB_TOPIC_JOB_FAILED: str = "job-failed"
    PUBSUB_TOPIC_FALLBACK_LANDING_CREATED: str = "fallback-landing-created"
    PUBSUB_TOPIC_FALLBACK_REQUESTED: str = "fallback-requested"
    PUBSUB_TOPIC_DEAD_LETTER: str = "job-failures-dead-letter-topic"
    PUBSUB_TOPIC_QUALITY_CHECK_REQUESTED: str = "quality-check-requested"
    PUBSUB_TOPIC_QUALITY_CHECK_COMPLETED: str = "quality-check-completed"

    # GCP Pub/Sub Subscriptions
    PUBSUB_SUBSCRIPTION_INGESTION_REQUESTED: str = "ingestion-requested-sub"
    PUBSUB_SUBSCRIPTION_DATASET_RECEIVED: str = "dataset-received-sub"
    PUBSUB_SUBSCRIPTION_METADATA_EXTRACTED: str = "metadata-extracted-sub"
    PUBSUB_SUBSCRIPTION_METADATA_VECTORIZED: str = "metadata-vectorized-sub"
    PUBSUB_SUBSCRIPTION_TARGET_INFERRED: str = "target-inferred-sub"
    PUBSUB_SUBSCRIPTION_SCHEMA_VALIDATED: str = "schema-validated-sub"
    PUBSUB_SUBSCRIPTION_DRIFT_DETECTED: str = "drift-detected-sub"
    PUBSUB_SUBSCRIPTION_TARGET_MUTATED: str = "target-mutated-sub"
    PUBSUB_SUBSCRIPTION_FEEDBACK_SUBMITTED: str = "feedback-submitted-sub"
    PUBSUB_SUBSCRIPTION_JOB_COMPLETED: str = "job-completed-sub"
    PUBSUB_SUBSCRIPTION_JOB_FAILED: str = "job-failed-sub"
    PUBSUB_SUBSCRIPTION_FALLBACK_LANDING_CREATED: str = "fallback-landing-created-sub"
    PUBSUB_SUBSCRIPTION_FALLBACK_REQUESTED: str = "fallback-requested-sub"
    PUBSUB_SUBSCRIPTION_DEAD_LETTER: str = "job-failures-dead-letter-sub"
    PUBSUB_SUBSCRIPTION_QUALITY_CHECK_REQUESTED: str = "quality-check-requested-sub"
    PUBSUB_SUBSCRIPTION_QUALITY_CHECK_COMPLETED: str = "quality-check-completed-sub"

    # Notification Subscriptions
    # (Leaving these default to None / fallback if not overridden)
    # But ensuring dead letter defaults to the expected subscriber name
    # instead of being required.
    # We will let these be string fields with their defaults.

    # Notification Channels (Slack & SMTP)
    SLACK_WEBHOOK_URL: str | None = None
    SLACK_WEBHOOK_NEW_TABLE: str | None = None
    SLACK_WEBHOOK_JOB_COMPLETED: str | None = None
    SLACK_WEBHOOK_JOB_FAILED: str | None = None
    SLACK_WEBHOOK_DEAD_LETTER: str | None = None
    SLACK_WEBHOOK_QUALITY_CHECK: str | None = None
    SMTP_HOST: str | None = None
    SMTP_PORT: int | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    NOTIFICATION_EMAIL_SENDER: str | None = None

    # Thresholds
    INFERENCE_CONFIDENCE_THRESHOLD: float = 0.70
    VALIDATION_WARNING_THRESHOLD: float = 1.0
    DRIFT_WARNING_THRESHOLD: float = 20.0
    DRIFT_CRITICAL_THRESHOLD: float = 50.0
    TARGET_INFERENCE_TOP_K: int = 7

    # Retry Thresholds
    RETRY_DELAY_INFRA_ERROR: int = 1800
    RETRY_DELAY_TRANSIENT_ERROR_1: int = 10
    RETRY_DELAY_TRANSIENT_ERROR_2: int = 30

    # Vertex AI
    LLM_PROVIDER: str = "vertex"
    VERTEX_EMBEDDING_MODEL: str = "text-embedding-004"
    VERTEX_GENERATIVE_MODEL: str = "gemini-2.5-flash-lite"

    # Dev mode
    DEV_MODE: bool = True

    # Agentic Pipeline
    ENABLE_AGENTIC_PIPELINE: bool = False

    @property
    def database_url(self) -> str:
        if self.CLOUD_SQL_CONNECTION_NAME:
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@/{self.DB_NAME}?host=/cloudsql/{self.CLOUD_SQL_CONNECTION_NAME}"
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(
        extra="ignore"
    )

settings = Settings()