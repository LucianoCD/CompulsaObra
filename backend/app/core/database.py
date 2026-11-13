"""Engine SQLAlchemy 2.0, SessionLocal y Base Declarativa."""

import os
import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from alembic.config import Config
from alembic import command
from app.core.config import settings

logger = logging.getLogger(__name__)

# Conexión transparente híbrida: SQLite o PostgreSQL
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Generador de sesión de base de datos para inyección FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Ejecuta migraciones Alembic hasta 'head' al iniciar el servicio (CO-13 / H-20).

    En producción no se permite continuar si las migraciones fallan.
    """
    is_production = settings.ENVIRONMENT.lower() == "production"
    if ":memory:" in settings.DATABASE_URL:
        if is_production:
            raise RuntimeError("No se permite base de datos :memory: en producción.")
        Base.metadata.create_all(bind=engine)
        return

    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    if os.path.exists(alembic_ini_path):
        try:
            alembic_cfg = Config(alembic_ini_path)
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            command.upgrade(alembic_cfg, "head")
            logger.info("Migraciones Alembic aplicadas exitosamente.")
            return
        except Exception as e:
            if is_production:
                logger.critical(f"Fallo crítico al aplicar migraciones Alembic en producción: {e}")
                raise
            logger.warning(f"Aviso al ejecutar migraciones Alembic en {settings.ENVIRONMENT}: {e}. Aplicando Base.metadata.create_all.")
    elif is_production:
        raise FileNotFoundError(f"No se encontró alembic.ini requerido en producción: {alembic_ini_path}")

    Base.metadata.create_all(bind=engine)
