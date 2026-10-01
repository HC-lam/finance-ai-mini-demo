# T1 Project Plan

## Project Goal

Develop a clear and reproducible research workflow that compares three familiar asset classes using illustrative ETF data:

- `SPY` — US equities
- `TLT` — long-term US Treasury bonds
- `GLD` — gold

The project starts with a written plan in T1 and later supports a bounded, verifiable AI-assisted analysis task using the same repository.

## Available Data

`data/etf_snapshot.csv` is a small, fixed snapshot with one row per ETF and six columns: `ticker`, `asset_class`, `expected_return_pct`, `volatility_pct`, `max_drawdown_pct`, and `expense_ratio_pct`. `data/data_dictionary.md` documents each column. The dataset is synthetic teaching data: all numeric values are illustrative assumptions, not live quotes, verified historical estimates, or forecasts.

## Expected Final Deliverable

The final deliverable is this concise written plan at `artifacts/t1/project-plan.md`, defining the comparison workflow and laying groundwork for later tutorials that design a bounded analysis task and organize a verifiable agent workflow.

## Three Project Milestones

1. **Project setup (T1)**: Read the repository overview, data dictionary, and snapshot data, and create this written project plan.
2. **Planned analysis design**: Design a bounded, reproducible comparison of SPY, TLT, and GLD on expected return, volatility, maximum drawdown, and expense ratio.
3. **Planned verification and handoff**: Verify the analysis workflow (inputs, outputs, steps) and hand it off for review and version control using Git.

## One Data Limitation

The dataset is synthetic teaching data and intentionally omits correlations, taxes, transaction costs, liquidity, currency exposure, and investor-specific constraints; it must not be used as investment advice or as the basis for a real investment decision.

## Next Action

Review this plan, then save the file with Git as part of the T1 tutorial workflow. No commits or pushes are made during T1.
