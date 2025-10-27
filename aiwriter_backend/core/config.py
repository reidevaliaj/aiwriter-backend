"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings."""
    
    # Database - Use SQLite for development if PostgreSQL not available
    DATABASE_URL: str = "sqlite:///./aiwriter.db"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_TEXT_MODEL: str = "gpt-5"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
    OPENAI_MAX_TOKENS_TEXT: int = 2200
    OPENAI_TEMPERATURE: float = 0.4
    OPENAI_TIMEOUT_S: int = 60
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    HMAC_SECRET: str = "your-hmac-secret-here"
    
    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    
    # PayPal
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # App settings
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"


settings = Settings()