from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

DATABASE_PATH = DATA_DIR / "database.db"

RSS_FEEDS = [
    "https://techcrunch.com/category/fintech/feed/",
    "https://www.finextra.com/rss/headlines.aspx",
    "https://www.paymentsdive.com/feeds/news/"
]

COMPETITOR_BLACKLIST_PATH = DATA_DIR / "competitor_blacklist.txt"

BRAND_IDENTITY_PATH = DATA_DIR / "brand_identity.txt"

COMPLIANCE_SIMILARITY_THRESHOLD = 0.35

DAILY_POST_BUDGET = 20

# [DIDACTIC_LIMITATION] Defaulting to Gemini mock mode and key to allow the pipeline to run out of the box without requiring real external API keys.
GEMINI_MOCK_MODE = True
GEMINI_API_KEY = "MOCK"


