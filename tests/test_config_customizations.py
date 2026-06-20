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

    def test_timezone_is_valid_shanghai_timezone(self):
        self.assertEqual(self.config.get("app", {}).get("timezone"), "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
