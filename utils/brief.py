import re
import json
import httpx
from groq import Groq
from config import GROQ_API_KEY, SERPER_API_KEY, AGENCY_SERVICES

_MODEL_NAME = "llama-3.3-70b-versatile"
_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def generate_brief(lead: dict) -> dict:
    """
    Build a business brief for a lead using website content, Serper search,
    and existing pipeline data (praise, complaints, rating).

    Returns a dict with keys: about, pain_points, why_a_fit, data_flags.
    """
    data_flags = []

    website_text = _fetch_website(lead.get("website"), data_flags)
    search_text  = _serper_search(lead.get("business_name", ""), lead.get("city", ""), data_flags)

    return _generate_with_gemini(lead, website_text, search_text, data_flags)


# ── Step 1: fetch website ─────────────────────────────────────────────────────

def _fetch_website(url: str | None, data_flags: list) -> str | None:
    if not url:
        data_flags.append("website_not_found")
        return None
    try:
        response = httpx.get(url, timeout=5, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; LeadGenBot/1.0)"
        })
        response.raise_for_status()
        text = _strip_html(response.text)
        return text[:2000] if text else None
    except Exception:
        data_flags.append("website_not_found")
        return None


def _strip_html(html: str) -> str:
    text = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── Step 2: Serper web search ─────────────────────────────────────────────────

def _serper_search(business_name: str, city: str, data_flags: list) -> str | None:
    if not business_name:
        data_flags.append("search_unavailable")
        return None
    city_str = city.strip() if city else ""
    query = f"{business_name} {city_str} South Africa".strip()
    try:
        response = httpx.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": 5, "gl": "za", "hl": "en"},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        snippets = []

        # Answer box (Google AI Overview / featured snippet)
        ab = data.get("answerBox", {})
        if ab.get("answer"):
            snippets.append(ab["answer"])
        if ab.get("snippet"):
            snippets.append(ab["snippet"])

        # Knowledge graph description + attributes
        kg = data.get("knowledgeGraph", {})
        if kg.get("description"):
            snippets.append(kg["description"])
        for attr in kg.get("attributes", {}).values():
            snippets.append(str(attr))

        # Organic results — all snippets for this business
        for result in data.get("organic", [])[:4]:
            snippet = result.get("snippet", "")
            # Only include if it mentions the business name (avoids wrong matches)
            if snippet and business_name.split()[0].lower() in snippet.lower():
                snippets.append(snippet)

        return " ".join(snippets).strip() if snippets else None
    except Exception:
        data_flags.append("search_unavailable")
        return None


# ── Step 3: Gemini generation ─────────────────────────────────────────────────

def _generate_with_gemini(
    lead: dict,
    website_text: str | None,
    search_text: str | None,
    data_flags: list,
) -> dict:
    name       = lead.get("business_name", "this business")
    category   = lead.get("category", "")
    rating     = lead.get("rating")
    score      = lead.get("score", "")
    praise     = lead.get("praise", "")
    complaints = lead.get("complaints", "")

    sections = [f"Business: {name}"]
    if category:
        sections.append(f"Category: {category}")
    if rating:
        sections.append(f"Rating: {rating}★")
    if score:
        sections.append(f"Lead score: {score}")
    if praise and praise != "No reviews available.":
        sections.append(f"What customers praise: {praise}")
    if complaints and complaints != "No reviews available.":
        sections.append(f"What customers complain about: {complaints}")
    if website_text:
        sections.append(f"Website content (excerpt): {website_text}")
    if search_text:
        sections.append(f"Public search snippets: {search_text}")

    context = "\n".join(sections)

    services_block = "\n".join(
        f"- {name}: {desc}" for name, desc in AGENCY_SERVICES.items()
    )

    prompt = (
        f"Based ONLY on the information below, write a business brief.\n"
        f"Do NOT invent facts not supported by the data.\n\n"
        f"DATA:\n{context}\n\n"
        f"Respond with this exact JSON structure — all values must be quoted strings:\n"
        f'{{"about": "...", "pain_points": "...", "why_a_fit": "..."}}\n\n'
        f"  about:       2-3 sentences. Who they are, what they do, their positioning.\n"
        f"  pain_points: 2-3 sentences. Visible weaknesses based strictly on the data above.\n"
        f"  why_a_fit:   Two parts combined as one string:\n"
        f"    PART 1 — Service bullets: For each service listed below, check if the data\n"
        f"    provides specific evidence this business needs it. If yes, write one bullet:\n"
        f"    '• [Service]: [one specific reason grounded in the data].'\n"
        f"    If the data does NOT support a service, omit it entirely. Do not recommend\n"
        f"    a service just because it sounds reasonable — only include it if the data\n"
        f"    specifically supports it.\n"
        f"    PART 2 — Closing paragraph: 2-3 punchy sentences naming the biggest gap.\n"
        f"    Only if one service is clearly the strongest entry point based on the data,\n"
        f"    end with: 'Lead with: [Service] — [one-line reason why].'\n"
        f"    If the data is not strong enough to recommend a lead service, omit that line.\n\n"
        f"SERVICES THIS AGENCY OFFERS:\n{services_block}\n\n"
        f"Output valid JSON only. No explanation, no markdown."
    )

    fallback = {
        "about":       f"{name} is a {category or 'local business'} with limited public information available.",
        "pain_points": "Insufficient data to identify specific pain points.",
        "why_a_fit":   "A marketing agency could help strengthen their online presence.",
        "data_flags":  data_flags + ["gemini_error"],
    }

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
        if parsed and all(k in parsed for k in ("about", "pain_points", "why_a_fit")):
            parsed["data_flags"] = data_flags
            return parsed
    except Exception as e:
        print(f"⚠️ Brief generation failed for '{name}': {type(e).__name__}: {e}")

    return fallback


def _parse_json_response(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
