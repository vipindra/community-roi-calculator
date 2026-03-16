# Community ROI Calculator

A command-line tool that helps online community creators measure the real financial value of their community, identify members at churn risk, and project growth over the next 12 months.

Built for creators running subscription communities on platforms like Circle, Mighty Networks, or Kajabi — where understanding member lifetime value, churn economics, and engagement health directly determines how you spend your time.

---

## The Problem This Solves

Most community creators track vanity metrics: total member count, post volume, weekly active users. These numbers feel good but don't answer the questions that actually matter when you're deciding whether to hire a community manager, launch a new course, or cut your subscription price.

This tool answers the questions that drive real decisions:

- What is a single member worth to my business over their lifetime?
- At my current churn rate, what's the largest my community can realistically grow?
- Which members are about to leave, and what should I do about it?
- Is my community ROI-positive relative to how much time I'm putting into it?
- If I acquire 15 new members a month, what does my revenue look like in 12 months?

---

## Features

**ROI Engine**
- Calculates gross and net monthly revenue across subscription, course, coaching, and sponsorship streams
- Member lifetime value (LTV) based on your actual churn rate and pricing
- Platform ROI: net revenue relative to what you're paying the platform
- Creator time ROI: how much you're earning per hour of content creation

**Community Health Score**
- Overall score out of 100 with letter grade (A through F)
- Four weighted dimensions: revenue stability, churn health, engagement depth, growth momentum
- Plain-English interpretation of what the score means and where to focus

**Churn Risk Segmentation**
- Segments all active members into High, Medium, and Low risk tiers
- Based on engagement score calculated from real activity signals
- Specific recommended actions for each risk tier

**Growth Projection**
- Month-by-month member count and net revenue forecast for the next 12 months
- Steady-state calculation: the equilibrium size your community will reach at current churn and acquisition rates
- Uses simulation rather than closed-form approximation for accuracy

**Data Layer**
- SQLite database with full member lifecycle tracking
- Monthly revenue snapshots with churn rate calculation
- Engagement event logging with weighted scoring by event type
- Churn reason tracking and aggregation

**Reporting**
- Formatted terminal report with ASCII charts
- CSV export for further analysis in Excel or Google Sheets

---

## Quickstart

```bash
# Clone the repo
git clone https://github.com/your-username/community-roi-calculator.git
cd community-roi-calculator

# No dependencies to install — uses Python standard library only
# Requires Python 3.8+

# Run with auto-generated sample data (a fitness coach community with ~200 members)
python main.py

# Export a CSV report at the same time
python main.py --csv

# Reset and regenerate fresh sample data
python main.py --reset
```

---

## Sample Output

```
  ══════════════════════════════════════════════════════════════
                       COMMUNITY ROI REPORT
                          January 2025
  ══════════════════════════════════════════════════════════════

  ◆ COMMUNITY HEALTH SCORE
  ──────────────────────────────────────────────────────────────
    Overall Score   ████████████████░░░░  78.4/100  🟢 Grade B

    Revenue Stability  82.1/100  █████████░░░
    Churn Health       74.0/100  ████████░░░░
    Engagement Depth   81.5/100  █████████░░░
    Growth Momentum    65.2/100  ███████░░░░░

    → Healthy community with room to optimize engagement and revenue mix.

  ◆ MONTHLY REVENUE BREAKDOWN
  ──────────────────────────────────────────────────────────────
    Gross Revenue ............................ $10,842.00
    Platform Fees & Costs ................... ($99.00)
    Net Revenue .............................. $10,346.00
    Projected Annual ......................... $124,152.00

  ◆ CHURN RISK SEGMENTS
  ──────────────────────────────────────────────────────────────
    🔴  High Risk        42 members  avg score: 1.8
    🟡  Medium Risk      67 members  avg score: 11.3
    🟢  Low Risk         96 members  avg score: 34.7

    High Risk:
      → Send personalised re-engagement message within 48 hours.
        Offer a check-in call or exclusive resource.
```

---

## Project Structure

```
community-roi-calculator/
├── main.py                 Entry point and CLI
├── src/
│   ├── calculator.py       Core ROI formulas and LTV calculations
│   ├── db.py               SQLite schema, write operations, and SQL queries
│   ├── analyze.py          Health scoring, churn risk segmentation, projections
│   ├── sample_data.py      Realistic seed data generator
│   └── report.py           Terminal report formatting and CSV export
├── data/                   SQLite database lives here (gitignored)
├── reports/                CSV exports land here (gitignored)
├── requirements.txt        No third-party dependencies required
└── .gitignore
```

---

## Adapting for Your Own Community

The community configuration is defined in `main.py` under the `CommunityConfig` block. Update these values to match your actual numbers:

```python
config = CommunityConfig(
    monthly_subscription_price=49.0,       # what members pay per month
    annual_subscription_price=399.0,       # annual plan price
    platform_fee_percent=0.04,             # platform's revenue share
    monthly_platform_cost=99.0,            # flat monthly SaaS fee
    avg_monthly_churn_rate=0.055,          # 5.5% monthly churn
    avg_new_members_per_month=15,          # new members joining each month
    one_time_course_revenue=400.0,         # monthly average from course sales
    coaching_revenue_per_month=600.0,
    sponsorship_revenue_per_month=200.0,
    content_creation_hours_per_month=20.0,
    creator_hourly_rate=75.0,              # your opportunity cost per hour
)
```

To use real member data instead of the sample data, use the functions in `src/db.py` to insert your own member records, engagement events, and monthly snapshots.

---

## Design Decisions

**Why SQLite?**
Zero setup, zero infrastructure. Creators running communities aren't necessarily engineers. SQLite means this runs on any machine with Python installed, with no server, no credentials, and no configuration required. The schema is also straightforward to inspect directly if someone wants to understand what data is being stored.

**Why no third-party dependencies?**
Same reason. The entire tool runs on Python's standard library. If you want to add matplotlib charts or pandas DataFrames for richer analysis, the optional dependencies in `requirements.txt` are clearly labeled.

**Why simulation for steady-state projection instead of a closed-form formula?**
The closed-form formula for steady state (new_members / churn_rate) gives the equilibrium point but doesn't tell you how long it takes to get there, or what the revenue curve looks like on the way. The month-by-month simulation costs almost nothing computationally and produces projections that are easier to reason about and extend.

**Why weight engagement events differently?**
A member attending a live event is a much stronger retention signal than a member reacting to a post. Treating all events equally would underweight the behaviors that actually predict whether someone renews. The weights in `sample_data.py` are based on community industry benchmarks and can be tuned to match your platform's data.

---

## Background

This project grew out of thinking about a recurring problem in the creator economy: community builders often have a rough sense of their monthly revenue but very little visibility into whether that revenue is healthy or fragile, which members are likely to leave next month, or what their community would look like in a year if nothing changed.

The calculations here are not novel — LTV = revenue per period / churn rate is standard SaaS finance. The value is in applying those formulas to a community context and surfacing the outputs in a way that drives action rather than just satisfying curiosity.

---

## License

MIT. Use it, fork it, adapt it.
