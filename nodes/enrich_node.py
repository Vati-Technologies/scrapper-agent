import re
import httpx
import googlemaps
from config import GOOGLE_PLACES_API_KEY

# Lazy-initialised so tests can import this module without a real API key
_gmaps_client = None

SOCIAL_DOMAINS = ["facebook.com", "instagram.com", "twitter.com", "tiktok.com", "x.com"]

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_EMAIL_NOISE = {"example", "test", "placeholder", "sentry", "wixpress", "schema", "yourdomain", "domain"}


def _get_gmaps():
    global _gmaps_client
    if _gmaps_client is None:
        _gmaps_client = googlemaps.Client(key=GOOGLE_PLACES_API_KEY)
    return _gmaps_client


def enrich_node(state: dict) -> dict:
    """Enrich each business with reviews and details from Google Places API."""
    raw_businesses = state["raw_businesses"]
    enriched = []

    for business in raw_businesses:
        place_id = business.get("place_id")
        if not place_id:
            enriched.append(business)
            continue

        details = _get_place_details(place_id)
        enriched.append({**business, **details})

    return {"enriched_businesses": enriched}


def _get_place_details(place_id: str) -> dict:
    # Serper sometimes returns a numeric CID instead of the ChIJ... format.
    # The Legacy Places API only accepts the ChIJ... format.
    if not place_id.startswith("ChIJ"):
        print(f"⚠️ Skipping place_id '{place_id}' — not a valid Google Place ID (must start with ChIJ). "
              f"Serper may have returned a CID instead.")
        return {"reviews": [], "photo_count": 0, "missing_social": False}

    try:
        result = _get_gmaps().place(
            place_id=place_id,
            fields=[
                "name",
                "formatted_phone_number",
                "website",
                "rating",
                "user_ratings_total",
                "reviews",
                "opening_hours",
                "type",
                "photo",
            ],
            language="en",
        )
        place    = result.get("result", {})
        reviews  = place.get("reviews", [])
        types    = place.get("types", [])
        photos   = place.get("photos", [])
        category = types[0].replace("_", " ").title() if types else ""
        website  = place.get("website", "")

        if not reviews:
            print(f"ℹ️ No reviews returned by Google Places API for {place_id}. "
                  f"API status: {result.get('status')}. "
                  f"Full result keys: {list(place.keys())}")

        missing_social, email = _get_website_info(website)

        return {
            "phone":          place.get("formatted_phone_number", ""),
            "email":          email,
            "website":        website,
            "rating":         place.get("rating"),
            "review_count":   place.get("user_ratings_total", 0),
            "category":       category,
            "photo_count":    len(photos),
            "missing_social": missing_social,
            "reviews": [
                {
                    "author": r.get("author_name", ""),
                    "rating": r.get("rating"),
                    "text":   r.get("text", ""),
                    "time":   r.get("relative_time_description", ""),
                }
                for r in reviews
            ],
        }
    except Exception as e:
        print(f"❌ Google Places API error for place_id '{place_id}': {type(e).__name__}: {e}")
        return {"reviews": [], "photo_count": 0, "missing_social": False, "email": None}


def _get_website_info(website: str) -> tuple[bool, str | None]:
    """Fetch website once — return (missing_social, email_or_None)."""
    if not website:
        return False, None
    try:
        response = httpx.get(website, timeout=10, follow_redirects=True)
        html_lower = response.text.lower()
        missing_social = sum(1 for d in SOCIAL_DOMAINS if d in html_lower) == 0
        candidates = _EMAIL_RE.findall(response.text)
        email = next(
            (e for e in candidates if not any(noise in e.lower() for noise in _EMAIL_NOISE)),
            None,
        )
        return missing_social, email
    except Exception:
        return False, None
