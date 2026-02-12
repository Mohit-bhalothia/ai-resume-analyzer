from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI Resume Analyzer & Job Matcher"
    environment: str = "development"

    # Security
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Database
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/ai_resume_analyzer"

    # File storage
    upload_dir: str = "uploads"

    # NLP / models
    spacy_model: str = "en_core_web_sm"
    sentence_transformer_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

