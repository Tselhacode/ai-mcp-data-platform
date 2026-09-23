"""Application configuration via Pydantic Settings v2.

All runtime settings are loaded from environment variables.
No hard-coded credentials or environment-specific values.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the AI MCP Data Platform backend.

    All values come from environment variables (case-insensitive).
    See docs/architecture.md for variable descriptions.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/db.sqlite",
        description="SQLAlchemy async database URL",
    )

    # LLM provider
    llm_provider: str = Field(
        default="fake",
        description="LLM provider: 'bedrock' or 'fake'",
    )
    llm_model: str = Field(
        default="anthropic.claude-3-5-sonnet-20241022-v2:0",
        description="LLM model ID (used when provider=bedrock)",
    )
    llm_max_tokens: int = Field(
        default=4096,
        description="Max tokens per LLM response",
    )
    llm_max_iterations: int = Field(
        default=10,
        description="Max agent tool-calling loop iterations",
    )

    # AWS
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region for Bedrock",
    )

    # Observability
    log_level: str = Field(
        default="INFO",
        description="Python log level",
    )

    # MCP
    mcp_transport: str = Field(
        default="stdio",
        description="MCP transport: 'stdio' or 'sse'",
    )

    # API
    cors_origins: str = Field(
        default="http://localhost:5173",
        description="Comma-separated allowed CORS origins",
    )

    # LangSmith (optional observability — disabled by default)
    langsmith_tracing: bool = Field(
        default=False,
        description="Enable LangSmith tracing",
    )
    langsmith_api_key: str | None = Field(
        default=None,
        description="LangSmith API key (required only when tracing=true)",
    )
    langsmith_project: str = Field(
        default="ai-mcp-data-platform",
        description="LangSmith project namespace",
    )


def get_settings() -> Settings:
    """Return a Settings instance loaded from the environment."""
    return Settings()
