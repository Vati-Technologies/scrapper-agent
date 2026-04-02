from utils.whatsapp import send_message, send_document
from utils.db import save_leads, mark_request_complete
from datetime import date


def deliver_node(state: dict) -> dict:
    """Send WhatsApp summary + Excel attachment to client."""
    businesses  = state["analyzed_businesses"]
    excel_path  = state["excel_path"]
    client_id   = state["client_id"]
    whatsapp_no = state["whatsapp_number"]
    request_id  = state["request_id"]
    industry    = state["industry"]
    city        = state["city"]

    hot_leads  = [b for b in businesses if b.get("score") == "HOT"]
    warm_leads = [b for b in businesses if b.get("score") == "WARM"]
    total      = len(businesses)

    # ── Build summary message ─────────────────────────────────────────────
    summary = _build_summary(industry, city, hot_leads, warm_leads, total)
    send_message(whatsapp_no, summary)

    # ── Send Excel attachment ─────────────────────────────────────────────
    send_document(
        whatsapp_no,
        excel_path,
        caption=f"📎 Full lead report — {industry.title()} in {city.title()} | {date.today().strftime('%d %B %Y')}",
    )

    # ── Persist to DB ─────────────────────────────────────────────────────
    save_leads(client_id, businesses)
    mark_request_complete(request_id)

    print(f"✅ Delivered {total} leads to {whatsapp_no}")
    return {"delivery_status": "sent"}


def _build_summary(industry: str, city: str, hot: list, warm: list, total: int) -> str:
    today = date.today().strftime("%d %B %Y")
    lines = [
        f"📊 *LEAD REPORT — {industry.upper()} IN {city.upper()}*",
        f"📅 {today}",
        "",
        f"✅ *{total} leads generated*",
        f"🔴 HOT: {len(hot)}",
        f"🟡 WARM: {len(warm)}",
        "",
        "📎 Full report attached below.",
    ]
    return "\n".join(lines)
