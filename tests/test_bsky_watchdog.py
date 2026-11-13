import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import bsky_watchdog as w  # noqa: E402

NOW = datetime(2026, 11, 9, 10, 0, tzinfo=timezone(timedelta(hours=9)))


class TestWatchdog(unittest.TestCase):
    def test_no_alert_when_result_exists(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "2026-11-09_B.json").write_text("{}")
            self.assertIsNone(w.build_message(NOW, d, []))

    def test_alert_when_hung(self):
        with tempfile.TemporaryDirectory() as d:
            m = w.build_message(NOW, d, [(43620, "20:15", "python bsky_daily_b.py --post")])
            self.assertIn("PID 43620", m)
            self.assertIn("ハング", m)

    def test_alert_when_not_started(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("起動しなかった", w.build_message(NOW, d, []))

    def test_alert_when_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "2026-11-09_B.json").write_text('{"posted": false, "post_skipped": "機械検証で不合格のため投稿しない", "problems": ["裏付けのない「大雨」"]}')
            m = w.build_message(NOW, d, [])
            self.assertIn("まだ投稿されていません", m)
            self.assertIn("裏付けのない「大雨」", m)

    def test_no_alert_when_posted(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "2026-11-09_B.json").write_text('{"posted": true}')
            self.assertIsNone(w.build_message(NOW, d, []))

    def test_broken_json_does_not_alert(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "2026-11-09_B.json").write_text("{")
            self.assertIsNone(w.build_message(NOW, d, []))

    def test_yesterday_result_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "2026-11-08_B.json").write_text("{}")
            self.assertIsNotNone(w.build_message(NOW, d, []))


if __name__ == "__main__":
    unittest.main()
