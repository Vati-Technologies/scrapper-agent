import httpx
from config import SERPER_API_KEY, MAX_BUSINESSES


def scrape_node(state: dict) -> dict:
    """Search Google Maps via Serper.dev and return raw business listings."""
    industry = state["industry"]
    city = state["city"]
    query = f"{industry} in {city}"

    results = _search_serper(query)
    return {"raw_businesses": results}


def _search_serper(query: str) -> list:
    url = "https://google.serper.dev/maps"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": MAX_BUSINESSES, "gl": "us"}

    response = httpx.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        print(f"❌ Serper API error: {data['error']}")
    print(f"🔍 Serper returned {len(data.get('places', []))} places for '{query}'")

    places = data.get("places", [])
    businesses = []
    for place in places:
        place_id = place.get("placeId", "")
        if not place_id:
            continue
        businesses.append({
            "name":         place.get("title", ""),
            "address":      place.get("address", ""),
            "rating":       place.get("rating"),
            "review_count": place.get("ratingCount", 0),
            "place_id":     place_id,
            "phone":        place.get("phoneNumber", ""),
            "website":      place.get("website", ""),
            "category":     place.get("category", ""),
        })

    return businesses
