from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://signal_user:signal_pass@localhost:5432/signal_analysis"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    aws_region: str = "eu-central-1"
    aws_s3_bucket: str = ""
    anomaly_window_seconds: float = 10.0
    z_score_threshold: float = 3.0
    battery_temp_threshold: float = 80.0
    generator_version: str = "1.0.0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
