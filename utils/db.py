import uuid
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from config import DATABASE_URL


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_migrations():
    """Create all tables if they don't exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── Core WhatsApp tables ──────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id                  TEXT PRIMARY KEY,
                    name                TEXT,
                    whatsapp_number     TEXT UNIQUE NOT NULL,
                    active              BOOLEAN DEFAULT true,
                    created_at          TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS daily_requests (
                    id              SERIAL PRIMARY KEY,
                    client_id       TEXT REFERENCES clients(id),
                    industry        TEXT NOT NULL,
                    city            TEXT NOT NULL,
                    status          TEXT DEFAULT 'pending',
                    request_date    DATE NOT NULL DEFAULT CURRENT_DATE,
                    requested_at    TIMESTAMPTZ DEFAULT NOW(),
                    completed_at    TIMESTAMPTZ,
                    UNIQUE(client_id, request_date)
                );

                CREATE TABLE IF NOT EXISTS leads_history (
                    id              SERIAL PRIMARY KEY,
                    client_id       TEXT REFERENCES clients(id),
                    place_id        TEXT NOT NULL,
                    business_name   TEXT,
                    score           TEXT,
                    sent_at         DATE DEFAULT CURRENT_DATE,
                    UNIQUE(client_id, place_id)
                );
            """)

            # ── Dashboard extensions to leads_history ─────────────────────────
            cur.execute("""
                ALTER TABLE leads_history
                    ADD COLUMN IF NOT EXISTS status     VARCHAR(20) DEFAULT 'new',
                    ADD COLUMN IF NOT EXISTS notes      TEXT,
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ,
                    ADD COLUMN IF NOT EXISTS phone      VARCHAR(50),
                    ADD COLUMN IF NOT EXISTS email      VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS website    TEXT,
                    ADD COLUMN IF NOT EXISTS city       TEXT,
                    ADD COLUMN IF NOT EXISTS rating     NUMERIC(3,1),
                    ADD COLUMN IF NOT EXISTS category   TEXT,
                    ADD COLUMN IF NOT EXISTS praise     TEXT,
                    ADD COLUMN IF NOT EXISTS complaints TEXT,
                    ADD COLUMN IF NOT EXISTS brief      JSONB;
            """)

            # ── Dashboard tables ──────────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agency_clients (
                    id             SERIAL PRIMARY KEY,
                    name           VARCHAR(255) NOT NULL,
                    contact_email  VARCHAR(255),
                    contact_phone  VARCHAR(50),
                    monthly_fee    NUMERIC(10,2),
                    payment_status VARCHAR(20) DEFAULT 'pending',
                    started_at     DATE,
                    notes          TEXT,
                    created_at     TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS client_services (
                    id               SERIAL PRIMARY KEY,
                    agency_client_id INTEGER REFERENCES agency_clients(id) ON DELETE CASCADE,
                    service_type     VARCHAR(50),
                    status           VARCHAR(20) DEFAULT 'not_started',
                    updated_at       TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(agency_client_id, service_type)
                );
            """)

            # ── Seed dashboard system client ──────────────────────────────────
            cur.execute("""
                INSERT INTO clients (id, name, whatsapp_number)
                VALUES ('dashboard', 'Dashboard', 'dashboard')
                ON CONFLICT DO NOTHING;
            """)

    print("✅ Database migrations complete.")


# ── Client helpers ──────────────────────────────────────────────────────────

def get_client_by_whatsapp(whatsapp_number: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM clients WHERE whatsapp_number = %s AND active = true",
                (whatsapp_number,)
            )
            return cur.fetchone()


def create_client(whatsapp_number: str, name: str = None) -> dict:
    client_id = str(uuid.uuid4())[:8]
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO clients (id, name, whatsapp_number)
                VALUES (%s, %s, %s)
                ON CONFLICT (whatsapp_number) DO UPDATE SET active = true
                RETURNING *
                """,
                (client_id, name or whatsapp_number, whatsapp_number)
            )
            return cur.fetchone()


# ── Daily request helpers ────────────────────────────────────────────────────

def has_used_daily_request(client_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM daily_requests
                WHERE client_id = %s AND request_date = CURRENT_DATE
                """,
                (client_id,)
            )
            return cur.fetchone() is not None


def save_request(client_id: str, industry: str, city: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_requests (client_id, industry, city)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (client_id, industry, city)
            )
            return cur.fetchone()[0]


def mark_request_complete(request_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE daily_requests
                SET status = 'completed', completed_at = NOW()
                WHERE id = %s
                """,
                (request_id,)
            )


def mark_request_failed(request_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE daily_requests SET status = 'failed' WHERE id = %s",
                (request_id,)
            )


# ── Leads history helpers ────────────────────────────────────────────────────

def get_sent_place_ids(client_id: str) -> set:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT place_id FROM leads_history WHERE client_id = %s",
                (client_id,)
            )
            return {row[0] for row in cur.fetchall()}


def save_leads(client_id: str, businesses: list, city: str | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            for b in businesses:
                cur.execute(
                    """
                    INSERT INTO leads_history
                        (client_id, place_id, business_name, score, phone, email,
                         website, city, rating, category, praise, complaints)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (client_id, place_id) DO NOTHING
                    """,
                    (
                        client_id,
                        b["place_id"],
                        b["name"],
                        b.get("score", "UNKNOWN"),
                        b.get("phone") or None,
                        b.get("email") or None,
                        b.get("website") or None,
                        city or None,
                        b.get("rating"),
                        b.get("category") or None,
                        b.get("praise") or None,
                        b.get("complaints") or None,
                    )
                )
