from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    GCP_PROJECT_ID: str

    PUBSUB_TOPIC_INGESTION_REQUESTED: str
    PUBSUB_TOPIC_DATASET_RECEIVED: str
    PUBSUB_TOPIC_METADATA_EXTRACTED: str
    PUBSUB_TOPIC_JOB_COMPLETED: str
    PUBSUB_TOPIC_JOB_FAILED: str

    PUBSUB_SUBSCRIPTION_INGESTION_REQUESTED: str
    PUBSUB_SUBSCRIPTION_DATASET_RECEIVED: str

    PUBSUB_TOPIC_TARGET_MUTATED: str
    PUBSUB_TOPIC_FEEDBACK_SUBMITTED: str
    PUBSUB_SUBSCRIPTION_TARGET_MUTATED: str
    PUBSUB_SUBSCRIPTION_FEEDBACK_SUBMITTED: str

    PUBSUB_SUBSCRIPTION_METADATA_EXTRACTED: str
    PUBSUB_TOPIC_METADATA_VECTORIZED: str
    PUBSUB_SUBSCRIPTION_METADATA_VECTORIZED: str

    GEMINI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        extra="ignore"
    )


settings = Settings()