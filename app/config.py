from functools import lru_cache
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from environment variables or .env file."""

    neo4j_uri: Annotated[str, Field(description="Neo4j database connection URI")] = (
        "bolt://localhost:7687"
    )
    neo4j_user: Annotated[str, Field(description="Neo4j database username")] = "neo4j"
    neo4j_password: Annotated[str, Field(description="Neo4j database password")] = (
        "password"
    )
    log_level: Annotated[str, Field(description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")] = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Retrieve application settings (cached singleton)."""
    return Settings()
