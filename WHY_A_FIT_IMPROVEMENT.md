# Why They're a Fit — Improvement Design

## Understanding Summary

- **What:** Redesign the `why_a_fit` section of the business brief from generic consulting language into a structured, sales-ready output
- **Why:** Current output is vague and could apply to any business — not useful before a sales call
- **Who:** Agency staff using the dashboard to prepare before calling a lead
- **Format:** Service-led bullets (only where data supports) + punchy closing paragraph with optional "Lead with" recommendation
- **Constraints:** LLM reasons about services from raw data — no hardcoded mappings; services list lives in `config.py` as `AGENCY_SERVICES`
- **Non-goals:** No hardcoded signal→service logic, no database-driven service list, no confidence scores

## Assumptions

1. `AGENCY_SERVICES` in `config.py` is a simple dict of service name → one-line description
2. Change is limited to `config.py`, `utils/brief.py`, and `leads/page.tsx`
3. `why_a_fit` remains a single string field — no schema changes
4. "Lead with" line is omitted by the LLM when data is not strong enough

## Decision Log

| # | Decision | Alternatives Considered | Why |
|---|----------|------------------------|-----|
| 1 | All three: bullets + paragraph + optional lead | Bullets only, pitch angle only, numbers only | Most complete and sales-ready |
| 2 | Only recommend services data actually supports | Always recommend all three | Prevents manufactured recommendations |
| 3 | LLM reasons about services from raw data | Hardcoded signal mappings, DB-driven | Future-proof as services grow |
| 4 | `AGENCY_SERVICES` dict in `config.py` | Hardcoded in prompt, pulled from DB | Easy to extend; separate from prompt logic |
| 5 | "Lead with" only when data strongly supports it | Always give a lead, confidence-flagged | Honest over confident |
| 6 | Bullets + paragraph as one combined string | Separate JSON fields, structured array | No schema changes; whitespace-pre-line handles layout |
| 7 | `whitespace-pre-line` div for `why_a_fit` only | Parse bullets client-side | Zero parsing logic |

## Implementation

### 1. `config.py` — Add `AGENCY_SERVICES`

```python
AGENCY_SERVICES = {
    "SEO": "Improve Google search ranking, local map visibility, and review volume",
    "Website": "Build or redesign the business website for credibility and conversions",
    "Social Media": "Manage Instagram, Facebook and other channels to grow online presence",
}
```

### 2. `utils/brief.py` — Inject services into prompt

Import `AGENCY_SERVICES` and replace the `why_a_fit` prompt instruction with the two-part structure.

### 3. `leads/page.tsx` — `whitespace-pre-line` on `why_a_fit`

Switch `why_a_fit` from `<p>` to a `whitespace-pre-line` div so bullets and line breaks render correctly.
