# LeadGen Pro

AI-powered lead generation pipeline for marketing agencies.

## What It Does

1. Client sends a WhatsApp message: `Industry: Plumbers\nCity: Cape Town`
2. System scrapes 10–20 businesses from Google
3. Gemini AI analyzes reviews → generates pitch angles + HOT/WARM/SKIP scores
4. Exports a formatted Excel report
5. Sends summary + Excel to client via WhatsApp

One request per client per day. No duplicates ever resent.

---

## Setup

### 1. Clone & install

```bash
git clone <repo>
cd leadgen-pro
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in all values in .env
```

**Required API keys:**

| Key | Where to get it |
|-----|----------------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) — free |
| `SERPER_API_KEY` | [serper.dev](https://serper.dev) — free tier available |
| `GOOGLE_PLACES_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) |
| `WHATSAPP_TOKEN` | Meta for Developers → WhatsApp → API Setup |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta for Developers → WhatsApp → API Setup |
| `WHATSAPP_VERIFY_TOKEN` | Any random string you choose |
| `DATABASE_URL` | [neon.tech](https://neon.tech) — free tier |

### 3. Run locally

```bash
uvicorn main:app --reload --port 8000
```

### 4. Expose webhook (for local dev)

```bash
# Install ngrok, then:
ngrok http 8000
# Copy the https URL → paste into Meta WhatsApp webhook config
```

### 5. Configure WhatsApp webhook

In Meta for Developers:
- Webhook URL: `https://your-domain.com/webhook`
- Verify token: same as `WHATSAPP_VERIFY_TOKEN` in `.env`
- Subscribe to: `messages`

---

## Deploy (Docker)

```bash
docker build -t leadgen-pro .
docker run -d --env-file .env -p 8000:8000 leadgen-pro
```

---

## Project Structure

```
├── main.py              # FastAPI app + WhatsApp webhook
├── pipeline.py          # LangGraph pipeline
├── config.py            # Environment config
├── nodes/
│   ├── scrape_node.py   # Serper.dev Google search
│   ├── enrich_node.py   # Google Places API (reviews)
│   ├── dedup_node.py    # Remove already-sent leads
│   ├── analyze_node.py  # Gemini AI review analysis
│   ├── excel_node.py    # Excel report generation
│   └── deliver_node.py  # WhatsApp delivery
├── utils/
│   ├── db.py            # PostgreSQL helpers
│   └── whatsapp.py      # WhatsApp Cloud API helpers
└── output/              # Generated Excel files
```

---

## Client WhatsApp Format

```
Industry: Plumbers
City: Cape Town
```

One request per day. Results arrive in ~2 minutes.
