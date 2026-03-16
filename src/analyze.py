"""
Analysis layer for community health and churn prediction.

This module sits on top of the database queries and ROI calculations
to produce higher-level signals: health scores, churn risk tiers,
engagement segments, and growth projections.

These are the outputs a CSM actually uses to prioritize their week.
"""

from dataclasses import dataclass, field
from typing import Optional
from src.db import (
    get_revenue_trend,
    get_at_risk_members,
    get_engagement_score_by_member,
    get_plan_distribution,
    get_churn_reasons_breakdown,
    get_active_member_count,
)
from src.calculator import CommunityConfig, run_roi_calculation


@dataclass
class HealthScore:
    """
    Overall community health score out of 100.
    Broken into four weighted dimensions so creators know exactly
    where to focus their energy.
    """
    overall: float
    revenue_stability: float      # 30% weight — is revenue growing or declining?
    churn_health: float           # 30% weight — is churn rate sustainable?
    engagement_depth: float       # 25% weight — are members actually using the platform?
    growth_momentum: float        # 15% weight — is the member count trending up?
    grade: str                    # A / B / C / D / F for easy reading
    interpretation: str           # plain English summary


@dataclass
class ChurnRiskSegment:
    """A group of members at a specific risk tier."""
    tier: str                     # "High Risk", "Medium Risk", "Low Risk"
    member_ids: list[int] = field(default_factory=list)
    count: int = 0
    avg_engagement: float = 0.0
    recommended_action: str = ""


@dataclass
class GrowthProjection:
    """Month-by-month member count and revenue forecast."""
    months: list[int] = field(default_factory=list)
    projected_members: list[int] = field(default_factory=list)
    projected_net_revenue: list[float] = field(default_factory=list)
    steady_state_members: int = 0
    steady_state_revenue: float = 0.0


def score_community_health(db_path: str,
                            config: CommunityConfig,
                            current_members: int) -> HealthScore:
    """
    Calculate an overall health score for a community based on its
    revenue trend, churn rate, engagement levels, and growth momentum.

    Scoring is transparent and formula-based — no black box.
    """
    trend = get_revenue_trend(months=6, db_path=db_path)

    # ── Revenue stability (0-100) ────────────────────────────────────────────
    if len(trend) >= 2:
        recent = trend[-1]["net_revenue"]
        prior = trend[-3]["net_revenue"] if len(trend) >= 3 else trend[0]["net_revenue"]
        if prior > 0:
            revenue_change_pct = (recent - prior) / prior
            # +20% or more = 100, flat = 60, -20% or more = 0
            revenue_score = min(100, max(0, 60 + revenue_change_pct * 200))
        else:
            revenue_score = 50.0
    else:
        revenue_score = 50.0

    # ── Churn health (0-100) ─────────────────────────────────────────────────
    # Monthly churn benchmarks for online communities:
    # < 2% = excellent, 2-5% = healthy, 5-8% = concerning, > 8% = critical
    churn_rate = config.avg_monthly_churn_rate
    if churn_rate <= 0.02:
        churn_score = 100.0
    elif churn_rate <= 0.05:
        churn_score = 100 - ((churn_rate - 0.02) / 0.03) * 40
    elif churn_rate <= 0.08:
        churn_score = 60 - ((churn_rate - 0.05) / 0.03) * 40
    else:
        churn_score = max(0, 20 - (churn_rate - 0.08) * 200)

    # ── Engagement depth (0-100) ─────────────────────────────────────────────
    at_risk = get_at_risk_members(db_path=db_path)
    at_risk_count = len(at_risk)
    if current_members > 0:
        at_risk_pct = at_risk_count / current_members
        engagement_score = max(0, 100 - at_risk_pct * 150)
    else:
        engagement_score = 50.0

    # ── Growth momentum (0-100) ──────────────────────────────────────────────
    if len(trend) >= 3:
        recent_growth = trend[-1]["new_members"] - trend[-1]["churned_members"]
        older_growth = trend[-3]["new_members"] - trend[-3]["churned_members"]
        if recent_growth > 0:
            growth_score = min(100, 60 + (recent_growth / max(current_members, 1)) * 400)
        elif recent_growth == 0:
            growth_score = 50.0
        else:
            growth_score = max(0, 50 + recent_growth)
    else:
        growth_score = 50.0

    # ── Weighted overall ─────────────────────────────────────────────────────
    overall = (
        revenue_score * 0.30
        + churn_score * 0.30
        + engagement_score * 0.25
        + growth_score * 0.15
    )

    grade = (
        "A" if overall >= 85 else
        "B" if overall >= 70 else
        "C" if overall >= 55 else
        "D" if overall >= 40 else "F"
    )

    interpretation = _interpret_health(overall, churn_rate, at_risk_pct if current_members > 0 else 0)

    return HealthScore(
        overall=round(overall, 1),
        revenue_stability=round(revenue_score, 1),
        churn_health=round(churn_score, 1),
        engagement_depth=round(engagement_score, 1),
        growth_momentum=round(growth_score, 1),
        grade=grade,
        interpretation=interpretation
    )


