"""Application configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SEED_DIR = DATA_DIR / "seed"
HISTORICAL_DIR = DATA_DIR / "historical"

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR}/worldcup.db")
DATABASE_URL_SYNC = os.getenv("DATABASE_URL_SYNC", f"sqlite:///{BASE_DIR}/worldcup.db")

# World Cup 2026
WORLD_CUP_START = "2026-06-11"
WORLD_CUP_END = "2026-07-19"
TOTAL_MATCHES = 104  # 48 teams → 104 matches total

# FIFA official API identifiers (World Cup 26™)
FIFA_COMPETITION_ID = os.getenv("FIFA_COMPETITION_ID", "17")
FIFA_SEASON_ID = os.getenv("FIFA_SEASON_ID", "285023")

# Elo config
ELO_K_FACTOR = float(os.getenv("ELO_K_FACTOR", "60"))
ELO_HOME_ADVANTAGE = float(os.getenv("ELO_HOME_ADVANTAGE", "60"))
ELO_HOST_BONUS_L1 = float(os.getenv("ELO_HOST_BONUS_L1", "100"))
ELO_HOST_BONUS_L2 = float(os.getenv("ELO_HOST_BONUS_L2", "50"))
ELO_HOST_BONUS_L3 = float(os.getenv("ELO_HOST_BONUS_L3", "30"))
LEAGUE_AVG_GOALS = float(os.getenv("LEAGUE_AVG_GOALS", "1.25"))

# Model ensemble weights (Elo + Poisson + ML)
ELO_WEIGHT = float(os.getenv("ELO_WEIGHT", "0.40"))
POISSON_WEIGHT = float(os.getenv("POISSON_WEIGHT", "0.35"))
ML_WEIGHT = float(os.getenv("ML_WEIGHT", "0.25"))

# Betting
INITIAL_BANKROLL = float(os.getenv("INITIAL_BANKROLL", "10000"))
MAX_STAKE_PCT = float(os.getenv("MAX_STAKE_PCT", "0.05"))
MAX_DAILY_STAKE_PCT = float(os.getenv("MAX_DAILY_STAKE_PCT", "0.20"))
MIN_ODDS = float(os.getenv("MIN_ODDS", "1.50"))
MAX_PARLAY = int(os.getenv("MAX_PARLAY", "4"))
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))
STOP_LOSS_STREAK = int(os.getenv("STOP_LOSS_STREAK", "3"))
STOP_LOSS_FRACTION = float(os.getenv("STOP_LOSS_FRACTION", "0.125"))

# Scraping
ODDS_UPDATE_INTERVAL = int(os.getenv("ODDS_UPDATE_INTERVAL", "300"))
SCORE_UPDATE_INTERVAL = int(os.getenv("SCORE_UPDATE_INTERVAL", "120"))
INJURY_UPDATE_INTERVAL = int(os.getenv("INJURY_UPDATE_INTERVAL", "7200"))
SQUAD_VALUE_UPDATE_INTERVAL = int(os.getenv("SQUAD_VALUE_UPDATE_INTERVAL", "86400"))

# Security (optional — leave empty for local dev without auth)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
RELOAD = os.getenv("RELOAD", "false").lower() in ("1", "true", "yes")

# APIs (set via env vars)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
