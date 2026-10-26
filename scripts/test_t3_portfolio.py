"""Synthetic checks for the T3 starter. Run: python3 scripts/test_t3_portfolio.py"""

import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import t3_portfolio as tool


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, mutation=None):
        dates = ["2021-08-31", "2021-09-01", "2024-08-30",
                 "2024-09-03", "2026-08-31", "2026-09-01"]
        rows = [{"date": day, "ticker": ticker, "adjusted_close": 100 + i}
                for ticker in tool.TICKERS for i, day in enumerate(dates)]
        if mutation:
            mutation(rows)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["date", "ticker", "adjusted_close"])
        writer.writeheader()
        writer.writerows(rows)
        path = self.root / "prices.csv"
        path.write_text(buffer.getvalue())
        return path

    def inputs(self):
        directory = self.root / "inputs"
        tool.prepare(self.source(), directory)
        return directory / "design.json", directory / "test.json"

    def flat_design(self):
        design_path, _ = self.inputs()
        data, _ = tool.read_json(design_path)
        data["prices"] = {ticker: [100, 100] for ticker in tool.TICKERS}
        design_path.write_bytes(tool.json_bytes(data))
        return design_path

    def test_grid_contains_66_triples_and_exact_baseline(self):
        weights = tool.candidates()
        self.assertEqual(len(weights), 67)
        self.assertEqual(len({tuple(w[t] for t in tool.TICKERS) for w in weights}), 67)
        self.assertEqual(weights[-1], tool.BASELINE)
        for allocation in weights:
            tool.validate_weights(allocation)

    def test_date_boundaries_and_independent_normalization(self):
        design_path, test_path = self.inputs()
        design, _ = tool.read_json(design_path)
        test, _ = tool.read_json(test_path)
        self.assertEqual(design["dates"], ["2021-09-01", "2024-08-30"])
        self.assertEqual(test["dates"], ["2024-09-03", "2026-08-31"])
        result = tool.backtest(test, tool.BASELINE)
        self.assertEqual(result["curve"][0]["nav"], 100)
        self.assertAlmostEqual(result["metrics"]["total_return"], 104 / 103 - 1)

    def test_flat_prices_retain_baseline(self):
        result = tool.optimize(self.flat_design())
        self.assertEqual(result["weights"], tool.BASELINE)
        self.assertEqual(result["metrics"], {"total_return": 0.0, "max_drawdown": 0.0})
        self.assertFalse(result["improved_design_drawdown"])
        self.assertEqual(result["eligible_count"], 67)

    def test_drawdown_sign_and_peak_order(self):
        data = {"dates": ["2022-01-03", "2022-01-04", "2022-01-05", "2022-01-06"],
                "prices": {ticker: [100, 120, 90, 110] for ticker in tool.TICKERS}}
        result = tool.backtest(data, tool.BASELINE)
        self.assertAlmostEqual(result["metrics"]["max_drawdown"], -0.25)
        self.assertAlmostEqual(result["metrics"]["total_return"], 0.10)
        self.assertTrue(all(point["drawdown"] <= 0 for point in result["curve"]))

    def test_buy_and_hold_is_not_daily_rebalancing(self):
        data = {"dates": ["2022-01-03", "2022-01-04", "2022-01-05"],
                "prices": {"SPY": [100, 200, 100], "TLT": [100, 100, 200], "GLD": [100, 100, 100]}}
        result = tool.backtest(data, {"SPY": 0.5, "TLT": 0.5, "GLD": 0.0})
        self.assertAlmostEqual(result["curve"][-1]["nav"], 150)
        self.assertNotAlmostEqual(result["curve"][-1]["nav"], 187.5)

    def test_optimizer_only_reads_design(self):
        design_path = self.flat_design()
        original = Path.read_bytes
        opened = []
        def record_read(path):
            opened.append(path)
            return original(path)
        with patch.object(Path, "read_bytes", record_read):
            tool.optimize(design_path)
        self.assertEqual(opened, [design_path])

    def test_ties_prefer_higher_return_then_ascending_weights(self):
        path = self.flat_design()
        choices = [(0.0, 0.5, 0.5), (0.2, 0.4, 0.4), (0.3, 0.3, 0.4)]
        def result(_, weights):
            key = tuple(weights[t] for t in tool.TICKERS)
            if weights == tool.BASELINE:
                ret, drawdown = 0.2, -0.3
            elif key in choices:
                ret, drawdown = (0.4 if key != choices[-1] else 0.3), -0.1
            else:
                ret, drawdown = 0.1, -0.05
            return {"weights": weights, "metrics": {"total_return": ret, "max_drawdown": drawdown}, "curve": []}
        with patch.object(tool, "backtest", result):
            selected = tool.optimize(path)
        self.assertEqual(tuple(selected["weights"][t] for t in tool.TICKERS), choices[0])

    def test_evaluation_hashes_without_changing_candidate(self):
        design_path, test_path = self.inputs()
        candidate_path = self.root / "candidate.json"
        frozen = tool.json_bytes(tool.optimize(design_path))
        candidate_path.write_bytes(frozen)
        result = tool.evaluate(test_path, candidate_path, tool.sha256(frozen))
        self.assertEqual(result["candidate_sha256"], tool.sha256(frozen))
        self.assertEqual(candidate_path.read_bytes(), frozen)
        self.assertEqual(result["candidate"]["curve"][0]["nav"], 100)

    def test_hash_mismatch_does_not_open_test(self):
        design_path, test_path = self.inputs()
        candidate_path = self.root / "candidate.json"
        candidate_path.write_bytes(tool.json_bytes(tool.optimize(design_path)))
        original = Path.read_bytes
        opened = []
        def record_read(path):
            opened.append(path)
            return original(path)
        with patch.object(Path, "read_bytes", record_read), self.assertRaises(ValueError):
            tool.evaluate(test_path, candidate_path, "0" * 64)
        self.assertEqual(opened, [candidate_path])

    def test_invalid_weights(self):
        invalid = [{"SPY": 0.5, "TLT": 0.5}, {"SPY": -0.1, "TLT": 0.6, "GLD": 0.5},
                   {"SPY": 1, "TLT": 1, "GLD": 1}, {"SPY": float("nan"), "TLT": 0, "GLD": 1},
                   {"SPY": True, "TLT": 0, "GLD": 0}]
        for weights in invalid:
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                tool.validate_weights(weights)

    def test_bad_source_rows(self):
        changes = [lambda rows: rows.append(dict(rows[0])), lambda rows: rows.pop(),
                   lambda rows: rows[0].update(adjusted_close="nan"),
                   lambda rows: rows[0].update(adjusted_close=0),
                   lambda rows: rows[0].update(adjusted_close=-2)]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                tool.prepare(self.source(change), self.root / "bad-inputs")

    def test_empty_window(self):
        def remove_test(rows):
            rows[:] = [row for row in rows if row["date"] < "2024-09-01"]
        with self.assertRaises(ValueError):
            tool.prepare(self.source(remove_test), self.root / "empty-inputs")

    def test_existing_output_is_preserved(self):
        design_path, _ = self.inputs()
        before = design_path.read_bytes()
        with self.assertRaises(ValueError):
            tool.prepare(self.root / "prices.csv", design_path.parent)
        self.assertEqual(design_path.read_bytes(), before)

    def test_page_contains_two_curves_and_detects_candidate_change(self):
        design_path, test_path = self.inputs()
        base_path = self.root / "baseline.json"
        candidate_path = self.root / "candidate.json"
        evaluation_path = self.root / "evaluation.json"
        base_path.write_bytes(tool.json_bytes(tool.baseline(design_path)))
        candidate_path.write_bytes(tool.json_bytes(tool.optimize(design_path)))
        evaluation_path.write_bytes(tool.json_bytes(tool.evaluate(
            test_path, candidate_path, tool.sha256(candidate_path.read_bytes()))))
        rendered = tool.page(base_path, candidate_path, evaluation_path)
        self.assertEqual(rendered.count("<svg "), 2)
        self.assertEqual(rendered.count("<polyline "), 4)
        self.assertIn("Team interpretation", rendered)
        candidate_path.write_bytes(candidate_path.read_bytes() + b"\n")
        with self.assertRaises(ValueError):
            tool.page(base_path, candidate_path, evaluation_path)


if __name__ == "__main__":
    unittest.main()
