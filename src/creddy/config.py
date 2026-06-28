"""Application configuration, loaded from environment variables / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the MCP server and tooling.

    Values are read from environment variables prefixed with ``CREDDY_`` or
    from a local ``.env`` file (see ``.env.example``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CREDDY_",
        extra="ignore",
    )

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "creddy"
    db_user: str = "creddy"
    db_password: str = "creddy"
    # Managed Postgres (Neon/Supabase) require SSL: set to "require".
    db_sslmode: str = ""

    # Hard cap on the number of rows any single query may return.
    query_row_limit: int = 1000

    # TCMB EVDS (live Turkish central-bank data). Get a free key at evds3.tcmb.gov.tr.
    tcmb_api_key: str = ""
    # Documented public REST web service base (key-authenticated). TCMB is migrating
    # EVDS2 -> EVDS3; override this when the current public endpoint is published.
    tcmb_base_url: str = "https://evds2.tcmb.gov.tr/service/evds"
    # EVDS3 site, used by the live `tcmb_indicators` tool (no key required).
    tcmb_site_url: str = "https://evds3.tcmb.gov.tr"

    @property
    def dsn(self) -> str:
        """libpq connection string for psycopg."""
        parts = [
            f"host={self.db_host}",
            f"port={self.db_port}",
            f"dbname={self.db_name}",
            f"user={self.db_user}",
            f"password={self.db_password}",
        ]
        if self.db_sslmode:
            parts.append(f"sslmode={self.db_sslmode}")
        return " ".join(parts)
