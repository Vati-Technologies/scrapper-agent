# Hosting Design — LeadGen Pro

## Understanding Summary

- **What:** Paid, production-quality deployment of LeadGen Pro for a real client
- **Why:** Always-on public HTTPS URL required for Meta to deliver inbound WhatsApp messages
- **Who:** South African client (POPIA applies); developer handles technical issues, client pays the bill
- **Key constraints:** Under $10/month, auto-deploy on git push, best-effort uptime, zero infrastructure management
- **Data sensitivity:** Business contact data (phones, addresses) stored in Neon — HTTPS mandatory, no personal data in logs, SOC 2 compliant platform satisfies POPIA cross-border transfer requirements
- **Already hosted:** PostgreSQL on Neon — no change needed
- **Non-goals:** High availability, multi-region, custom domain at launch, scaling beyond one client

## Assumptions

- Neon PostgreSQL stays as-is — no database migration needed
- A custom domain is not required at launch — Render's HTTPS URL works for Meta's webhook
- Brief downtime during redeploys (~30–60 seconds) is acceptable
- Secrets are set manually in the Render dashboard — never committed to git

## Decision Log

| Decision | Alternatives Considered | Reason Chosen |
|---|---|---|
| Render Starter ($7/month) | Railway ($5/month variable), Fly.io ($3/month + card required) | Flat predictable cost, one-line change from existing config, SOC 2 compliant, easiest for client to understand their bill |
| Keep Neon PostgreSQL | Migrate DB to Render | Already working, no downtime risk, free tier sufficient |
| Platform HTTPS URL | Custom domain | Not required at launch — Meta webhook works with any valid HTTPS URL |
| GitHub auto-deploy | Manual CLI deploy | Already designed this way, zero extra effort per release |

## Architecture

```
GitHub repo
    │
    │  git push → auto-deploy
    ▼
Render Starter ($7/month)
    │  builds from Dockerfile
    │  always-on (no sleep)
    │  public HTTPS URL
    │  env vars set in dashboard
    │  SOC 2 compliant
    │
    ├──▶ Neon PostgreSQL (already hosted, free tier)
    ├──▶ Serper.dev API
    ├──▶ Google Places API
    ├──▶ Google Gemini API
    └──▶ WhatsApp Cloud API (Meta)
```

## Cost Breakdown

| Service | Cost |
|---|---|
| Render Starter (web service) | $7/month |
| Neon PostgreSQL | Free tier |
| Serper.dev | Pay per use (outside this hosting plan) |
| Google Places API | Pay per use (outside this hosting plan) |
| Google Gemini API | Pay per use (outside this hosting plan) |
| **Total hosting** | **$7/month** |

## Environment Variables (set in Render dashboard)

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key |
| `SERPER_API_KEY` | Serper.dev API key |
| `GOOGLE_PLACES_API_KEY` | Google Places API key |
| `WHATSAPP_TOKEN` | WhatsApp Cloud API bearer token |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verify token (any secret string you choose) |
| `DATABASE_URL` | Neon PostgreSQL connection string |

## Security & Compliance

| Concern | Mitigation |
|---|---|
| POPIA (South Africa) | Render is SOC 2 certified — satisfies adequate protection for cross-border transfer |
| Secrets exposure | `.env` in `.gitignore`; all secrets set via Render dashboard, never in code |
| Transport security | HTTPS enforced by Render on all endpoints |
| Personal data in logs | `print()` statements log business names only — no phone numbers or addresses logged |
| Unauthorised webhook access | Meta verifies requests via `WHATSAPP_VERIFY_TOKEN` |
| Container security | Non-root user in Dockerfile; no secrets baked into image layers (.dockerignore) |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Brief downtime during redeploy | Render performs zero-downtime deploys on Starter plan where possible |
| API cost spikes (Serper, Places, Gemini) | 1-request-per-client-per-day limit enforced at DB level |
| DB connection failure | psycopg2 context manager rolls back and raises — pipeline error caught by main.py wrapper |

## Deployment Setup Steps

### 1. Push code to GitHub
Ensure your repository is up to date with all recent changes.

### 2. Create a Render account
Go to [render.com](https://render.com) → sign up (no credit card needed to start, card required for Starter plan billing).

### 3. Create a new Web Service
- Dashboard → **New** → **Web Service**
- Connect your GitHub repository
- Render detects `render.yaml` automatically — plan is pre-set to **Starter**
- Click **Create Web Service**

### 4. Set environment variables
In the Render dashboard → your service → **Environment**:
Add all 7 variables from the table above, copying values from your local `.env`.

### 5. Deploy
Render builds and deploys automatically. First deploy takes ~2–3 minutes.

### 6. Copy your public URL
Render assigns: `https://leadgen-pro.onrender.com` (or similar). Copy it.

### 7. Register the webhook with Meta
- Meta Developer dashboard → WhatsApp → **Configuration**
- Webhook URL: `https://your-app.onrender.com/webhook`
- Verify token: your `WHATSAPP_VERIFY_TOKEN` value
- Click **Verify and Save**

### 8. Test end-to-end
Send a WhatsApp message in the correct format:
```
Industry: Plumbers
City: Cape Town
```
You should receive the acknowledgement within a few seconds.

### Ongoing — every future update
```bash
git push origin main
```
Render redeploys automatically. No manual steps needed.
