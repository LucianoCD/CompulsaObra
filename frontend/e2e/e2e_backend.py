"""Servidor FastAPI aislado para pruebas E2E de Playwright (H-35)."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

E2E_DIR = Path(tempfile.gettempdir()) / "compulsa_e2e"
if E2E_DIR.exists():
    shutil.rmtree(E2E_DIR, ignore_errors=True)
E2E_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = E2E_DIR / "e2e_compulsa.db"
OUTBOX_PATH = E2E_DIR / "email_outbox.jsonl"

E2E_BACKEND_PORT = int(os.environ.get("E2E_BACKEND_PORT", "8001"))
E2E_FRONTEND_PORT = int(os.environ.get("E2E_FRONTEND_PORT", "5174"))

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
os.environ["REDIS_URL"] = ""
os.environ["SECRET_KEY"] = "e2e-playwright-secret-key-at-least-32-chars"
os.environ["HMAC_SHARE_SECRET"] = "e2e-playwright-hmac-secret-at-least-32-chars"
os.environ["COOKIE_SECURE"] = "false"
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "true"
os.environ["EMAIL_BACKEND"] = "file"
os.environ["EMAIL_FILE_SINK"] = OUTBOX_PATH.as_posix()
os.environ["EMAIL_RESEND_COOLDOWN_SECONDS"] = "1"
os.environ["FRONTEND_PUBLIC_URL"] = f"http://127.0.0.1:{E2E_FRONTEND_PORT}"
os.environ["CORS_ORIGINS"] = (
    f'["http://127.0.0.1:{E2E_FRONTEND_PORT}","http://localhost:{E2E_FRONTEND_PORT}"]'
)

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=E2E_BACKEND_PORT, log_level="warning")
