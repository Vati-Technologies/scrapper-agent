# LeadGen Pro — System Design Document

**Version:** 1.0
**Date:** 2026-03-16
**Status:** Approved — Ready for Implementation

---

## 1. What Is Being Built

An AI-powered lead generation pipeline for marketing agencies. It scrapes businesses from Google, analyzes their reviews, scores them as sales opportunities, and delivers a formatted report to the client via WhatsApp — on demand, once per day.

---

## 2. Why It Exists

Marketing agency clients need fresh, pre-qualified business leads daily. This tool replaces hours of manual Google research with an automated pipeline that delivers actionable leads with review summaries and pitch angles directly to the salesperson's phone.

---

## 3. Who It Is For

Marketing agency salespeople who cold-call businesses to sell marketing services (websites, reputation management, social media, etc.)

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────┐
│                 Single Python Service            │
│                                                 │
│  ┌─────────────┐     ┌──────────────────────┐  │
│  │ WhatsApp    │     │   LangGraph Pipeline  │  │
│  │ Cloud API   │────▶│                       │  │
│  │             │     │  scrape → enrich →    │  │
│  │ (webhook)   │◀────│  dedup → analyze →    │  │
│  └─────────────┘     │  score → excel →      │  │
│                      │  deliver              │  │
│                      └──────────────────────┘  │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │         PostgreSQL (Neon - free tier)     │  │
│  │  clients | daily_requests | leads_history │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 5. Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Orchestration | LangGraph | State management, retries, parallel nodes |
| LLM | Google Gemini 1.5 Flash | Free tier (1M tokens/day) |
| Scraping | Serper.dev + Google Places API | Cheap search + structured business data |
| Excel | openpyxl | Formatted spreadsheet generation |
| Delivery | WhatsApp Cloud API (Meta) | Free (1000 conversations/month) |
| Database | PostgreSQL via Neon | Free tier, serverless, no maintenance |
| Language | Python 3.11+ | LangGraph native |
| Hosting | Single VPS or Railway | $5/month |

---

## 6. LangGraph Pipeline

### State

```python
class LeadGenState(TypedDict):
    client_id:              str
    industry:               str
    city:                   str
    raw_businesses:         list    # from Serper.dev
    enriched_businesses:    list    # + reviews from Places API
    new_businesses:         list    # deduped against DB
    analyzed_businesses:    list    # + Gemini summary + score
    excel_path:             str     # generated file path
    delivery_status:        str     # sent / failed
    errors:                 Annotated[list, add]
```

### Nodes

```
START
  │
  ▼
[scrape_node]       Serper.dev → search "[industry] in [city]" → 10-20 results
  │
  ▼
[enrich_node]       Google Places API → add reviews, rating, phone, website, address
  │
  ▼
[dedup_node]        Check leads_history → remove already-sent businesses
  │
  ▼
[analyze_node]      Gemini (parallel per business) → review summary + pitch angle
  │
  ▼
[score_node]        Gemini → HOT / WARM / SKIP classification
  │
  ▼
[excel_node]        openpyxl → formatted spreadsheet
  │
  ▼
[deliver_node]      WhatsApp → text summary (top HOT leads) + Excel attachment
  │
  ▼
END
```

---

## 7. Lead Scoring Model

### Signals (simplified — 3 signals only)

| Signal | HOT | WARM | SKIP |
|--------|-----|------|------|
| Online presence | No website | Basic website | Professional site |
| Review count | <10 reviews | 10-50 reviews | 50+ reviews |
| Star rating | 3.0–3.8★ | 3.9–4.2★ | >4.2★ or <3.0★ |

### Classification
- **HOT** — 2-3 signals present → call first
- **WARM** — 1 signal present → call second
- **SKIP** — 0 signals → excluded from report

Only HOT and WARM leads are included in the daily report.

### Gemini Prompt (per business)

```
Business: [name]
Rating: [X]★, [N] reviews
Website: [yes/no]
Reviews: [list]

1. Summarize in 1 sentence what customers consistently praise
2. Summarize in 1 sentence what customers consistently complain about
3. Write 1 sentence pitch angle for a marketing salesperson
4. Classify as HOT, WARM, or SKIP with one reason

Return JSON:
{
  "praise": "...",
  "complaints": "...",
  "pitch": "...",
  "score": "HOT",
  "reason": "..."
}
```
-TOON - Token Oriented Object Notation

