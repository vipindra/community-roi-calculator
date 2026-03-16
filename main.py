#!/usr/bin/env python3
"""
Community ROI Calculator — CLI entry point.

Usage:
    python main.py                  # Run with sample data (auto-generated)
    python main.py --members 250    # Override current member count
    python main.py --reset          # Wipe the database and regenerate sample data
    python main.py --csv            # Also export a CSV report

This tool helps online community creators understand the real financial
value of their community, identify members at churn risk, and project
growth over the next 12 months.
"""

import argparse
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "community.db")


def main():
    parser = argparse.ArgumentParser(
        description="Community ROI Calculator — measure the real value of your community."
    )
    parser.add_argument("--members", type=int, default=None,
                        help="Override current active member count.")
    parser.add_argument("--reset", action="store_true",
                        help="Clear the database and regenerate sample data.")
    parser.add_argument("--csv", action="store_true",
                        help="Export results to a CSV file in /reports/.")
    parser.add_argument("--seed-only", action="store_true",
                        help="Just generate sample data without running the report.")
    args = parser.parse_args()

    # ── Database setup ─────────────────────────────────────────────────────
    if args.reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Database cleared.")

    if not os.path.exists(DB_PATH):
        print("No database found. Generating sample data...\n")
        from src.db import initialize_database
        from src.sample_data import generate_sample_data
        initialize_database(DB_PATH)
        generate_sample_data(DB_PATH, verbose=True)
    else:
        from src.db import initialize_database
        initialize_database(DB_PATH)

    if args.seed_only:
        print("Sample data ready. Run `python main.py` to see the report.")
        return

    # ── Community configuration ────────────────────────────────────────────
    # This represents the creator profile used in sample data:
    # A fitness coach community at $49/month with ~200 members
    from src.calculator import CommunityConfig
    config = CommunityConfig(
        monthly_subscription_price=49.0,
        annual_subscription_price=399.0,
        platform_fee_percent=0.04,           # Circle's approximate fee
        monthly_platform_cost=99.0,          # Circle Plus tier cost
        avg_monthly_churn_rate=0.055,        # 5.5% monthly churn
        avg_new_members_per_month=15,
        one_time_course_revenue=400.0,
        coaching_revenue_per_month=600.0,
        sponsorship_revenue_per_month=200.0,
        content_creation_hours_per_month=20.0,
        creator_hourly_rate=75.0,
    )

    # ── Current member count ───────────────────────────────────────────────
    from src.db import get_active_member_count
    current_members = args.members if args.members else get_active_member_count(DB_PATH)

    if current_members == 0:
        print("No active members found. Run with --reset to regenerate sample data.")
        sys.exit(1)

    # ── Run all calculations ───────────────────────────────────────────────
    from src.calculator import run_roi_calculation
    from src.analyze import score_community_health, segment_members_by_churn_risk, project_growth
    from src.report import print_full_report, export_csv_report

    roi = run_roi_calculation(config, current_members)
    health = score_community_health(DB_PATH, config, current_members)
    risk_segments = segment_members_by_churn_risk(DB_PATH)
    projection = project_growth(config, current_members, months_ahead=12)

    # ── Print report ───────────────────────────────────────────────────────
    print_full_report(config, roi, health, risk_segments, projection, current_members, DB_PATH)

    # ── Optional CSV export ────────────────────────────────────────────────
    if args.csv:
        filepath = export_csv_report(roi, health, projection, current_members, DB_PATH)
        print(f"  CSV report saved to: {filepath}\n")


if __name__ == "__main__":
    main()
