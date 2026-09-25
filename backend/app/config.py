import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    APP_NAME: str = "Piemonte - Replanejamento Físico-Financeiro"
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1")
    
    # DATABASE_URL:
    # Local fallback: sqlite:///./replanejamento.db
    # VPS Postgres: postgresql+psycopg://username:password@localhost:5432/replanejamento_db
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{BASE_DIR}/replanejamento.db"
    )
    
    DEFAULT_CYCLE_START_DAY: int = int(os.getenv("DEFAULT_CYCLE_START_DAY", "21"))
    DEFAULT_CYCLE_END_DAY: int = int(os.getenv("DEFAULT_CYCLE_END_DAY", "20"))
    
    PIEMONTE_PATHS = [
        r"C:\Users\HomePC\Piemonte Construtora\Piemonte Engenharia - Planejamento",
        r"C:\Users\HomePC\OneDrive - Piemonte Construtora\PLANEJAMENTO PIEMONTE"
    ]

settings = Settings()
