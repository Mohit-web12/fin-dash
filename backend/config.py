# config.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{BASE_DIR / 'finance.db'}"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 1 day

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Trade lifecycle engine. Called server-to-server only — the engine has no auth of
    # its own, so it stays private and SpendGauge's JWT guards access to it.
    #
    # Empty by default, meaning "no engine connected". The engine runs locally and is not
    # reachable from the public deploy, and defaulting to localhost:8000 made the deployed
    # API call ITSELF (it binds 8000 too), returning 404 for a route it doesn't have.
    # Unset means Investments serves its own data instead of surfacing an error.
    engine_base_url: str = ""

    @property
    def engine_configured(self) -> bool:
        return bool(self.engine_base_url.strip())

    seed_user_email: str = "demo@example.com"
    seed_user_password: str = "password"

    # Refill the demo account's history on boot when it's empty. Render's free
    # plan wipes the SQLite file on deploy, which would otherwise leave the
    # public demo showing empty gauges. Set false for a real deployment.
    seed_demo_data: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
