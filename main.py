import asyncio
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from concurrent.futures import ThreadPoolExecutor

from config import WHATSAPP_VERIFY_TOKEN, validate_config
from utils.db import run_migrations, get_client_by_whatsapp, create_client, has_used_daily_request, save_request
from utils.whatsapp import (
    parse_incoming,
    parse_lead_request,
    send_message,
    ONBOARDING_MSG,
    FORMAT_ERROR_MSG,
    DAILY_LIMIT_MSG,
    PROCESSING_MSG,
)
from pipeline import run_pipeline

app = FastAPI(title="LeadGen Pro")
executor = ThreadPoolExecutor(max_workers=4)


@app.on_event("startup")
async def startup():
    validate_config()
    run_migrations()
    print("🚀 LeadGen Pro is running.")


# ── WhatsApp webhook verification ─────────────────────────────────────────────

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    return Response(status_code=403)


# ── WhatsApp incoming messages ────────────────────────────────────────────────

@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()

    # Ignore status updates
    try:
        if "statuses" in body["entry"][0]["changes"][0]["value"]:
            return {"status": "ok"}
    except (KeyError, IndexError):
        pass

    msg = parse_incoming(body)
    if not msg:
        return {"status": "ok"}

    sender = msg["from"]
    text   = msg["text"]

    # ── Identify or create client ──────────────────────────────────────────
    client = get_client_by_whatsapp(sender)
    if not client:
        create_client(sender)
        send_message(sender, ONBOARDING_MSG)
        return {"status": "ok"}

    client_id = client["id"]

    # ── Check daily limit ──────────────────────────────────────────────────
    if has_used_daily_request(client_id):
        send_message(sender, DAILY_LIMIT_MSG)
        return {"status": "ok"}

    # ── Parse request ──────────────────────────────────────────────────────
    parsed = parse_lead_request(text)
    if not parsed:
        send_message(sender, FORMAT_ERROR_MSG)
        return {"status": "ok"}

    industry = parsed["industry"]
    city     = parsed["city"]
    star_min = parsed.get("star_min")
    star_max = parsed.get("star_max")

    # Build star label for acknowledgement message
    if star_min is not None and star_max is not None:
        stars_label = f" (⭐ {star_min:.0f}–{star_max:.0f} stars)"
    elif star_max is not None:
        stars_label = f" (⭐ up to {star_max:.0f} stars)"
    else:
        stars_label = ""

    # ── Save request + acknowledge ─────────────────────────────────────────
    request_id = save_request(client_id, industry, city)
    send_message(sender, PROCESSING_MSG.format(industry=industry, city=city, stars_label=stars_label))

    # ── Run pipeline in background (non-blocking) ──────────────────────────
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor,
        run_pipeline,
        client_id,
        sender,
        industry,
        city,
        request_id,
        star_min,
        star_max,
    )

    return {"status": "ok"}


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy"}
