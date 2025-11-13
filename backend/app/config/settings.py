# app/config/settings.py

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded automatically from .env or environment."""

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/soar_db",
        description="PostgreSQL connection URL",
    )
    google_client_secret_file: str = Field(
        default="client_secret.json",
        description="Path to Google OAuth client secret JSON file",
    )
    gmail_sync_folder: str = Field(
        default="INBOX",
        description="Gmail folder label to read when syncing",
    )
    gmail_max_results: int = Field(
        default=25,
        ge=1,
        le=500,
        description="Maximum number of emails to fetch per sync",
    )
    token_directory: str = Field(
        default="token files",
        description="Directory for cached Google OAuth tokens",
    )
    model_artifact_path: Path = Field(
        default=Path("artifacts/phishing_model.joblib"),
        description="Location of phishing ML model artifact",
    )
    vectorizer_artifact_path: Path = Field(
        default=Path("artifacts/phishing_vectorizer.joblib"),
        description="Location of persisted TF-IDF vectorizer",
    )
    training_data_path: Path = Field(
        default=Path("data/data.csv"),
        description="Default CSV dataset for training the phishing detector",
    )

    # Enable `.env` loading automatically
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Cached instance for app-wide reuse
settings = Settings()