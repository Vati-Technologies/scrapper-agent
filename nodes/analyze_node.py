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
    """Score each business and summarise its reviews with Groq/Llama."""
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


# ── Groq review summary ───────────────────────────────────────────────────────

def _analyze_business(business: dict) -> dict:
    score, reason, points = _calculate_score(business)

    reviews_with_text = [r for r in business.get("reviews", []) if r.get("text", "").strip()]

    if not reviews_with_text:
        print(f"ℹ️ No review text for '{business.get('name')}' — skipping summary.")
        return {
            **business,
            "summary": "No reviews available.",
            "score":   score,
            "reason":  reason,
            "points":  points,
        }

    review_text = "\n".join(
        f"- [{r['rating']}★] {r['text']}" for r in reviews_with_text
    )

    prompt = (
        f"Summarise these customer reviews for {business.get('name', 'this business')} "
        f"(rated {business.get('rating', 'N/A')}★) in 2-3 sentences. "
        f"Cover what customers consistently praise and what they complain about. "
        f"Be specific and factual. Write only the summary paragraph, no headers.\n\n"
        f"Reviews:\n{review_text}"
    )

    try:
        response = _get_client().chat.completions.create(
            model=_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
        print(f"✅ Summary for '{business.get('name')}': OK")
    except Exception as e:
        print(f"⚠️ Groq error for '{business.get('name')}': {type(e).__name__}: {e}")
        summary = "Unable to summarise reviews."

    return {
        **business,
        "summary": summary,
        "score":   score,
        "reason":  reason,
        "points":  points,
    }
