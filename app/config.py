from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    base_url: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"

settings = Settings()
