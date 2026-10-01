# T2 ETF Comparison: Annual Fees and Maximum Drawdown (SPY, TLT, GLD)

Building on the T1 plan, which described a reproducible workflow against a small synthetic snapshot, this T2 report upgrades the comparison to the instructor-prepared T2 ETF Data Pack of real historical daily prices.

## Source and Method

- **Inputs**: `data/t2/daily_prices.csv` (7,536 daily observations), `data/t2/fund_info.csv` (three fund records), `data/t2/data_dictionary.md`.
- **Preparation date**: 2026-09-25 (pack prepared from responses recorded as downloaded on 2026-09-20; independent live confirmation of retained history is pending).
- **Common drawdown period**: 2016-09-01 through 2026-08-31, inclusive, daily (US market sessions, `America/New_York`); 2,512 observations per ETF.
- **Adjustment basis**: `adjusted_close` (Yahoo chart `indicators.adjclose[0].adjclose`, USD, reflecting the provider's split and dividend adjustments). The raw `close` column was not used for the drawdown calculation.
- **Script**: `artifacts/t2/calculate_drawdown.py` (Python 3 standard library only).
- **Command executed**: `python3 artifacts/t2/calculate_drawdown.py`
- **Input-check result**: passed — 3 tickers (SPY, TLT, GLD); unique ticker/date pairs; ascending dates; positive finite prices; 2,512 rows per ETF; common first/last dates and matching date sets.
- **Calculation method**: for each ticker, all `adjusted_close` observations were processed with a cumulative maximum from the window start; `(value / cumulative_high − 1) × 100` was evaluated at every date; the most negative value is the maximum drawdown. The dictionary's tie rule was applied (earliest trough and its earliest corresponding peak; peak on or before trough; zero drawdown with the first date for both if no loss). Full precision was kept internally; only display values were rounded.

## 1. Comparison

| Ticker | Annual expense ratio (%) | Max drawdown (%) | Peak date | Trough date |
|---|---|---|---|---|
| SPY | 0.0945 | -33.72 | 2020-02-19 | 2020-03-23 |
| TLT | 0.15 | -48.35 | 2020-08-04 | 2023-10-19 |
| GLD | 0.4 | -26.40 | 2026-01-29 | 2026-07-16 |

Fee precision is preserved as disclosed: SPY 0.0945%, TLT 0.15%, GLD 0.4% (percentage units as recorded in `fund_info.csv`). Drawdowns are displayed to two decimals and are non-positive.

Fee disclosure dates (from `data/t2/fund_info.csv`; all accessed on 2026-09-25):
- **SPY**: fund-information as-of date 2026-09-10; fee-specific effective date not stated.
- **TLT**: current prospectus; specific date not stated in the fee panel.
- **GLD**: not stated in the selected field.

## 2. Observation

In this period, **GLD** has the smallest drawdown loss (closest to zero) at **-26.40%**, compared with SPY at -33.72% and TLT at -48.35%. There is no tie among the displayed two-decimal results. These drawdowns were calculated from `adjusted_close`, not read from a precomputed snapshot; closer to zero means a smaller loss. One limitation: these disclosed fees are current issuer snapshots, not ten-year average fees, and the drawdown measures daily-close loss only within this fixed window — not intraday losses, all-time risk, or future performance.

## 3. Agent Check

This is my own self-check of the calculated result; it is not independent verification, and the student has not yet checked the data.

- **Chosen ETF**: SPY (reported peak 2020-02-19, trough 2020-03-23).
- **Source rows re-read from `data/t2/daily_prices.csv`**:
  - 2020-02-19, SPY, `adjusted_close` = 307.639495849609375
  - 2020-03-23, SPY, `adjusted_close` = 203.911895751953125
- **Check command**: `python3 artifacts/t2/calculate_drawdown.py --verify SPY 2020-02-19 2020-03-23`
- **Actual output**: `recomputed (trough / peak - 1) * 100 = -33.717257210811404`, displayed to two decimals = -33.72.
- **Comparison**: the recomputed two-point value (-33.72) matches the full-series maximum drawdown reported above for SPY (-33.72). No correction or recheck was needed.
- **Method inspection**: the script uses all dates, all `adjusted_close` values, cumulative highs from the window start, and selects the trough only after its peak (peak on or before trough); for ties it keeps the earliest trough and earliest corresponding peak. The observation was checked against all three displayed results (GLD -26.40 is closest to zero; no tie).
- **Note**: this two-point arithmetic check confirms the reported pair; a two-point check alone cannot prove it is the worst drawdown in the whole window — that rests on the inspected full-series method.
