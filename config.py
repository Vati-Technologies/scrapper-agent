import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL")

MAX_BUSINESSES = int(os.getenv("MAX_BUSINESSES", 20))
MIN_BUSINESSES = int(os.getenv("MIN_BUSINESSES", 10))

# Validate required vars on startup
REQUIRED = [
    "GROQ_API_KEY",
    "SERPER_API_KEY",
    "GOOGLE_PLACES_API_KEY",
    "WHATSAPP_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_VERIFY_TOKEN",
    "DATABASE_URL",
]

def validate_config():
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
