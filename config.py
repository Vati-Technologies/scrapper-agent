import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL")

MAX_BUSINESSES = int(os.getenv("MAX_BUSINESSES", 20))
MIN_BUSINESSES = int(os.getenv("MIN_BUSINESSES", 10))

# Services the agency offers — add new services here as the business grows
AGENCY_SERVICES = {
    "SEO": "Improve Google search ranking, local map visibility, and review volume",
    "Website": "Build or redesign the business website for credibility and conversions",
    "Social Media": "Manage Instagram, Facebook and other channels to grow online presence",
}

CORS_ORIGINS               = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
DASHBOARD_API_KEY          = os.getenv("DASHBOARD_API_KEY")
DASHBOARD_DAILY_SCRAPE_LIMIT = int(os.getenv("DASHBOARD_DAILY_SCRAPE_LIMIT", 3))

# Validate required vars on startup
REQUIRED = [
    "GROQ_API_KEY",
    "SERPER_API_KEY",
    "GOOGLE_PLACES_API_KEY",
    "WHATSAPP_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_VERIFY_TOKEN",
    "DATABASE_URL",
    "DASHBOARD_API_KEY",
]

def validate_config():
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
