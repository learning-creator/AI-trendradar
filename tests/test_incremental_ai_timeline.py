from pathlib import Path
import re
import unittest

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


class IncrementalAITimelineTest(unittest.TestCase):
    def test_incremental_push_windows_enable_current_ai_analysis(self):
        timeline_path = Path(__file__).resolve().parents[1] / "config" / "timeline.yaml"
        timeline_text = timeline_path.read_text(encoding="utf-8")

        if yaml is None:
            self._assert_known_incremental_windows(timeline_text)
            return

        timeline = yaml.safe_load(timeline_text)

        incremental_windows = []

        for preset_name, preset in timeline.get("presets", {}).items():
            default = preset.get("default", {})
            if default.get("report_mode") == "incremental" and default.get("push") is True:
                incremental_windows.append((f"presets.{preset_name}.default", default))

            for period_name, period in preset.get("periods", {}).items():
                merged = {**default, **period}
                if merged.get("report_mode") == "incremental" and merged.get("push") is True:
                    incremental_windows.append(
                        (f"presets.{preset_name}.periods.{period_name}", merged)
                    )

        custom = timeline.get("custom", {})
        custom_default = custom.get("default", {})
        if custom_default.get("report_mode") == "incremental" and custom_default.get("push") is True:
            incremental_windows.append(("custom.default", custom_default))

        for period_name, period in custom.get("periods", {}).items():
            merged = {**custom_default, **period}
            if merged.get("report_mode") == "incremental" and merged.get("push") is True:
                incremental_windows.append((f"custom.periods.{period_name}", merged))

        self.assertTrue(incremental_windows)
        for name, config in incremental_windows:
            with self.subTest(window=name):
                self.assertIs(config.get("analyze"), True)
                self.assertEqual(config.get("ai_mode"), "current")

    def _assert_known_incremental_windows(self, timeline_text):
        windows = {
            "presets.always_on.default": r"always_on:\n(?P<body>.*?)(?=\n\s+periods:)",
            "presets.office_hours.periods.weekend_free": r"weekend_free:\n(?P<body>.*?)(?=\n\s+day_plans:)",
            "custom.periods.weekday_morning": r"weekday_morning:\n(?P<body>.*?)(?=\n\s+weekend_morning:)",
        }

        for name, pattern in windows.items():
            with self.subTest(window=name):
                match = re.search(pattern, timeline_text, re.DOTALL)
                self.assertIsNotNone(match)
                body = match.group("body")
                self.assertIn('report_mode: "incremental"', body)
                self.assertIn("analyze: true", body)
                self.assertIn('ai_mode: "current"', body)


if __name__ == "__main__":
    unittest.main()
