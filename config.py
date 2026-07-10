from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

DATABASE_PATH = DATA_DIR / "database.db"

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=fintech",
    "https://news.google.com/rss/search?q=open+banking",
    "https://news.google.com/rss/search?q=embedded+finance",
    "https://news.google.com/rss/search?q=digital+payments"
]