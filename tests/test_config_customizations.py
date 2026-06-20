from pathlib import Path
import unittest

import yaml


class ConfigCustomizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        cls.config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    def test_finance_platform_sources_are_preserved(self):
        source_ids = [
            source.get("id")
            for source in self.config.get("platforms", {}).get("sources", [])
        ]

        for source_id in [
            "wallstreetcn-hot",
            "wallstreetcn-quick",
            "wallstreetcn-news",
            "cls-hot",
            "gelonghui",
            "xueqiu",
            "jin10",
            "fastbull",
        ]:
            with self.subTest(source_id=source_id):
                self.assertIn(source_id, source_ids)

    def test_ai_analysis_is_first_display_region(self):
        region_order = self.config.get("display", {}).get("region_order", [])
        self.assertGreater(len(region_order), 0)
        self.assertEqual(region_order[0], "ai_analysis")

    def test_ai_translation_batch_config_is_present(self):
        ai_translation = self.config.get("ai_translation", {})
        self.assertEqual(ai_translation.get("batch_size"), 100)
        self.assertEqual(ai_translation.get("batch_interval"), 2)

    def test_western_rss_sources_are_added_without_removing_existing_feeds(self):
        feed_ids = [
            feed.get("id")
            for feed in self.config.get("rss", {}).get("feeds", [])
        ]

        for existing_feed in ["hacker-news", "ruanyifeng", "yahoo-finance"]:
            with self.subTest(existing_feed=existing_feed):
                self.assertIn(existing_feed, feed_ids)

        for source_id in [
            "wsj-world",
            "wsj-markets",
            "ft-world",
            "nyt-world",
            "nyt-business",
            "bbc-world",
            "bbc-business",
            "guardian-china",
            "guardian-economics",
            "npr-world",
        ]:
            with self.subTest(source_id=source_id):
                self.assertIn(source_id, feed_ids)

    def test_rss_is_included_in_ai_analysis(self):
        ai_analysis = self.config.get("ai_analysis", {})
        self.assertIs(ai_analysis.get("include_rss"), True)

    def test_trend_summary_config_is_present(self):
        trend_summary = self.config.get("trend_summary", {})
        self.assertIs(trend_summary.get("enabled"), True)
        self.assertIs(trend_summary.get("include_hotlist"), True)
        self.assertIs(trend_summary.get("include_rss"), True)
        self.assertEqual(trend_summary.get("prompt_file"), "trend_summary_prompt.txt")

    def test_timezone_is_valid_shanghai_timezone(self):
        self.assertEqual(self.config.get("app", {}).get("timezone"), "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