---

## 8. WhatsApp Communication Flow

### Client Request Format

```
Industry: Plumbers
City: Cape Town
```

### System Responses

**Acknowledgement:**
```
✅ Got it! Searching for plumbers in Cape Town.
   Your report will be ready in ~2 minutes.
```

**Results:**
```
📊 LEAD REPORT — Plumbers, Cape Town
📅 16 March 2026 | 12 leads found | 6 HOT | 4 WARM

🔴 Joe's Plumbing — HOT LEAD
📍 Cape Town | ☎️ 021 555 1234
⭐ 3.2★ | 8 reviews | No website
✅ Praise: Fast response, friendly staff
❌ Complaints: Hard to reach, no follow-up
💡 Pitch: "Customers love your work but can't find or reach you online"

[top 5 HOT leads shown in message]
[full report attached as Excel]
```

**Already used daily request:**
```
⏳ You've already received your leads for today.
   Your next report is available tomorrow.
   Send your request any time after midnight.
```

**Wrong format:**
```
❌ Please send your request in this format:

Industry: Plumbers
City: Cape Town
```

**First time (onboarding):**
```
👋 Welcome to LeadGen Pro!

To get your daily leads, send:

Industry: [business type]
City: [city name]

You get 1 report per day.
Reports include 10-20 leads with review summaries.
```

---

## 9. Excel Output Structure

| Column | Content |
|--------|---------|
| Business Name | Joe's Plumbing |
| Phone | 021 555 1234 |
| Address | 12 Main Rd, Cape Town |
| Website | None |
| Rating | 3.2★ |
| Review Count | 8 |
| Lead Status | 🔴 HOT |
| Pitch Angle | One sentence |
| Review Summary — Positive | What customers love |
| Review Summary — Negative | What customers complain about |
| Raw Reviews | All reviews listed |

---

## 10. Database Schema (PostgreSQL / Neon)

```sql
CREATE TABLE clients (
    id                  TEXT PRIMARY KEY,
    name                TEXT,
    whatsapp_number     TEXT UNIQUE,
    active              BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE daily_requests (
    id              SERIAL PRIMARY KEY,
    client_id       TEXT REFERENCES clients(id),
    industry        TEXT,
    city            TEXT,
    status          TEXT DEFAULT 'pending',
    requested_at    TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    UNIQUE(client_id, DATE(requested_at))
);

CREATE TABLE leads_history (
    id              SERIAL PRIMARY KEY,
    client_id       TEXT REFERENCES clients(id),
    place_id        TEXT,
    business_name   TEXT,
    score           TEXT,
    sent_at         DATE DEFAULT CURRENT_DATE,
    UNIQUE(client_id, place_id)
);
```

---

## 11. Decision Log

| Decision | Choice | Alternatives Considered | Reason |
|----------|--------|------------------------|--------|
| Orchestration | LangGraph | n8n, Temporal | Native Python, handles parallel nodes, right complexity level |
| LLM | Gemini 1.5 Flash | Claude claude-sonnet-4-6, GPT-4o-mini | Free tier sufficient for scale |
| Scraping | Serper.dev + Places API | Playwright DIY, Apify, Outscraper | Cheapest reliable option with reviews |
| Delivery | WhatsApp Cloud API | Telegram, Email, Twilio | Clients already on WhatsApp, free tier |
| Trigger | Client-initiated (1/day) | Scheduled automatic | Client controls timing, simpler |
| Lead count | 10-20 per run | 50, 100 | Quality over quantity, lower cost |
| Scoring | HOT/WARM/SKIP (3 signals) | Complex weighted formula | Simpler = more actionable for salespeople |
| Database | PostgreSQL via Neon | SQLite | Free, scalable, production-grade |
| Architecture | Single service | Microservices | No unnecessary complexity at this stage |

---

## 12. Assumptions

- Clients are comfortable using WhatsApp as the primary interface
- English-language reviews (South African market initially)
- 10-20 leads/day provides sufficient value per client
- Google Places API returns adequate reviews for analysis
- Gemini free tier (15 req/min) is sufficient for parallel business analysis
- One VPS can handle multiple clients without performance issues

---

## 13. Non-Goals (This Version)

- No web UI for clients
- No custom scoring per client
- No CRM integration
- No multi-language support
- No automatic scheduled runs (client-triggered only)
- No SMS or email fallback delivery
