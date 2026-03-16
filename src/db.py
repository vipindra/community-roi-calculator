"""
Database layer for the Community ROI Calculator.

Uses SQLite for simplicity and portability. No external database needed.
All tables are created on first run. This module handles:
  - Member records and activity tracking
  - Monthly revenue snapshots
  - Churn event logging
  - Aggregation queries used by the analysis layer
"""

import sqlite3
import os
from datetime import date, datetime
from typing import Optional


DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "community.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a connection with row_factory set so results come back as dicts."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Create all tables if they don't already exist.
    Safe to call repeatedly — uses CREATE TABLE IF NOT EXISTS throughout.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        -- Members: one row per member, tracks their full lifecycle
        CREATE TABLE IF NOT EXISTS members (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            joined_date     DATE NOT NULL,
            churned_date    DATE,
            plan_type       TEXT NOT NULL CHECK(plan_type IN ('monthly', 'annual', 'free')),
            acquisition_source TEXT,
            is_active       INTEGER NOT NULL DEFAULT 1
        );

        -- Revenue snapshots: monthly rollup of all revenue streams
        CREATE TABLE IF NOT EXISTS monthly_revenue (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_month          DATE NOT NULL UNIQUE,
            active_members          INTEGER NOT NULL,
            subscription_revenue    REAL NOT NULL DEFAULT 0,
            course_revenue          REAL NOT NULL DEFAULT 0,
            coaching_revenue        REAL NOT NULL DEFAULT 0,
            sponsorship_revenue     REAL NOT NULL DEFAULT 0,
            platform_costs          REAL NOT NULL DEFAULT 0,
            net_revenue             REAL NOT NULL DEFAULT 0,
            new_members             INTEGER NOT NULL DEFAULT 0,
            churned_members         INTEGER NOT NULL DEFAULT 0
        );

        -- Engagement events: member activity signals used for churn prediction
        CREATE TABLE IF NOT EXISTS engagement_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id       INTEGER NOT NULL REFERENCES members(id),
            event_date      DATE NOT NULL,
            event_type      TEXT NOT NULL,
            value           REAL DEFAULT 1.0
        );

        -- Churn log: why members left (when known)
        CREATE TABLE IF NOT EXISTS churn_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id       INTEGER NOT NULL REFERENCES members(id),
            churn_date      DATE NOT NULL,
            churn_reason    TEXT,
            plan_type       TEXT,
            months_active   INTEGER
        );

        -- Indexes for common query patterns
        CREATE INDEX IF NOT EXISTS idx_members_active ON members(is_active);
        CREATE INDEX IF NOT EXISTS idx_members_joined ON members(joined_date);
        CREATE INDEX IF NOT EXISTS idx_revenue_month ON monthly_revenue(snapshot_month);
        CREATE INDEX IF NOT EXISTS idx_engagement_member ON engagement_events(member_id);
        CREATE INDEX IF NOT EXISTS idx_engagement_date ON engagement_events(event_date);
    """)

    conn.commit()
    conn.close()


# ─── Write operations ────────────────────────────────────────────────────────

def insert_member(joined_date: date, plan_type: str,
                   acquisition_source: Optional[str] = None,
                   db_path: str = DEFAULT_DB_PATH) -> int:
    """Insert a new member and return their ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO members (joined_date, plan_type, acquisition_source) VALUES (?, ?, ?)",
        (joined_date.isoformat(), plan_type, acquisition_source)
    )
    member_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return member_id


