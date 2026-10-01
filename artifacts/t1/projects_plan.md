# T1 Project Plan

## Project Goal

Develop a clear and reproducible research workflow for comparing three familiar asset classes: SPY (US equities), TLT (long-term US Treasury bonds), and GLD (gold). This tutorial phase produces a written plan; later tutorials are planned to use the same repository for a bounded analysis task and a verifiable agent workflow.

## Available Data

- `data/etf_snapshot.csv` — one row per ETF with `ticker`, `asset_class`, `expected_return_pct`, `volatility_pct`, `max_drawdown_pct`, and `expense_ratio_pct`.
- `data/data_dictionary.md` — field definitions, units, and limitations.
- The dataset is **synthetic teaching data**: all numeric values are illustrative assumptions, not live quotations, verified historical estimates, or forecasts.

## Expected Final Deliverable

The T1 deliverable is this written project plan in Markdown. Later work is planned to produce an analysis report (for example, an ETF comparison with verified calculations) inside `artifacts/`; that analysis is planned work and has not been completed yet.

## Three Project Milestones

1. Write and review this initial project plan (T1).
2. Design a bounded comparison analysis of the three ETFs, including the calculation method and output format (planned).
3. Run the analysis, verify the results manually, and save the report with Git (planned).

## One Data Limitation

All values in the snapshot are synthetic teaching assumptions and are not real market data; the dataset also omits correlations, taxes, transaction costs, liquidity, currency exposure, and investor-specific constraints.

## Next Action

Review this plan against the repository contents. The next step is planned as designing the bounded analysis task and its acceptance check before any calculations are run.
