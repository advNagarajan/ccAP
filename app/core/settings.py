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

    model_config = SettingsConfigDict(
        extra="ignore"
    )


settings = Settings()