def record_churn(member_id: int, churn_date: date,
                  churn_reason: Optional[str] = None,
                  db_path: str = DEFAULT_DB_PATH) -> None:
    """Mark a member as churned and log the event."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT joined_date, plan_type FROM members WHERE id = ?", (member_id,)
    )
    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Member ID {member_id} not found.")

    joined = date.fromisoformat(row["joined_date"])
    months_active = (churn_date.year - joined.year) * 12 + (churn_date.month - joined.month)

    cursor.execute(
        "UPDATE members SET churned_date = ?, is_active = 0 WHERE id = ?",
        (churn_date.isoformat(), member_id)
    )
    cursor.execute(
        """INSERT INTO churn_log (member_id, churn_date, churn_reason, plan_type, months_active)
           VALUES (?, ?, ?, ?, ?)""",
        (member_id, churn_date.isoformat(), churn_reason, row["plan_type"], months_active)
    )

    conn.commit()
    conn.close()


def log_engagement(member_id: int, event_type: str,
                    event_date: Optional[date] = None,
                    value: float = 1.0,
                    db_path: str = DEFAULT_DB_PATH) -> None:
    """Log an engagement event (post, comment, login, course completion, etc.)."""
    event_date = event_date or date.today()
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO engagement_events (member_id, event_date, event_type, value) VALUES (?, ?, ?, ?)",
        (member_id, event_date.isoformat(), event_type, value)
    )
    conn.commit()
    conn.close()


def upsert_monthly_snapshot(snapshot_month: date, active_members: int,
                              subscription_revenue: float, course_revenue: float,
                              coaching_revenue: float, sponsorship_revenue: float,
                              platform_costs: float, new_members: int,
                              churned_members: int,
                              db_path: str = DEFAULT_DB_PATH) -> None:
    """Insert or replace a monthly revenue snapshot."""
    net = (subscription_revenue + course_revenue + coaching_revenue +
           sponsorship_revenue - platform_costs)
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO monthly_revenue
               (snapshot_month, active_members, subscription_revenue, course_revenue,
                coaching_revenue, sponsorship_revenue, platform_costs, net_revenue,
                new_members, churned_members)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(snapshot_month) DO UPDATE SET
               active_members=excluded.active_members,
               subscription_revenue=excluded.subscription_revenue,
               course_revenue=excluded.course_revenue,
               coaching_revenue=excluded.coaching_revenue,
               sponsorship_revenue=excluded.sponsorship_revenue,
               platform_costs=excluded.platform_costs,
               net_revenue=excluded.net_revenue,
               new_members=excluded.new_members,
               churned_members=excluded.churned_members""",
        (snapshot_month.isoformat(), active_members, subscription_revenue,
         course_revenue, coaching_revenue, sponsorship_revenue, platform_costs,
         net, new_members, churned_members)
    )
    conn.commit()
    conn.close()


# ─── Read / aggregation queries ──────────────────────────────────────────────

def get_active_member_count(db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_connection(db_path)
    row = conn.execute("SELECT COUNT(*) AS cnt FROM members WHERE is_active = 1").fetchone()
    conn.close()
    return row["cnt"]


def get_revenue_trend(months: int = 12,
                       db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    """
    Return the last N months of revenue snapshots, oldest first.
    Each row includes net_revenue, active_members, and churn/growth signals.
    """
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT snapshot_month, active_members, subscription_revenue,
                  net_revenue, new_members, churned_members,
                  ROUND(CAST(churned_members AS REAL) / NULLIF(active_members + churned_members, 0) * 100, 2)
                      AS churn_rate_pct
           FROM monthly_revenue
           ORDER BY snapshot_month DESC
           LIMIT ?""",
        (months,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_churn_reasons_breakdown(db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    """Aggregate churn reasons to surface the top reasons members leave."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT churn_reason,
                  COUNT(*) AS total_churns,
                  ROUND(AVG(months_active), 1) AS avg_months_before_churn
           FROM churn_log
           WHERE churn_reason IS NOT NULL
           GROUP BY churn_reason
           ORDER BY total_churns DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_engagement_score_by_member(top_n: int = 20,
                                    db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    """
    Return top N members by total engagement score.
    High engagement scores correlate strongly with lower churn probability.
    """
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT m.id, m.joined_date, m.plan_type,
                  COALESCE(SUM(e.value), 0) AS engagement_score,
                  COUNT(e.id) AS total_events
           FROM members m
           LEFT JOIN engagement_events e ON e.member_id = m.id
           WHERE m.is_active = 1
           GROUP BY m.id
           ORDER BY engagement_score DESC
           LIMIT ?""",
        (top_n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_at_risk_members(low_engagement_threshold: float = 5.0,
                         db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    """
    Identify active members with very low engagement scores.
    These are churn risks — the CSM team should prioritize outreach to them.

    Threshold is total engagement score over the member's lifetime.
    """
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT m.id, m.joined_date, m.plan_type,
                  COALESCE(SUM(e.value), 0) AS engagement_score,
                  JULIANDAY('now') - JULIANDAY(m.joined_date) AS days_since_join
           FROM members m
           LEFT JOIN engagement_events e ON e.member_id = m.id
           WHERE m.is_active = 1
           GROUP BY m.id
           HAVING engagement_score <= ?
           ORDER BY days_since_join DESC""",
        (low_engagement_threshold,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plan_distribution(db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    """Break down active members by subscription plan type."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT plan_type,
                  COUNT(*) AS member_count,
                  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct_of_total
           FROM members
           WHERE is_active = 1
           GROUP BY plan_type
           ORDER BY member_count DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
