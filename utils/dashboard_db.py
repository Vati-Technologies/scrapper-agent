import json
import psycopg2.extras
from utils.db import get_conn

DASHBOARD_CLIENT_ID = "dashboard"


# ── Leads ─────────────────────────────────────────────────────────────────────

def get_all_leads(status: str | None = None, score: str | None = None) -> list:
    filters, params = [], []
    if status:
        filters.append("status = %s")
        params.append(status)
    if score:
        filters.append("score = %s")
        params.append(score.upper())
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, business_name, score, status, notes, sent_at, updated_at,
                       phone, email, website, city, rating, category, praise, complaints, brief
                FROM leads_history
                {where}
                ORDER BY sent_at DESC, id DESC
                """,
                params,
            )
            return [dict(r) for r in cur.fetchall()]


def get_lead(lead_id: int) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, business_name, score, status, notes, sent_at, updated_at,
                       phone, email, website, city, rating, category, praise, complaints, brief
                FROM leads_history
                WHERE id = %s
                """,
                (lead_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def save_lead_brief(lead_id: int, brief: dict):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE leads_history
                SET brief = %s::jsonb, updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(brief), lead_id),
            )


def update_lead(lead_id: int, status: str | None, notes: str | None) -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE leads_history
                SET status     = COALESCE(%s, status),
                    notes      = COALESCE(%s, notes),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, business_name, score, status, notes, updated_at
                """,
                (status, notes, lead_id),
            )
            return dict(cur.fetchone())


# ── Dashboard scrape requests ─────────────────────────────────────────────────

def count_dashboard_scrapes_today() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM daily_requests
                WHERE client_id = %s AND request_date = CURRENT_DATE
                """,
                (DASHBOARD_CLIENT_ID,),
            )
            return cur.fetchone()[0]


def save_dashboard_request(industry: str, city: str) -> int:
    """Insert or overwrite today's dashboard scrape record — no daily limit enforced."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_requests (client_id, industry, city)
                VALUES (%s, %s, %s)
                ON CONFLICT (client_id, request_date)
                DO UPDATE SET industry    = EXCLUDED.industry,
                              city        = EXCLUDED.city,
                              status      = 'pending',
                              requested_at = NOW()
                RETURNING id
                """,
                (DASHBOARD_CLIENT_ID, industry, city),
            )
            return cur.fetchone()[0]


# ── Agency clients ─────────────────────────────────────────────────────────────

def get_agency_clients() -> list:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT ac.*,
                       COALESCE(
                           json_agg(cs ORDER BY cs.service_type)
                           FILTER (WHERE cs.id IS NOT NULL), '[]'
                       ) AS services
                FROM agency_clients ac
                LEFT JOIN client_services cs ON cs.agency_client_id = ac.id
                GROUP BY ac.id
                ORDER BY ac.created_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def create_agency_client(data: dict) -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO agency_clients
                    (name, contact_email, contact_phone, monthly_fee, payment_status, started_at, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    data["name"],
                    data.get("contact_email"),
                    data.get("contact_phone"),
                    data.get("monthly_fee"),
                    data.get("payment_status", "pending"),
                    data.get("started_at"),
                    data.get("notes"),
                ),
            )
            return dict(cur.fetchone())


def get_agency_client(client_id: int) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ac.*,
                       COALESCE(
                           json_agg(cs ORDER BY cs.service_type)
                           FILTER (WHERE cs.id IS NOT NULL), '[]'
                       ) AS services
                FROM agency_clients ac
                LEFT JOIN client_services cs ON cs.agency_client_id = ac.id
                WHERE ac.id = %s
                GROUP BY ac.id
                """,
                (client_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_agency_client(client_id: int, data: dict) -> dict:
    allowed = {"name", "contact_email", "contact_phone", "monthly_fee", "payment_status", "started_at", "notes"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return get_agency_client(client_id)
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [client_id]
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE agency_clients SET {set_clause} WHERE id = %s RETURNING *",
                values,
            )
            return dict(cur.fetchone())


def delete_agency_client(client_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM agency_clients WHERE id = %s", (client_id,))
            return cur.rowcount > 0


# ── Client services ────────────────────────────────────────────────────────────

def get_client_services(agency_client_id: int) -> list:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM client_services WHERE agency_client_id = %s ORDER BY service_type",
                (agency_client_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def upsert_client_service(agency_client_id: int, service_type: str, status: str) -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO client_services (agency_client_id, service_type, status, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (agency_client_id, service_type)
                DO UPDATE SET status = EXCLUDED.status, updated_at = NOW()
                RETURNING *
                """,
                (agency_client_id, service_type, status),
            )
            return dict(cur.fetchone())


# ── Analytics ──────────────────────────────────────────────────────────────────

def get_lead_funnel() -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS scraped,
                    COUNT(*) FILTER (WHERE status = 'contacted')  AS contacted,
                    COUNT(*) FILTER (WHERE status = 'converted')  AS converted,
                    COUNT(*) FILTER (WHERE status = 'skipped')    AS skipped
                FROM leads_history
            """)
            row = cur.fetchone()
            return {
                "scraped":   row[0],
                "contacted": row[1],
                "converted": row[2],
                "skipped":   row[3],
            }


def get_revenue_analytics() -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT name, monthly_fee, payment_status, started_at
                FROM agency_clients
                ORDER BY monthly_fee DESC NULLS LAST
            """)
            clients = [dict(r) for r in cur.fetchall()]
            total = sum(float(c["monthly_fee"] or 0) for c in clients)
            return {"clients": clients, "total_monthly": round(total, 2)}


def get_service_analytics() -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT service_type, status, COUNT(*) AS count
                FROM client_services
                GROUP BY service_type, status
                ORDER BY service_type, status
            """)
            result: dict = {}
            for service_type, status, count in cur.fetchall():
                result.setdefault(service_type, {})[status] = count
            return result


def get_home_summary() -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM leads_history WHERE sent_at = CURRENT_DATE) AS new_leads_today,
                    (SELECT COUNT(*) FROM agency_clients)                              AS active_clients,
                    (SELECT COALESCE(SUM(monthly_fee), 0) FROM agency_clients
                     WHERE payment_status = 'paid')                                   AS paid_monthly_revenue
            """)
            row = cur.fetchone()

            cur.execute("""
                SELECT business_name, status, updated_at
                FROM leads_history
                WHERE updated_at IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 5
            """)
            recent = [
                {"business_name": r[0], "status": r[1], "updated_at": r[2]}
                for r in cur.fetchall()
            ]

            return {
                "new_leads_today":       row[0],
                "active_clients":        row[1],
                "paid_monthly_revenue":  float(row[2]),
                "recent_activity":       recent,
            }
