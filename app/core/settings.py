from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Metadata DB
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    # GCP Core
    GCP_PROJECT_ID: str

    # GCP Pub/Sub
    PUBSUB_TOPIC_INGESTION_REQUESTED: str
    PUBSUB_TOPIC_DATASET_RECEIVED: str
    PUBSUB_TOPIC_METADATA_EXTRACTED: str
    PUBSUB_TOPIC_METADATA_VECTORIZED: str
    PUBSUB_TOPIC_TARGET_INFERRED: str
    PUBSUB_TOPIC_SCHEMA_VALIDATED: str
    PUBSUB_TOPIC_DRIFT_DETECTED: str
    PUBSUB_TOPIC_TARGET_MUTATED: str
    PUBSUB_TOPIC_FEEDBACK_SUBMITTED: str
    PUBSUB_TOPIC_JOB_COMPLETED: str
    PUBSUB_TOPIC_JOB_FAILED: str
    PUBSUB_TOPIC_FALLBACK_LANDING_CREATED: str
    PUBSUB_TOPIC_DEAD_LETTER: str = "job-failures-dead-letter-topic"

    RETRY_DELAY_INFRA_ERROR: int = 1800
    RETRY_DELAY_TRANSIENT_ERROR_1: int = 10
    RETRY_DELAY_TRANSIENT_ERROR_2: int = 30

    PUBSUB_SUBSCRIPTION_INGESTION_REQUESTED: str
    PUBSUB_SUBSCRIPTION_DATASET_RECEIVED: str
    PUBSUB_SUBSCRIPTION_METADATA_EXTRACTED: str
    PUBSUB_SUBSCRIPTION_METADATA_VECTORIZED: str
    PUBSUB_SUBSCRIPTION_TARGET_INFERRED: str
    PUBSUB_SUBSCRIPTION_SCHEMA_VALIDATED: str
    PUBSUB_SUBSCRIPTION_DRIFT_DETECTED: str    
    PUBSUB_SUBSCRIPTION_TARGET_MUTATED: str
    PUBSUB_SUBSCRIPTION_FEEDBACK_SUBMITTED: str

    # Notification Subscriptions
    PUBSUB_SUBSCRIPTION_JOB_COMPLETED: str | None = None
    PUBSUB_SUBSCRIPTION_JOB_FAILED: str | None = None
    PUBSUB_SUBSCRIPTION_FALLBACK_LANDING_CREATED: str | None = None
    PUBSUB_SUBSCRIPTION_DEAD_LETTER: str = "job-failures-dead-letter-sub"

    # Notification Channels (Slack & SMTP)
    SLACK_WEBHOOK_URL: str | None = None
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

    # Vertex AI
    GCP_LOCATION: str = "us-central1"
    LLM_PROVIDER: str = "vertex"
    VERTEX_EMBEDDING_MODEL: str | None = None
    VERTEX_GENERATIVE_MODEL: str | None = None

    model_config = SettingsConfigDict(
        extra="ignore"
    )


settings = Settings()