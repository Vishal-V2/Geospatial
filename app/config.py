from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEO_")

    database_url: str = "sqlite:///./geo.db"
    max_upload_mb: int = 50
    max_unzipped_mb: int = 300
    max_features: int = 100_000


settings = Settings()