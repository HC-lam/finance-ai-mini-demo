#!/usr/bin/env python3
"""T2 ETF maximum drawdown calculation for SPY / TLT / GLD.

Computes per-ticker maximum drawdown from the adjusted_close column using a
cumulative high from the window start, applying the data dictionary's
earliest-trough / earliest-peak tie rule. Uses only the Python 3 standard
library (csv, math, sys). Prints a compact summary only; it never prints the
full 7,536-row input.

Usage:
  python3 artifacts/t2/calculate_drawdown.py
  python3 artifacts/t2/calculate_drawdown.py --verify SPY 2018-09-20 2020-03-23
"""

import csv
import math
import sys

DATA_PATH = "data/t2/daily_prices.csv"
TICKERS = ["SPY", "TLT", "GLD"]
EXPECTED_ROWS_PER_ETF = 2512


def load_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def run_checks(rows):
    """Run all required input checks; return (issues, by_ticker)."""
    issues = []
    ticker_set = set(r["ticker"] for r in rows)
    if ticker_set != set(TICKERS):
        issues.append("ticker set mismatch: %s" % sorted(ticker_set))

    by_ticker = {t: [] for t in TICKERS}
    for r in rows:
        if r["ticker"] in by_ticker:
            by_ticker[r["ticker"]].append(r)
        else:
            issues.append("unexpected ticker: %s" % r["ticker"])

    first_dates, last_dates, date_sets = {}, {}, {}
    for t in TICKERS:
        g = by_ticker[t]
        n = len(g)
        if n != EXPECTED_ROWS_PER_ETF:
            issues.append("%s: expected %d rows, got %d" % (t, EXPECTED_ROWS_PER_ETF, n))

        dates = [r["date"] for r in g]
        if len(set(dates)) != len(dates):
            dup = sorted({d for d in dates if dates.count(d) > 1})
            issues.append("%s: duplicate date keys %s" % (t, dup[:5]))
        if dates != sorted(dates):
            issues.append("%s: dates not in ascending order" % t)

        for r in g:
            for col in ("close", "adjusted_close"):
                try:
                    v = float(r[col])
                except (TypeError, ValueError):
                    issues.append("%s: non-numeric %s on %s: %r" % (t, col, r["date"], r[col]))
                    continue
                if not math.isfinite(v) or v <= 0:
                    issues.append("%s: non-positive/non-finite %s on %s: %r"
                                  % (t, col, r["date"], r[col]))

        first_dates[t] = dates[0] if dates else None
        last_dates[t] = dates[-1] if dates else None
        date_sets[t] = set(dates)

    if len(set(first_dates.values())) != 1:
        issues.append("first dates differ across tickers: %s" % first_dates)
    if len(set(last_dates.values())) != 1:
        issues.append("last dates differ across tickers: %s" % last_dates)
    base_set = date_sets[TICKERS[0]]
    for t in TICKERS[1:]:
        if date_sets[t] != base_set:
            issues.append("%s: date set differs from %s" % (t, TICKERS[0]))

    return issues, by_ticker


def compute(rows):
    """rows: list of dicts for one ticker, ascending by date.

    Returns full-precision max drawdown and its peak/trough info with the
    dictionary tie rule: earliest trough, and its earliest corresponding peak.
    """
    first = rows[0]
    best_dd = 0.0
    best_peak_date = first["date"]
    best_peak_price = float(first["adjusted_close"])
    best_trough_date = first["date"]
    best_trough_price = float(first["adjusted_close"])

    running_high = -math.inf
    high_date = None
    high_price = None
    for r in rows:
        price = float(r["adjusted_close"])
        if price > running_high:
            running_high = price
            high_date = r["date"]
            high_price = price
        dd = (price / running_high - 1.0) * 100.0
        if dd < best_dd:
            best_dd = dd
            best_trough_date = r["date"]
            best_trough_price = price
            best_peak_date = high_date
            best_peak_price = high_price

    return {
        "max_drawdown_pct": best_dd,
        "peak_date": best_peak_date,
        "peak_price": best_peak_price,
        "trough_date": best_trough_date,
        "trough_price": best_trough_price,
    }


def main():
    rows = load_rows(DATA_PATH)
    print("Loaded %d data rows from %s" % (len(rows), DATA_PATH))

    issues, by_ticker = run_checks(rows)
    if issues:
        print("INPUT CHECK FAILED:")
        for i in issues:
            print("  - %s" % i)
        print("Stopping before calculation; no results produced.")
        return 2
    print("Input checks passed: 3 tickers; unique ticker/date pairs; "
          "ascending dates; positive finite prices; %d rows per ETF; "
          "common first/last dates and matching date sets."
          % EXPECTED_ROWS_PER_ETF)

    results = {}
    for t in TICKERS:
        res = compute(by_ticker[t])
        results[t] = res
        print("%s | max_drawdown_pct=%.15f | peak=%s price=%.15f | "
              "trough=%s price=%.15f"
              % (t, res["max_drawdown_pct"], res["peak_date"],
                 res["peak_price"], res["trough_date"], res["trough_price"]))

    return 0


def verify():
    """Agent self-check: re-read a reported peak/trough pair from the CSV."""
    if len(sys.argv) != 5:
        print("Usage: calculate_drawdown.py --verify <ticker> <peak_date> <trough_date>")
        return 2
    ticker, peak_date, trough_date = sys.argv[2], sys.argv[3], sys.argv[4]
    rows = load_rows(DATA_PATH)
    peak = trough = None
    for r in rows:
        if r["ticker"] == ticker and r["date"] == peak_date:
            peak = r
        if r["ticker"] == ticker and r["date"] == trough_date:
            trough = r
    if peak is None or trough is None:
        print("VERIFY FAILED: could not locate reported rows for %s %s / %s"
              % (ticker, peak_date, trough_date))
        return 2
    peak_price = float(peak["adjusted_close"])
    trough_price = float(trough["adjusted_close"])
    recomputed = (trough_price / peak_price - 1.0) * 100.0
    print("VERIFY ticker=%s" % ticker)
    print("  peak row   : date=%s adjusted_close=%.15f" % (peak["date"], peak_price))
    print("  trough row : date=%s adjusted_close=%.15f" % (trough["date"], trough_price))
    print("  recomputed (trough / peak - 1) * 100 = %.15f" % recomputed)
    print("  displayed to 2 decimals = %.2f" % recomputed)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        sys.exit(verify())
    sys.exit(main())
