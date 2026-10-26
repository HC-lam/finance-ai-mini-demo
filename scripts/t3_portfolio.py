#!/usr/bin/env python3
"""Small, offline T3 portfolio experiment. Python 3 standard library only."""

import argparse
import csv
import hashlib
import html
import io
import json
import math
from datetime import date
from pathlib import Path

VERSION = 1
TICKERS = ("SPY", "TLT", "GLD")
EPS = 1e-12
BASELINE = {ticker: 1 / 3 for ticker in TICKERS}
WINDOWS = {
    "design": ("2021-09-01", "2024-08-31"),
    "test": ("2024-09-01", "2026-08-31"),
}
RULES = {
    "holdings": "buy-and-hold; initial weights drift; no rebalancing",
    "initial_nav": 100,
    "normalization": "each window starts at its own first available common close",
    "price_field": "adjusted_close",
    "costs": "no additional fees, transaction costs, slippage or tax",
    "candidate_set": "66 long-only 10%-grid triples plus exact equal thirds",
    "eligibility": "design total return >= equal-weight total return - tolerance",
    "objective": "minimize nonnegative maximum-drawdown loss magnitude",
    "ties": "within tolerance: baseline, then higher return, then ascending SPY/TLT/GLD weights",
    "fallback": "retain baseline unless drawdown loss is strictly smaller beyond tolerance",
    "tolerance": EPS,
}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def write_new(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(raw)


def read_json(path):
    raw = Path(path).read_bytes()
    return json.loads(raw, parse_constant=lambda value: fail("Non-finite JSON value: " + value)), raw


def fail(message):
    raise ValueError(message)


def valid_date(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        fail("Dates must use YYYY-MM-DD")
    return value


def positive_number(value):
    if isinstance(value, bool):
        fail("Prices must be finite positive numbers")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        fail("Prices must be finite positive numbers")
    return number


def validate_weights(weights):
    if not isinstance(weights, dict) or set(weights) != set(TICKERS):
        fail("Weights must name exactly SPY, TLT and GLD")
    values = list(weights.values())
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) or v < 0 for v in values):
        fail("Weights must be finite nonnegative numbers")
    if abs(math.fsum(values) - 1) > EPS:
        fail("Weights must sum to one")


def validate_input(data, window):
    if data.get("version") != VERSION or data.get("window") != window:
        fail("Wrong input version or window")
    if data.get("tickers") != list(TICKERS):
        fail("Unexpected asset universe")
    start, end = WINDOWS[window]
    period = data["period"]
    dates = data["dates"]
    if period["requested_start"] != start or period["requested_end"] != end:
        fail("Unexpected date window")
    if len(dates) < 2 or dates != sorted(set(dates)):
        fail("Need at least two unique ascending dates")
    if any(not start <= valid_date(day) <= end for day in dates):
        fail("Date outside the requested window")
    if (period["first_date"], period["last_date"], period["observations"]) != (
            dates[0], dates[-1], len(dates)):
        fail("Period metadata does not match the observations")
    if set(data["prices"]) != set(TICKERS):
        fail("Missing or unexpected price series")
    for ticker in TICKERS:
        if len(data["prices"][ticker]) != len(dates):
            fail("Misaligned price series")
        for price in data["prices"][ticker]:
            positive_number(price)


