"""
Report generator for the Community ROI Calculator.

Produces two outputs:
1. A clean, readable terminal report with all key metrics
2. A CSV file in /reports/ for further analysis in Excel or Sheets

The terminal output is designed to be the kind of thing a creator
would actually want to screenshot and share.
"""

import csv
import os
from datetime import datetime
from src.calculator import CommunityConfig, ROIResult
from src.analyze import HealthScore, ChurnRiskSegment, GrowthProjection
from src.db import (
    get_revenue_trend,
    get_churn_reasons_breakdown,
    get_plan_distribution,
)


REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")


def _fmt_currency(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def _bar(value: float, max_value: float = 100, width: int = 20, char: str = "█") -> str:
    """ASCII progress bar."""
    filled = int((value / max(max_value, 1)) * width)
    return char * filled + "░" * (width - filled)


def print_full_report(
    config: CommunityConfig,
    roi: ROIResult,
    health: HealthScore,
    risk_segments: list[ChurnRiskSegment],
    projection: GrowthProjection,
    current_members: int,
    db_path: str
) -> None:
    """Print a complete ROI report to the terminal."""

    W = 62  # report width
    divider = "─" * W
    thick = "═" * W

    def header(text: str) -> None:
        print(f"\n  ◆ {text.upper()}")
        print(f"  {divider}")

    def row(label: str, value: str, indent: int = 4) -> None:
        dots = "." * max(1, W - indent - len(label) - len(value) - 2)
        print(f"  {' ' * indent}{label} {dots} {value}")

    print(f"\n  {'═' * W}")
    print(f"  {'COMMUNITY ROI REPORT':^{W}}")
    print(f"  {datetime.now().strftime('%B %d, %Y'):^{W}}")
    print(f"  {'═' * W}")

    # ── Health Score ──────────────────────────────────────────────────────────
    header("Community Health Score")
    grade_color = {"A": "✅", "B": "🟢", "C": "🟡", "D": "🟠", "F": "🔴"}.get(health.grade, "")
    print(f"    Overall Score   {_bar(health.overall)}  {health.overall}/100  {grade_color} Grade {health.grade}")
    print()
    row("Revenue Stability", f"{health.revenue_stability}/100  {_bar(health.revenue_stability, width=12)}")
    row("Churn Health",      f"{health.churn_health}/100  {_bar(health.churn_health, width=12)}")
    row("Engagement Depth",  f"{health.engagement_depth}/100  {_bar(health.engagement_depth, width=12)}")
    row("Growth Momentum",   f"{health.growth_momentum}/100  {_bar(health.growth_momentum, width=12)}")
    print()
    print(f"    → {health.interpretation}")

    # ── Revenue Breakdown ─────────────────────────────────────────────────────
    header("Monthly Revenue Breakdown")
    row("Gross Revenue",            _fmt_currency(roi.gross_monthly_revenue))
    row("Platform Fees & Costs",    f"({_fmt_currency(roi.total_platform_costs)})")
    row("Net Revenue",              _fmt_currency(roi.net_monthly_revenue))
    row("Projected Annual",         _fmt_currency(roi.annual_projected_revenue))
    print()
    row("  Subscription Revenue",   _fmt_currency(roi.subscription_revenue), indent=6)
    row("  Ancillary Revenue",      _fmt_currency(roi.ancillary_revenue), indent=6)

    # ── Member Economics ──────────────────────────────────────────────────────
    header("Member Economics")
    row("Active Members",           f"{current_members:,}")
    row("Avg Member LTV",           _fmt_currency(roi.avg_member_ltv))
    row("Payback Period",           f"{roi.member_payback_months:.1f} months")
    row("Monthly Churn Rate",       _fmt_pct(config.avg_monthly_churn_rate * 100))
    row("Platform ROI",             _fmt_pct(roi.platform_roi_percent))

    if config.content_creation_hours_per_month > 0:
        row("Revenue per Creator Hour", _fmt_currency(roi.time_roi_score))

    # ── Plan Distribution ─────────────────────────────────────────────────────
    plan_dist = get_plan_distribution(db_path=db_path)
    if plan_dist:
        header("Plan Distribution")
        for plan in plan_dist:
            bar = _bar(plan["pct_of_total"], width=14)
            row(f"{plan['plan_type'].capitalize()} plan",
                f"{plan['member_count']:>4} members  {bar}  {plan['pct_of_total']}%")

    # ── Churn Risk Segments ───────────────────────────────────────────────────
    header("Churn Risk Segments")
    for seg in risk_segments:
        emoji = {"High Risk": "🔴", "Medium Risk": "🟡", "Low Risk": "🟢"}.get(seg.tier, "")
        print(f"    {emoji}  {seg.tier:<14}  {seg.count:>4} members  "
              f"avg score: {seg.avg_engagement:.1f}")
    print()

    for seg in risk_segments:
        if seg.count > 0:
            print(f"    {seg.tier}:")
            print(f"      → {seg.recommended_action}")
            print()

    # ── Churn Reasons ─────────────────────────────────────────────────────────
    churn_reasons = get_churn_reasons_breakdown(db_path=db_path)
    if churn_reasons:
        header("Top Churn Reasons")
        for i, cr in enumerate(churn_reasons[:5], 1):
            label = cr["churn_reason"].replace("_", " ").title()
            row(f"{i}. {label}",
                f"{cr['total_churns']} members  |  avg {cr['avg_months_before_churn']} months active")

    # ── Revenue Trend ─────────────────────────────────────────────────────────
    trend = get_revenue_trend(months=6, db_path=db_path)
    if trend:
        header("6-Month Revenue Trend")
        max_rev = max(r["net_revenue"] for r in trend) or 1
        print(f"    {'Month':<10} {'Members':>8}  {'Net Revenue':>12}  Trend")
        print(f"    {'─'*54}")
        for r in trend:
            bar = _bar(r["net_revenue"], max_rev, width=16)
            month_str = r["snapshot_month"][:7]
            print(f"    {month_str:<10} {r['active_members']:>8}  "
                  f"{_fmt_currency(r['net_revenue']):>12}  {bar}")

    # ── 12-Month Growth Projection ────────────────────────────────────────────
    header("12-Month Growth Projection")
    row("Steady State Members",   f"{projection.steady_state_members:,}")
    row("Steady State Net Revenue", _fmt_currency(projection.steady_state_revenue))
    print()
    print(f"    {'Month':>6}  {'Members':>9}  {'Net Revenue':>13}")
    print(f"    {'─'*34}")
    for i in range(0, len(projection.months), 3):
        m = projection.months[i]
        mem = projection.projected_members[i]
        rev = projection.projected_net_revenue[i]
        print(f"    Month {m:>2}   {mem:>8,}   {_fmt_currency(rev):>12}")

    print(f"\n  {'═' * W}\n")


def export_csv_report(
    roi: ROIResult,
    health: HealthScore,
    projection: GrowthProjection,
    current_members: int,
    db_path: str
) -> str:
    """
    Export a structured CSV report to /reports/.
    Returns the file path of the written report.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(REPORTS_DIR, f"roi_report_{timestamp}.csv")

    trend = get_revenue_trend(months=12, db_path=db_path)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow(["COMMUNITY ROI REPORT", datetime.now().strftime("%Y-%m-%d %H:%M")])
        writer.writerow([])

        writer.writerow(["HEALTH SCORES"])
        writer.writerow(["Metric", "Score", "Grade"])
        writer.writerow(["Overall Health", health.overall, health.grade])
        writer.writerow(["Revenue Stability", health.revenue_stability, ""])
        writer.writerow(["Churn Health", health.churn_health, ""])
        writer.writerow(["Engagement Depth", health.engagement_depth, ""])
        writer.writerow(["Growth Momentum", health.growth_momentum, ""])
        writer.writerow([])

        writer.writerow(["MONTHLY FINANCIALS"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Active Members", current_members])
        writer.writerow(["Gross Monthly Revenue", roi.gross_monthly_revenue])
        writer.writerow(["Net Monthly Revenue", roi.net_monthly_revenue])
        writer.writerow(["Annual Projected Revenue", roi.annual_projected_revenue])
        writer.writerow(["Avg Member LTV", roi.avg_member_ltv])
        writer.writerow(["Platform ROI %", roi.platform_roi_percent])
        writer.writerow([])

        writer.writerow(["12-MONTH REVENUE TREND"])
        writer.writerow(["Month", "Active Members", "Net Revenue", "New Members", "Churned", "Churn Rate %"])
        for r in trend:
            writer.writerow([
                r["snapshot_month"], r["active_members"],
                r["net_revenue"], r["new_members"],
                r["churned_members"], r.get("churn_rate_pct", "")
            ])
        writer.writerow([])

        writer.writerow(["12-MONTH GROWTH PROJECTION"])
        writer.writerow(["Month", "Projected Members", "Projected Net Revenue"])
        for m, mem, rev in zip(projection.months, projection.projected_members, projection.projected_net_revenue):
            writer.writerow([f"Month {m}", mem, rev])

    return filepath
