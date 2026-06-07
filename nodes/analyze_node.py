import re
import json
import threading
import concurrent.futures
from groq import Groq
from config import GROQ_API_KEY

_MODEL_NAME = "llama-3.3-70b-versatile"
_local = threading.local()


def _get_client():
    """Return a thread-local Groq client so threads don't share one instance."""
    if not hasattr(_local, "client"):
        _local.client = Groq(api_key=GROQ_API_KEY)
    return _local.client


def analyze_node(state: dict) -> dict:
    """Score each business and summarise its reviews with Gemini."""
    businesses = state["new_businesses"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(_analyze_business, businesses))

    hot  = sum(1 for b in results if b.get("score") == "HOT")
    warm = sum(1 for b in results if b.get("score") == "WARM")
    print(f"✅ Analysis: {len(results)} businesses → {hot} HOT, {warm} WARM")
    return {"analyzed_businesses": results}


# ── Deterministic scoring ─────────────────────────────────────────────────────

def _calculate_score(business: dict) -> tuple[str, str, int]:
    points = 0
    reasons = []

    if not business.get("website"):
        points += 2
        reasons.append("no website")

    rating = business.get("rating")
    if rating is not None:
        if rating < 3.0:
            points += 2
            reasons.append(f"low rating ({rating}★)")
        elif rating <= 4.0:
            points += 1
            reasons.append(f"below-average rating ({rating}★)")

    reviews = business.get("reviews", [])
    if reviews:
        negative = sum(1 for r in reviews if (r.get("rating") or 5) <= 2)
        if negative / len(reviews) > 0.20:
            points += 1
            reasons.append(f"{negative}/{len(reviews)} negative reviews")

    if business.get("website") and business.get("missing_social"):
        points += 1
        reasons.append("no social media links on website")

    if business.get("photo_count", 0) <= 2:
        points += 1
        reasons.append(f"only {business.get('photo_count', 0)} photos")

    score  = "HOT" if points >= 3 else "WARM"
    reason = "Signals: " + ", ".join(reasons) if reasons else "No strong weakness signals."
    return score, reason, points


# ── JSON parsing ──────────────────────────────────────────────────────────────

def _parse_json_response(text: str) -> dict | None:
    """Parse a JSON response, stripping markdown code fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


# ── Gemini review summary ─────────────────────────────────────────────────────

def _analyze_business(business: dict) -> dict:
    score, reason, points = _calculate_score(business)

    reviews_with_text = [r for r in business.get("reviews", []) if r.get("text", "").strip()]

    if not reviews_with_text:
        print(f"ℹ️ No review text for '{business.get('name')}' — skipping summary.")
        return {
            **business,
            "praise":     "No reviews available.",
            "complaints": "No reviews available.",
            "score":      score,
            "reason":     reason,
            "points":     points,
        }

    review_text = "\n".join(
        f"- [{r['rating']}★] {r['text']}" for r in reviews_with_text
    )

    prompt = (
        f"Analyse these customer reviews for {business.get('name', 'this business')} "
        f"(rated {business.get('rating', 'N/A')}★).\n\n"
        f"Respond with this exact JSON structure — all values must be quoted strings:\n"
        f'{{ "praise": "...", "complaints": "..." }}\n\n'
        f"  praise:     1-2 sentences on what customers consistently praise.\n"
        f"  complaints: 1-2 sentences on what customers consistently complain about.\n"
        f"Output valid JSON only. No markdown, no extra keys.\n\n"
        f"Reviews:\n{review_text}"
    )

    praise     = "Unable to analyze reviews."
    complaints = "Unable to analyze reviews."

    try:
        response = _get_client().chat.completions.create(
            model=_MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a JSON API. Respond only with valid, parseable JSON. Every string value must be enclosed in double quotes."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        parsed = _parse_json_response(response.choices[0].message.content)
        if parsed and "praise" in parsed and "complaints" in parsed:
            praise     = parsed["praise"]
            complaints = parsed["complaints"]
            print(f"✅ Analysis for '{business.get('name')}': OK")
        else:
            print(f"⚠️ Unexpected Groq response for '{business.get('name')}': {response.choices[0].message.content[:100]}")
    except Exception as e:
        print(f"⚠️ Groq error for '{business.get('name')}': {type(e).__name__}: {e}")

    return {
        **business,
        "praise":     praise,
        "complaints": complaints,
        "score":      score,
        "reason":     reason,
        "points":     points,
    }
