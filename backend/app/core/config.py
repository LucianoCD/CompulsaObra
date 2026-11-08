"""Configuración centralizada y tipada con Pydantic Settings V2."""

from typing import List, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CompulsaObra"
    ENVIRONMENT: str = "development"
    
    # Persistencia Híbrida: SQLite por defecto para dev local y pytest; PostgreSQL en Docker/producción
    DATABASE_URL: str = Field(default="sqlite:///./compulsaobra.db")
    
    # Seguridad JWT y HMAC
    SECRET_KEY: str = Field(default="compulsa_super_secret_jwt_key_2026_noa")
    HMAC_SHARE_SECRET: str = Field(default="compulsa_hmac_share_secret_2026_noa")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas
    
    # Ingesta y Carga de Archivos
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    
    # Ingesta Multimodal (Google GenAI Gemini 2.5 Flash)
    GEMINI_API_KEY: str = Field(default="")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
    ])

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == "compulsa_super_secret_jwt_key_2026_noa":
                raise ValueError("En entorno de producción debe definirse una variable SECRET_KEY segura.")
            if self.HMAC_SHARE_SECRET == "compulsa_hmac_share_secret_2026_noa":
                raise ValueError("En entorno de producción debe definirse una variable HMAC_SHARE_SECRET segura.")
        return self

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
        return v if isinstance(v, list) else [str(v)]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
