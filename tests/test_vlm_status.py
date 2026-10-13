import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import vlm_status as v  # noqa: E402


class TestStripTyphoon(unittest.TestCase):
    def test_removes_typhoon_sentences(self):
        t = "高気圧に覆われ晴れ。南海上には台風28号(994hPa)があります。奄美は気圧の谷で雨。"
        self.assertEqual(v.strip_typhoon(t), "高気圧に覆われ晴れ。奄美は気圧の谷で雨。")

    def test_removes_abbreviated_and_tropical(self):
        t = "北海道は低気圧が接近。台28号は低気圧化し本州南岸に近づく。熱帯低気圧が発生。週末は変化に注意。"
        self.assertEqual(v.strip_typhoon(t), "北海道は低気圧が接近。週末は変化に注意。")

    def test_no_typhoon_unchanged(self):
        self.assertEqual(v.strip_typhoon("晴れ。雨。"), "晴れ。雨。")

    def test_empty(self):
        self.assertEqual(v.strip_typhoon(""), "")
        self.assertIsNone(v.strip_typhoon(None))


class TestNgHandling(unittest.TestCase):
    def _run(self, checks):
        import json, tempfile
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
        t = Path(tempfile.mkdtemp()); (t / today).mkdir()
        d = {"date": today, "confidence": 0.7, "pattern": "移動性高気圧", "general": {"today": "晴れ。", "tomorrow": "曇り。"},
             "guardrail_checks": checks}
        (t / today / "data.json").write_text(json.dumps(d))
        old, v.ROOT = v.ROOT, t
        try:
            return v.main()
        finally:
            v.ROOT = old

    def test_rain_ng_is_soft(self):
        r = self._run([{"verdict": "NG", "label": "実況突合:降水"}])
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["soft_ng"], ["実況突合:降水"])

    def test_label_and_season_ng_are_fatal(self):
        for label in ("ラベル許可リスト", "季節整合"):
            self.assertEqual(self._run([{"verdict": "NG", "label": label}])["status"], "fail")


if __name__ == "__main__":
    unittest.main()