def prepare(csv_path, out_dir):
    raw = Path(csv_path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not {"date", "ticker", "adjusted_close"}.issubset(reader.fieldnames or []):
        fail("CSV needs date, ticker and adjusted_close columns")
    series = {ticker: {} for ticker in TICKERS}
    for row in reader:
        ticker = row["ticker"]
        if ticker not in series:
            fail("Unexpected ticker: " + ticker)
        day = valid_date(row["date"])
        if day in series[ticker]:
            fail("Duplicate ticker/date: " + ticker + " " + day)
        series[ticker][day] = positive_number(row["adjusted_close"])
    dates = sorted(series[TICKERS[0]])
    if not dates or any(set(series[ticker]) != set(dates) for ticker in TICKERS):
        fail("Missing or misaligned dates across the three ETFs")
    files = {}
    for window, (start, end) in WINDOWS.items():
        selected = [day for day in dates if start <= day <= end]
        if len(selected) < 2:
            fail("Empty or too-short " + window + " window")
        data = {
            "version": VERSION, "window": window, "tickers": list(TICKERS),
            "source_sha256": sha256(raw), "price_field": "adjusted_close",
            "period": {"requested_start": start, "requested_end": end,
                       "first_date": selected[0], "last_date": selected[-1],
                       "observations": len(selected)},
            "dates": selected,
            "prices": {ticker: [series[ticker][day] for day in selected] for ticker in TICKERS},
        }
        validate_input(data, window)
        files[window + ".json"] = json_bytes(data)
    manifest = {
        "version": VERSION, "source": str(csv_path), "source_sha256": sha256(raw),
        "source_observations_per_etf": len(dates),
        "files": {name: sha256(content) for name, content in files.items()},
        "note": "Procedural separation only. Both windows are historical and were available in T2.",
    }
    files["manifest.json"] = json_bytes(manifest)
    for name in files:
        if (Path(out_dir) / name).exists():
            fail("Output already exists: " + str(Path(out_dir) / name))
    for name, content in files.items():
        write_new(Path(out_dir) / name, content)
    return manifest


def backtest(data, weights):
    """Fixed initial units, normalized using the first price inside this window."""
    validate_weights(weights)
    prices = data["prices"]
    nav = [100 * math.fsum(weights[ticker] * (prices[ticker][i] / prices[ticker][0])
                          for ticker in TICKERS) for i in range(len(data["dates"]))]
    nav[0] = 100.0
    peak = nav[0]
    curve = []
    for day, value in zip(data["dates"], nav):
        peak = max(peak, value)
        curve.append({"date": day, "nav": value, "drawdown": value / peak - 1})
    return {"weights": dict(weights),
            "metrics": {"total_return": nav[-1] / 100 - 1,
                        "max_drawdown": min(point["drawdown"] for point in curve)},
            "curve": curve}


def candidates():
    grid = [{"SPY": a / 10, "TLT": b / 10, "GLD": (10 - a - b) / 10}
            for a in range(11) for b in range(11 - a)]
    return grid + [dict(BASELINE)]


def baseline(design_path):
    data, raw = read_json(design_path)
    validate_input(data, "design")
    return {"version": VERSION, "kind": "baseline-design", "period": data["period"],
            "design_sha256": sha256(raw), "source_sha256": data["source_sha256"],
            "rules": RULES, **backtest(data, BASELINE)}


def optimize(design_path):
    # This command has one data input. It never opens a test file or the full CSV.
    data, raw = read_json(design_path)
    validate_input(data, "design")
    baseline_result = backtest(data, BASELINE)
    results = [backtest(data, weights) for weights in candidates()]
    eligible = [result for result in results if result["metrics"]["total_return"] >=
                baseline_result["metrics"]["total_return"] - EPS]
    minimum_loss = min(-result["metrics"]["max_drawdown"] for result in eligible)
    ties = [result for result in eligible if
            -result["metrics"]["max_drawdown"] <= minimum_loss + EPS]
    equal_tie = [result for result in ties if result["weights"] == BASELINE]
    if equal_tie:
        selected = equal_tie[0]
    else:
        highest_return = max(result["metrics"]["total_return"] for result in ties)
        return_ties = [result for result in ties if
                       result["metrics"]["total_return"] >= highest_return - EPS]
        selected = min(return_ties, key=lambda result: tuple(result["weights"][t] for t in TICKERS))
    improved = (selected["metrics"]["max_drawdown"] >
                baseline_result["metrics"]["max_drawdown"] + EPS)
    if not improved:
        selected = baseline_result
    return {
        "version": VERSION, "kind": "candidate", "period": data["period"],
        "design_sha256": sha256(raw), "source_sha256": data["source_sha256"],
        "rules": RULES, "candidate_count": len(results), "eligible_count": len(eligible),
        "baseline_metrics": baseline_result["metrics"],
        "improved_design_drawdown": improved,
        "selection_message": ("Selected a design-period improvement under the fixed rule." if improved else
                              "No strictly smaller design drawdown loss. Retained the equal-weight baseline."),
        **selected,
    }


def evaluate(test_path, candidate_path, expected_candidate_sha256):
    candidate, candidate_raw = read_json(candidate_path)
    if sha256(candidate_raw) != expected_candidate_sha256:
        fail("Candidate hash differs from the approved freeze; test input was not opened")
    if candidate.get("version") != VERSION or candidate.get("kind") != "candidate":
        fail("Expected a version-1 candidate file")
    if candidate.get("rules") != RULES:
        fail("Candidate rules differ from the fixed classroom experiment")
    validate_weights(candidate["weights"])
    if not any(all(abs(candidate["weights"][t] - w[t]) <= EPS for t in TICKERS)
               for w in candidates()):
        fail("Candidate is outside the fixed grid/baseline set")
    test, test_raw = read_json(test_path)
    validate_input(test, "test")
    if candidate["source_sha256"] != test["source_sha256"]:
        fail("Candidate and test inputs come from different source packs")
    return {
        "version": VERSION, "kind": "evaluation", "period": test["period"],
        "source_sha256": test["source_sha256"], "test_sha256": sha256(test_raw),
        "candidate_sha256": sha256(candidate_raw), "design_sha256": candidate["design_sha256"],
        "rules": RULES, "baseline": backtest(test, BASELINE),
        "candidate": backtest(test, candidate["weights"]),
    }


def chart(baseline_curve, candidate_curve, field, title):
    curves = [baseline_curve, candidate_curve]
    values = [point[field] for curve in curves for point in curve]
    low, high = min(values), max(values)
    if high == low:
        low, high = low - 1, high + 1
    def y(value):
        return 220 - 175 * (value - low) / (high - low)
    parts = [f'<svg viewBox="0 0 760 280" role="img" aria-label="{html.escape(title)}">',
             f'<title>{html.escape(title)}</title>']
    for fraction in (0, 0.5, 1):
        value = low + (high - low) * fraction
        label = f"{value:.1%}" if field == "drawdown" else f"{value:.1f}"
        parts.append(f'<line x1="70" y1="{y(value):.2f}" x2="735" y2="{y(value):.2f}" stroke="#d9e2eb"/>')
        parts.append(f'<text x="61" y="{y(value)+4:.2f}" text-anchor="end">{label}</text>')
    for curve, color, dash in zip(curves, ("#2764a5", "#b44624"), ("7 4", "none")):
        points = " ".join(f'{70 + 665*i/(len(curve)-1):.2f},{y(point[field]):.2f}'
                          for i, point in enumerate(curve))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"/>')
    parts += [f'<text x="70" y="245">{baseline_curve[0]["date"]}</text>',
              f'<text x="735" y="245" text-anchor="end">{baseline_curve[-1]["date"]}</text>',
              '<text x="70" y="273" fill="#2764a5">Dashed: equal-weight baseline</text>',
              '<text x="420" y="273" fill="#b44624">Solid: frozen candidate</text>', '</svg>']
    return "".join(parts)


def page(baseline_path, candidate_path, evaluation_path):
    base, _ = read_json(baseline_path)
    selected, selected_raw = read_json(candidate_path)
    result, _ = read_json(evaluation_path)
    if base["design_sha256"] != selected["design_sha256"] or result["design_sha256"] != selected["design_sha256"]:
        fail("Design input hashes do not match")
    if result["candidate_sha256"] != sha256(selected_raw):
        fail("Candidate changed after evaluation. Preserve the frozen candidate.")
    rows = []
    for window, name, item in (("Design", "Equal-weight baseline", base),
                               ("Design", "Selected candidate", selected),
                               ("Test", "Equal-weight baseline", result["baseline"]),
                               ("Test", "Frozen candidate", result["candidate"])):
        metrics = item["metrics"]
        rows.append(f'<tr><td>{window}</td><td>{name}</td><td>{metrics["total_return"]:.2%}</td>'
                    f'<td>{metrics["max_drawdown"]:.2%}</td></tr>')
    allocations = " / ".join(f"{ticker} {selected['weights'][ticker]:.2%}" for ticker in TICKERS)
    design, test = selected["period"], result["period"]
    nav_chart = chart(result["baseline"]["curve"], result["candidate"]["curve"], "nav", "Test-period portfolio value")
    dd_chart = chart(result["baseline"]["curve"], result["candidate"]["curve"], "drawdown", "Test-period drawdown")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ETF portfolio research</title><style>
body{{margin:0;background:#f4f7fa;color:#183045;font:17px/1.6 system-ui,sans-serif}}main{{max-width:1040px;margin:auto;padding:32px 20px 64px}}h1{{font-size:2.2rem;line-height:1.2}}h2{{font-size:1.4rem}}section{{background:white;border:1px solid #d9e2eb;border-radius:12px;padding:24px;margin:22px 0}}table{{border-collapse:collapse;width:100%}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #d9e2eb}}td:nth-last-child(-n+2){{font-variant-numeric:tabular-nums;white-space:nowrap}}.table{{overflow-x:auto}}svg{{width:100%;height:auto}}svg text{{font:14px system-ui,sans-serif}}code{{overflow-wrap:anywhere}}.pending{{border-left:4px solid #b76d16;padding-left:16px}}small{{font-size:.9rem}}@media(max-width:600px){{main{{padding:20px 12px}}section{{padding:16px}}h1{{font-size:1.8rem}}}}
</style></head><body><main>
<h1>Can a simple ETF portfolio improve the return–drawdown trade-off?</h1>
<p>SPY, TLT and GLD · A retrospective historical experiment</p>
<section><h2>Frozen initial allocation</h2><p>{allocations}</p>
<p>{html.escape(selected['selection_message'])}</p>
<p>Design: {design['first_date']} to {design['last_date']} ({design['observations']} closes).<br>
Test: {test['first_date']} to {test['last_date']} ({test['observations']} closes).</p>
<p>Each window starts a separate portfolio at 100. Weights are initial allocations and drift during buy-and-hold.</p></section>
<section><h2>Return and drawdown</h2><div class="table"><table><thead><tr><th>Window</th><th>Portfolio</th><th>Total return</th><th>Maximum drawdown</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p><small>Total return covers the whole window and is not annualized. Maximum drawdown is nonpositive. A value nearer zero means a smaller loss from a preceding peak.</small></p></section>
<section><h2>Test-period portfolio value (starts at 100)</h2>{nav_chart}</section>
<section><h2>Test-period drawdown</h2>{dd_chart}</section>
<section class="pending"><h2>Team interpretation</h2><p>To complete: compare the candidate with the baseline within each window, explain whether the design-period advantage persisted in the test period, and name a condition or limitation that could change the conclusion. This starter page does not record student acceptance.</p></section>
<section><h2>Method, source and limits</h2><p>Search 66 long-only 10%-grid allocations plus the exact equal-weight baseline. Require design return at least equal to the baseline within 1e-12, then minimize drawdown loss. Ties prefer the baseline, higher return, and ascending SPY/TLT/GLD weights. Retain the baseline if there is no strictly smaller loss.</p>
<p>For each window, portfolio value is 100 × the sum of each initial weight × its adjusted-close ratio to the first close in that window. Drawdown is value / running peak − 1. No previous-window return enters the calculation.</p>
<p>Source: the frozen T2 <code>data/t2/daily_prices.csv</code>. See <code>data/t2/data_dictionary.md</code> for provenance and validation limits. Adjusted-close values follow the provider's split/distribution convention. No additional fund-fee deduction, trading cost, slippage or tax is modeled.</p>
<p>Both periods were already available in the course data. This is a retrospective holdout with a procedural freeze, not a blinded market test. Three assets, one historical split and a small grid cannot establish a universally best strategy. Hypothetical results do not guarantee future profits.</p>
<p>Source SHA-256: <code>{html.escape(selected['source_sha256'])}</code><br>Frozen candidate SHA-256: <code>{html.escape(result['candidate_sha256'])}</code></p></section>
</main></body></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="split the unchanged source into design/test JSON inputs")
    prepare_parser.add_argument("--csv", required=True)
    prepare_parser.add_argument("--out-dir", required=True)
    for name in ("baseline", "optimize"):
        sub = commands.add_parser(name)
        sub.add_argument("--design", required=True)
        sub.add_argument("--out", required=True)
    evaluate_parser = commands.add_parser("evaluate", help="use the frozen candidate after human approval")
    evaluate_parser.add_argument("--test", required=True)
    evaluate_parser.add_argument("--candidate", required=True)
    evaluate_parser.add_argument("--expected-candidate-sha256", required=True,
                                 help="hash explicitly approved in chat before the test is opened")
    evaluate_parser.add_argument("--out", required=True)
    page_parser = commands.add_parser("page", help="build a static page for team interpretation")
    for name in ("baseline", "candidate", "evaluation", "out"):
        page_parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare(args.csv, args.out_dir)
            print("Created design.json, test.json and manifest.json in " + args.out_dir)
        else:
            if Path(args.out).exists():
                fail("Output already exists: " + args.out)
            if args.command == "baseline":
                output = json_bytes(baseline(args.design))
            elif args.command == "optimize":
                output = json_bytes(optimize(args.design))
            elif args.command == "evaluate":
                output = json_bytes(evaluate(args.test, args.candidate, args.expected_candidate_sha256))
            else:
                output = page(args.baseline, args.candidate, args.evaluation).encode()
            write_new(args.out, output)
            print("Created " + args.out)
            if args.command == "optimize":
                candidate = json.loads(output)
                print("Candidate SHA-256: " + sha256(output))
                print("Initial weights: " + json.dumps(candidate["weights"]))
                print("Design metrics (decimal fractions): " + json.dumps(candidate["metrics"]))
                print("Stop for human approval before test evaluation.")
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, "Error: " + str(error) + "\n")


if __name__ == "__main__":
    main()
