from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    huggingface_api_token: str = ""
    hf_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    skills_file: Path = Path("skills.md")
    
    # CRM API Settings
    api_key: str = ""
    crm_base_url: str = "https://api.30apps.dev/api/v1"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Don't fail if .env file doesn't exist (common on Vercel)
        env_file_required = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def load_skills() -> str:
    """Load the skills.md file content."""
    settings = get_settings()
    skills_path = settings.skills_file
    
    if not skills_path.exists():
        return "You are a helpful assistant."
    
    return skills_path.read_text()

