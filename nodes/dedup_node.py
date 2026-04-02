from utils.db import get_sent_place_ids


def dedup_node(state: dict) -> dict:
    """Remove businesses already sent to this client, then filter by star range."""
    client_id = state["client_id"]
    enriched  = state["enriched_businesses"]
    star_min  = state.get("star_min")
    star_max  = state.get("star_max")

    sent_ids = get_sent_place_ids(client_id)
    new_businesses = [b for b in enriched if b.get("place_id") not in sent_ids]
    print(f"🔍 Dedup: {len(enriched)} total → {len(new_businesses)} new leads")

    if star_min is not None or star_max is not None:
        before = len(new_businesses)
        filtered = []
        for b in new_businesses:
            rating = b.get("rating")
            if rating is None:
                continue  # skip unrated businesses when a star filter is active
            if star_min is not None and rating < star_min:
                continue
            if star_max is not None and rating > star_max:
                continue
            filtered.append(b)
        label = f"{star_min or '?'}–{star_max or '?'}★"
        print(f"⭐ Star filter ({label}): {before} → {len(filtered)} leads")
        new_businesses = filtered

    return {"new_businesses": new_businesses}
