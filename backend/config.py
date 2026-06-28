"""
Configuration management for the application.
Loads settings from environment variables with validation.
"""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Neo4j Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # LLM Configuration
    llm_provider: str = "openrouter"  # "openrouter" or "ollama"

    # OpenRouter Configuration
    openrouter_api_key: str = "PUT_YOUR_API_KEY_HERE"
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout: int = 120  # Request timeout in seconds
    openrouter_max_retries: int = 3  # Number of retry attempts

    # Ollama Configuration (fallback)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # Storage Paths
    data_dir: Path = Path("./data")
    upload_dir: Path = Path("./data/raw")
    processed_dir: Path = Path("./data/processed")

    # Extraction Settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_confidence: float = 0.7

    # Language Settings
    spacy_models: str = "fr_core_news_lg,en_core_web_lg"
    supported_languages: str = "fr,ar,en"

    # Logging
    log_level: str = "INFO"
    log_file: Path = Path("./logs/app.log")

    @property
    def spacy_models_list(self) -> List[str]:
        """Return list of spaCy models to load."""
        return [m.strip() for m in self.spacy_models.split(",")]

    @property
    def supported_languages_list(self) -> List[str]:
        """Return list of supported languages."""
        return [lang.strip() for lang in self.supported_languages.split(",")]

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(exist_ok=True)
        self.upload_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)
        self.log_file.parent.mkdir(exist_ok=True)


# Global settings instance
settings = Settings()