def _interpret_health(overall: float, churn_rate: float, at_risk_pct: float) -> str:
    """Generate a plain-English one-liner summary of community health."""
    if overall >= 85:
        return "Community is thriving. Focus on scaling what's already working."
    elif overall >= 70:
        if churn_rate > 0.05:
            return "Strong growth but churn is eating into gains. Prioritize member activation."
        return "Healthy community with room to optimize engagement and revenue mix."
    elif overall >= 55:
        if at_risk_pct > 0.3:
            return "Over 30% of members show low engagement. Intervention campaigns needed now."
        return "Community is stable but not growing. Revisit acquisition and onboarding strategy."
    elif overall >= 40:
        return "Warning signs across multiple dimensions. Revenue and member trends need immediate attention."
    else:
        return "Community health is critical. Churn is outpacing growth and engagement has collapsed."


def segment_members_by_churn_risk(db_path: str) -> list[ChurnRiskSegment]:
    """
    Segment active members into three churn risk tiers based on
    engagement score, weighted by recency.

    Tier thresholds are based on community industry benchmarks:
    - Low risk: engagement score > 20
    - Medium risk: score 5–20
    - High risk: score < 5 (or zero activity)
    """
    scored = get_engagement_score_by_member(top_n=10000, db_path=db_path)
    at_risk_raw = get_at_risk_members(low_engagement_threshold=5.0, db_path=db_path)
    at_risk_ids = {r["id"] for r in at_risk_raw}

    high_risk = ChurnRiskSegment(
        tier="High Risk",
        recommended_action="Send personalised re-engagement message within 48 hours. Offer a check-in call or exclusive resource."
    )
    medium_risk = ChurnRiskSegment(
        tier="Medium Risk",
        recommended_action="Include in next nurture campaign. Highlight underused features relevant to their goals."
    )
    low_risk = ChurnRiskSegment(
        tier="Low Risk",
        recommended_action="Recognise publicly, invite to contribute content or mentor newer members."
    )

    for member in scored:
        score = member["engagement_score"]
        mid = member["id"]
        if score <= 5:
            high_risk.member_ids.append(mid)
            high_risk.avg_engagement = (
                (high_risk.avg_engagement * high_risk.count + score) / (high_risk.count + 1)
            )
            high_risk.count += 1
        elif score <= 20:
            medium_risk.member_ids.append(mid)
            medium_risk.avg_engagement = (
                (medium_risk.avg_engagement * medium_risk.count + score) / (medium_risk.count + 1)
            )
            medium_risk.count += 1
        else:
            low_risk.member_ids.append(mid)
            low_risk.avg_engagement = (
                (low_risk.avg_engagement * low_risk.count + score) / (low_risk.count + 1)
            )
            low_risk.count += 1

    return [high_risk, medium_risk, low_risk]


def project_growth(config: CommunityConfig,
                    current_members: int,
                    months_ahead: int = 12) -> GrowthProjection:
    """
    Project member count and net revenue month by month.

    Models growth as: next_month = current * (1 - churn) + new_acquisitions
    Revenue is recalculated each month against the projected member count.
    """
    projection = GrowthProjection()
    members = float(current_members)

    for month in range(1, months_ahead + 1):
        members = members * (1 - config.avg_monthly_churn_rate) + config.avg_new_members_per_month
        projected_int = int(members)

        result = run_roi_calculation(config, projected_int)

        projection.months.append(month)
        projection.projected_members.append(projected_int)
        projection.projected_net_revenue.append(round(result.net_monthly_revenue, 2))

    # Steady state values
    from src.calculator import calculate_steady_state_members
    ss_members = calculate_steady_state_members(
        config.avg_new_members_per_month,
        config.avg_monthly_churn_rate
    )
    ss_result = run_roi_calculation(config, ss_members)

    projection.steady_state_members = ss_members
    projection.steady_state_revenue = round(ss_result.net_monthly_revenue, 2)

    return projection
