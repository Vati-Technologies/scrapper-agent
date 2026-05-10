# LeadGen Pro — Agency Dashboard Design

**Date:** 2026-05-03
**Status:** Validated — ready for implementation

---

## Understanding Summary

- **What:** A mobile-first web dashboard for a digital marketing agency owner to manage their entire business operation in one place 

2
- **Why:** The agency owner has no digital system — everything is manual. This becomes their single source of truth.
- **Who:** Single user — the agency owner only
- **Scope:** Lead pipeline, client management, service delivery tracking, analytics
- **Non-goals:** Client-facing portal, team management, external tool integrations, granular task/milestone tracking, multi-user roles

---

## Assumptions

- Single password + JWT cookie (7-day expiry) is sufficient auth for one user
- Hosted separately from FastAPI — Next.js on Vercel, backend stays on Render
- No native mobile app — responsive web app only
- Revenue figures are manually entered per client (no payment gateway)
- Analytics computed server-side, frontend renders numbers only
- Existing WhatsApp scraper flow remains unchanged

---

## Architecture

```
┌─────────────────────────────────┐
│   Next.js + Tailwind (Vercel)   │  ← Mobile-first web app
│   Dashboard Frontend            │
└────────────┬────────────────────┘
             │ HTTPS API calls
┌────────────▼────────────────────┐
│   FastAPI + uvicorn (Render)    │  ← Existing backend, extended
│   - WhatsApp webhook (existing) │
│   - Dashboard API (new routes)  │
│   - Scraper trigger (new route) │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│   PostgreSQL / Neon             │  ← Existing DB + 2 new tables
│   - clients (existing)          │
│   - leads_history (existing)    │
│   - agency_clients (new)        │
│   - client_services (new)       │
└─────────────────────────────────┘
```

**Deployments:**
- Frontend → Vercel (free tier, auto-deploys from GitHub)
- Backend → Render (already hosted)
- DB → Neon (already hosted)

---

## Pages & Navigation

Bottom navigation bar (one-thumb mobile use):

```
[Home]  [Leads]  [Clients]  [Services]  [Analytics]
```

### Home (Overview)
Daily briefing screen. Opens here by default.
- Today's lead run status (ran / not yet / in progress)
- Quick stats: new leads today, active clients count, monthly revenue snapshot
- "Run Leads" button — triggers new scrape from dashboard
- Recent activity feed — last 5 actions

### Leads
Full lead pipeline view.
- List: HOT / WARM badge, business name, status pill
- Status flow: `New → Contacted → Converted → Skipped`
- Tap → detail view: name, score, reviews, pitch angle, notes field
- Filter by status or score
- "Run Leads" trigger button

### Clients
Active paying clients.
- List: name, services active, payment status (Paid / Overdue / Pending)
- Tap → detail: contact info, start date, services, notes
- Add new client (manual entry form)

### Services
Delivery status grid.
- Rows: each client
- Columns: SEO / Website / Social Media
- Status pill: `Not Started / In Progress / Completed`
- Tap to update inline

### Analytics
- Lead funnel: Scraped → Contacted → Converted (bar chart)
- Revenue: monthly totals by client
- Services breakdown: clients per service + status

---

## Data Model

### Existing tables (read + extend)
```sql
-- Add to leads_history
ALTER TABLE leads_history
  ADD COLUMN status VARCHAR(20) DEFAULT 'new',
  ADD COLUMN notes TEXT,
  ADD COLUMN updated_at TIMESTAMPTZ;
```

### New tables
```sql
CREATE TABLE agency_clients (
  id             SERIAL PRIMARY KEY,
  name           VARCHAR(255) NOT NULL,
  contact_email  VARCHAR(255),
  contact_phone  VARCHAR(50),
  monthly_fee    NUMERIC(10,2),
  payment_status VARCHAR(20) DEFAULT 'pending',
  started_at     DATE,
  notes          TEXT,
  created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE client_services (
  id               SERIAL PRIMARY KEY,
  agency_client_id INTEGER REFERENCES agency_clients(id) ON DELETE CASCADE,
  service_type     VARCHAR(50),  -- seo / website / social_media
  status           VARCHAR(20) DEFAULT 'not_started',
  updated_at       TIMESTAMPTZ DEFAULT now(),
  UNIQUE(agency_client_id, service_type)
);
```

---

## API Endpoints

All routes under `/dashboard/*`, protected by JWT middleware.

### Auth
```
POST /dashboard/auth/login      -- validate password, return JWT cookie
POST /dashboard/auth/logout     -- clear cookie
```

### Leads
```
GET   /dashboard/leads               -- list all leads, filter by status/score
PATCH /dashboard/leads/{id}          -- update status + notes
POST  /dashboard/scrape              -- trigger LangGraph pipeline (background)
GET   /dashboard/scrape/status       -- check if run in progress
```

### Clients
```
GET    /dashboard/clients            -- list all agency clients
POST   /dashboard/clients            -- add new client
GET    /dashboard/clients/{id}       -- client detail
PATCH  /dashboard/clients/{id}       -- update client / payment status
DELETE /dashboard/clients/{id}       -- remove client
```

### Services
```
GET   /dashboard/clients/{id}/services            -- all service statuses for client
PATCH /dashboard/clients/{id}/services/{type}     -- update a service status
```

### Analytics
```
GET /dashboard/analytics/leads       -- funnel counts
GET /dashboard/analytics/revenue     -- monthly totals per client
GET /dashboard/analytics/services    -- clients per service + status breakdown
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| Scrape triggered while one running | Button disabled, "Run in progress..." shown |
| Pipeline fails | Stores failed status, dashboard shows "Last run failed" + timestamp |
| Lead status update fails | Optimistic UI rolls back, toast error shown |
| Client deleted with services | Cascade delete via FK constraint |
| No data (fresh install) | Empty state messages, no broken charts |
| JWT expired | Redirect to login, no data exposed |
| Mobile loses connection | Toast "Connection lost, please retry" |
| FastAPI unreachable | Error banner, last cached data shown where possible |

---

## Decision Log

| # | Decision | Alternatives | Why |
|---|----------|-------------|-----|
| 1 | Agency owner only (single user) | Multi-user, client portal | No team — zero auth complexity needed |
| 2 | Dashboard adds trigger; WhatsApp stays | Replace WhatsApp, dashboard-only | WhatsApp flow works; dashboard adds convenience |
| 3 | Scope: 4 areas only | Team mgmt, integrations | YAGNI — only what owner needs day one |
| 4 | Simple status per service | Milestones, task management | Visibility without overhead |
| 5 | Mobile-first web app | Desktop, native mobile | Owner on phone; browser = zero install |
| 6 | Next.js + Tailwind on Vercel | HTMX/FastAPI, SvelteKit | Best mobile-first DX, free hosting |
| 7 | Extend existing Neon DB | New DB, separate schema | Least disruption to existing pipeline |
| 8 | All API calls through FastAPI | Direct DB from frontend | DB credentials never in browser |
| 9 | Single password + JWT (7-day cookie) | OAuth, no auth | One user — complexity is waste |
| 10 | Analytics server-side | Client-side aggregation | Simpler frontend, one source of truth |
