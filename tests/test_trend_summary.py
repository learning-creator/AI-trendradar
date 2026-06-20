from datetime import date
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "trendradar" / "commands" / "trend_summary.py"
SPEC = importlib.util.spec_from_file_location("trend_summary_module", MODULE_PATH)
trend_summary = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = trend_summary
SPEC.loader.exec_module(trend_summary)

calculate_previous_period = trend_summary.calculate_previous_period
collect_stored_items = trend_summary.collect_stored_items


class DummyStorage:
    def __init__(self):
        self.news_by_date = {}
        self.rss_by_date = {}

    def get_today_all_data(self, date_str=None):
        return self.news_by_date.get(date_str)

    def get_rss_data(self, date_str=None):
        return self.rss_by_date.get(date_str)


class TrendSummaryTest(unittest.TestCase):
    def test_previous_complete_period_boundaries(self):
        self.assertEqual(
            calculate_previous_period("weekly", date(2026, 6, 20)),
            (date(2026, 6, 8), date(2026, 6, 14)),
        )
        self.assertEqual(
            calculate_previous_period("monthly", date(2026, 6, 20)),
            (date(2026, 5, 1), date(2026, 5, 31)),
        )
        self.assertEqual(
            calculate_previous_period("quarterly", date(2026, 6, 20)),
            (date(2026, 1, 1), date(2026, 3, 31)),
        )
        self.assertEqual(
            calculate_previous_period("semiannual", date(2026, 8, 1)),
            (date(2026, 1, 1), date(2026, 6, 30)),
        )
        self.assertEqual(
            calculate_previous_period("yearly", date(2026, 6, 20)),
            (date(2025, 1, 1), date(2025, 12, 31)),
        )

    def test_collect_stored_items_reads_multiple_dates_and_deduplicates(self):
        storage = DummyStorage()
        storage.news_by_date["2026-06-08"] = SimpleNamespace(
            items={
                "source-a": [
                    SimpleNamespace(
                        title="China growth signal",
                        url="https://example.com/a",
                        mobile_url="",
                        count=2,
                        rank=3,
                    )
                ]
            },
            id_to_name={"source-a": "Source A"},
        )
        storage.news_by_date["2026-06-09"] = SimpleNamespace(
            items={
                "source-a": [
                    SimpleNamespace(
                        title="China growth signal",
                        url="https://example.com/a",
                        mobile_url="",
                        count=1,
                        rank=1,
                    )
                ]
            },
            id_to_name={"source-a": "Source A"},
        )
        storage.rss_by_date["2026-06-09"] = SimpleNamespace(
            items={
                "wsj-world": [
                    SimpleNamespace(
                        title="Global economy update",
                        url="https://example.com/rss",
                        summary="A short summary.",
                        count=1,
                    )
                ]
            },
            id_to_name={"wsj-world": "WSJ World News"},
        )

        hotlist, rss, loaded_dates = collect_stored_items(
            storage,
            date(2026, 6, 8),
            date(2026, 6, 14),
        )

        self.assertEqual(loaded_dates, ["2026-06-08", "2026-06-09"])
        self.assertEqual(len(hotlist), 1)
        self.assertEqual(hotlist[0].count, 3)
        self.assertEqual(hotlist[0].best_rank, 1)
        self.assertEqual(hotlist[0].days, {"2026-06-08", "2026-06-09"})
        self.assertEqual(len(rss), 1)
        self.assertEqual(rss[0].source_name, "WSJ World News")


if __name__ == "__main__":
    unittest.main()
