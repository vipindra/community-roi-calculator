"""
Sample data generator for the Community ROI Calculator.

Generates realistic community data for a mid-sized creator:
- A fitness coach with ~200 active members
- Monthly subscription at $49, some annual plans at $399
- Mix of engagement levels (highly active core, dormant long-tail)
- Realistic churn patterns with reasons
- 12 months of revenue history

Run this once to populate the database before running the main CLI.
"""

import random
import os
from datetime import date, timedelta
from src.db import (
    initialize_database,
    insert_member,
    record_churn,
    log_engagement,
    upsert_monthly_snapshot,
)

SEED = 42
random.seed(SEED)

ACQUISITION_SOURCES = [
    "youtube", "instagram", "referral", "podcast", "email_list",
    "organic_search", "paid_ad", "twitter", "linkedin"
]

CHURN_REASONS = [
    "too_expensive", "not_enough_time", "content_not_relevant",
    "found_alternative", "achieved_goal", "technical_issues",
    "not_enough_community_interaction", None  # None = unknown reason
]

ENGAGEMENT_EVENT_TYPES = [
    "post_created", "comment_posted", "course_lesson_completed",
    "live_event_attended", "dm_sent", "resource_downloaded",
    "profile_updated", "reaction_given"
]

# Event weights — posts and comments are more valuable signals
EVENT_WEIGHTS = {
    "post_created": 3.0,
    "comment_posted": 2.0,
    "course_lesson_completed": 2.5,
    "live_event_attended": 4.0,
    "dm_sent": 1.5,
    "resource_downloaded": 1.0,
    "profile_updated": 0.5,
    "reaction_given": 0.5,
}


def generate_sample_data(db_path: str, verbose: bool = True) -> None:
    """
    Populate the database with 12 months of realistic community data.
    Designed to produce a community in healthy-but-imperfect shape
    to make the analysis outputs interesting and non-trivial.
    """
    initialize_database(db_path)

    today = date.today()
    start_date = date(today.year - 1, today.month, 1)

    if verbose:
        print("Generating sample community data...")
        print(f"Simulating 12 months from {start_date.strftime('%B %Y')}")

    active_member_ids = []
    all_time_members = []
    monthly_stats = []

    current_date = start_date

    for month_offset in range(12):
        month_start = date(current_date.year, current_date.month, 1)
        days_in_month = 28 if current_date.month == 2 else 30 if current_date.month in [4,6,9,11] else 31

        # New members this month (growing from ~8/month to ~18/month)
        new_count = random.randint(8 + month_offset, 14 + month_offset)
        new_this_month = []

        for _ in range(new_count):
            join_day = random.randint(1, days_in_month)
            join_date = month_start + timedelta(days=join_day - 1)
            plan = random.choices(["monthly", "annual"], weights=[0.75, 0.25])[0]
            source = random.choice(ACQUISITION_SOURCES)
            member_id = insert_member(join_date, plan, source, db_path)
            active_member_ids.append(member_id)
            all_time_members.append(member_id)
            new_this_month.append(member_id)

        # Churn: ~5.5% monthly churn rate, slightly higher for new members
        churned_this_month = []
        churn_candidates = active_member_ids.copy()

        for mid in churn_candidates:
            churn_probability = 0.04 if mid not in new_this_month else 0.10
            if random.random() < churn_probability:
                churn_day = random.randint(15, days_in_month)
                churn_date = month_start + timedelta(days=churn_day - 1)
                reason = random.choice(CHURN_REASONS)
                try:
                    record_churn(mid, churn_date, reason, db_path)
                    active_member_ids.remove(mid)
                    churned_this_month.append(mid)
                except Exception:
                    pass

        # Engagement events for active members
        for mid in active_member_ids:
            # Segment into active, moderate, dormant (realistic distribution)
            segment_roll = random.random()
            if segment_roll < 0.20:      # 20% highly active core
                num_events = random.randint(12, 30)
            elif segment_roll < 0.55:    # 35% moderate
                num_events = random.randint(3, 11)
            elif segment_roll < 0.80:    # 25% low engagement
                num_events = random.randint(1, 4)
            else:                        # 20% nearly dormant
                num_events = random.randint(0, 1)

            for _ in range(num_events):
                event_type = random.choice(ENGAGEMENT_EVENT_TYPES)
                event_day = random.randint(1, days_in_month)
                event_date = month_start + timedelta(days=event_day - 1)
                log_engagement(mid, event_type, event_date, EVENT_WEIGHTS[event_type], db_path)

        # Revenue calculation for this month
        monthly_members = len(active_member_ids)
        monthly_members_approx = monthly_members

        # Monthly subscribers pay $49, annual members pay $399/12 = $33.25/month
        monthly_subs = int(monthly_members_approx * 0.75)
        annual_subs = monthly_members_approx - monthly_subs
        subscription_rev = (monthly_subs * 49) + (annual_subs * 33.25)

        # Ancillary revenue grows slightly over time as trust builds
        course_rev = random.uniform(200, 600) * (1 + month_offset * 0.03)
        coaching_rev = random.uniform(300, 900) * (1 + month_offset * 0.05)
        sponsorship_rev = random.uniform(0, 400) if month_offset > 5 else 0.0
        platform_costs = 99.0  # flat monthly SaaS cost

        upsert_monthly_snapshot(
            snapshot_month=month_start,
            active_members=monthly_members,
            subscription_revenue=round(subscription_rev, 2),
            course_revenue=round(course_rev, 2),
            coaching_revenue=round(coaching_rev, 2),
            sponsorship_revenue=round(sponsorship_rev, 2),
            platform_costs=platform_costs,
            new_members=new_count,
            churned_members=len(churned_this_month),
            db_path=db_path
        )

        monthly_stats.append({
            "month": month_start.strftime("%b %Y"),
            "members": monthly_members,
            "new": new_count,
            "churned": len(churned_this_month),
            "net_rev": round(subscription_rev + course_rev + coaching_rev + sponsorship_rev - platform_costs, 2)
        })

        # Advance to next month
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)

    if verbose:
        print(f"\n{'Month':<12} {'Members':>8} {'New':>5} {'Churned':>8} {'Net Rev':>10}")
        print("-" * 48)
        for s in monthly_stats:
            print(f"{s['month']:<12} {s['members']:>8} {s['new']:>5} {s['churned']:>8} ${s['net_rev']:>9,.2f}")
        print(f"\nTotal active members: {len(active_member_ids)}")
        print(f"Total members ever: {len(all_time_members)}")
        print("Sample data generation complete.\n")
