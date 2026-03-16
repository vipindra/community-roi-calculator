"""
ROI calculation engine for creator communities.

This module contains the core formulas used to calculate community
financial value, member lifetime value, payback periods, and
engagement-weighted revenue contribution.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CommunityConfig:
    """
    Input parameters that describe a creator's community and business model.
    All monetary values are in USD.
    """
    monthly_subscription_price: float
    annual_subscription_price: Optional[float]
    platform_fee_percent: float          # e.g. 0.05 for 5%
    monthly_platform_cost: float         # flat SaaS fee
    avg_monthly_churn_rate: float        # e.g. 0.05 for 5% monthly churn
    avg_new_members_per_month: int
    one_time_course_revenue: float = 0.0
    coaching_revenue_per_month: float = 0.0
    sponsorship_revenue_per_month: float = 0.0
    content_creation_hours_per_month: float = 0.0
    creator_hourly_rate: float = 0.0     # opportunity cost of creator's time


@dataclass
class ROIResult:
    """Full breakdown of a community's ROI across all dimensions."""
    # Revenue
    gross_monthly_revenue: float
    net_monthly_revenue: float           # after platform fees and costs
    annual_projected_revenue: float

    # Member economics
    avg_member_ltv: float                # average lifetime value per member
    member_payback_months: float         # months to recover CAC equivalent

    # Growth
    steady_state_members: int            # equilibrium size at current churn/growth
    months_to_steady_state: float

    # ROI ratios
    platform_roi_percent: float          # net revenue / platform cost
    time_roi_score: float                # revenue per hour of creator time

    # Breakdown
    subscription_revenue: float
    ancillary_revenue: float
    total_platform_costs: float
    opportunity_cost_monthly: float


def calculate_member_ltv(monthly_price: float, monthly_churn_rate: float,
                          platform_fee_percent: float) -> float:
    """
    Calculate average lifetime value of a single member.

    Uses the standard LTV formula: LTV = (revenue per period) / churn rate
    adjusted for platform fees.

    Args:
        monthly_price: What a member pays per month
        monthly_churn_rate: Probability a member leaves each month (0 to 1)
        platform_fee_percent: Platform's cut as a decimal

    Returns:
        Expected total revenue from one member over their lifetime
    """
    if monthly_churn_rate <= 0 or monthly_churn_rate >= 1:
        raise ValueError("Churn rate must be between 0 and 1 exclusive.")

    net_revenue_per_member = monthly_price * (1 - platform_fee_percent)
    avg_lifetime_months = 1 / monthly_churn_rate
    return net_revenue_per_member * avg_lifetime_months


def calculate_steady_state_members(new_per_month: int,
                                    monthly_churn_rate: float) -> int:
    """
    The equilibrium member count a community reaches when acquisition
    equals churn. This is where most stable communities settle.

    Formula: steady_state = monthly_new_members / churn_rate
    """
    if monthly_churn_rate <= 0:
        raise ValueError("Churn rate must be greater than 0.")
    return int(new_per_month / monthly_churn_rate)


def calculate_months_to_steady_state(new_per_month: int,
                                      monthly_churn_rate: float,
                                      current_members: int = 0,
                                      threshold: float = 0.95) -> float:
    """
    Estimate how many months until a community reaches ~95% of steady state.
    Uses iterative simulation rather than closed-form approximation for accuracy.

    Args:
        new_per_month: New members joining each month
        monthly_churn_rate: Monthly churn rate
        current_members: Current member count (default 0 for new communities)
        threshold: What fraction of steady state counts as "reached" (default 95%)

    Returns:
        Number of months to reach steady state threshold
    """
    target = calculate_steady_state_members(new_per_month, monthly_churn_rate)
    members = float(current_members)
    months = 0

    while members < target * threshold and months < 1200:
        members = members * (1 - monthly_churn_rate) + new_per_month
        months += 1

    return float(months)


def run_roi_calculation(config: CommunityConfig,
                         current_members: int) -> ROIResult:
    """
    Main entry point. Takes a community config and current member count,
    returns a full ROI breakdown.

    Args:
        config: CommunityConfig dataclass with all community parameters
        current_members: How many paying members the community has right now

    Returns:
        ROIResult with complete financial and engagement breakdown
    """
    # Subscription revenue (net of platform percentage fee)
    gross_subscription = current_members * config.monthly_subscription_price
    net_subscription = gross_subscription * (1 - config.platform_fee_percent)

    # Ancillary revenue streams
    ancillary = (
        config.one_time_course_revenue / 12  # annualized to monthly
        + config.coaching_revenue_per_month
        + config.sponsorship_revenue_per_month
    )

    # Total costs
    total_costs = config.monthly_platform_cost
    opportunity_cost = (
        config.content_creation_hours_per_month * config.creator_hourly_rate
    )

    gross_monthly = gross_subscription + ancillary
    net_monthly = net_subscription + ancillary - total_costs

    # LTV and payback
    ltv = calculate_member_ltv(
        config.monthly_subscription_price,
        config.avg_monthly_churn_rate,
        config.platform_fee_percent
    )

    # Payback period: how many months of membership covers CAC
    # Using platform cost per acquired member as proxy for CAC
    cac_proxy = config.monthly_platform_cost / max(config.avg_new_members_per_month, 1)
    net_revenue_per_member_monthly = (
        config.monthly_subscription_price * (1 - config.platform_fee_percent)
    )
    payback_months = cac_proxy / max(net_revenue_per_member_monthly, 0.01)

    # Growth trajectory
    steady_state = calculate_steady_state_members(
        config.avg_new_members_per_month,
        config.avg_monthly_churn_rate
    )
    months_to_ss = calculate_months_to_steady_state(
        config.avg_new_members_per_month,
        config.avg_monthly_churn_rate,
        current_members
    )

    # ROI ratios
    platform_roi = (net_monthly / max(config.monthly_platform_cost, 0.01)) * 100
    time_roi = net_monthly / max(config.content_creation_hours_per_month, 1)

    return ROIResult(
        gross_monthly_revenue=gross_monthly,
        net_monthly_revenue=net_monthly,
        annual_projected_revenue=net_monthly * 12,
        avg_member_ltv=ltv,
        member_payback_months=payback_months,
        steady_state_members=steady_state,
        months_to_steady_state=months_to_ss,
        platform_roi_percent=platform_roi,
        time_roi_score=time_roi,
        subscription_revenue=net_subscription,
        ancillary_revenue=ancillary,
        total_platform_costs=total_costs,
        opportunity_cost_monthly=opportunity_cost,
    )
