from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./geo.db"
    max_upload_mb: int = 50
    max_unzipped_mb: int = 300
    max_features: int = 100_000

    class Config:
        env_prefix = "GEO_"


settings = Settings()