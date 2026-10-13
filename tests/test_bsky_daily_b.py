import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
sys.path.insert(0, "/Users/masahiro/projects/jma_mcp")
import bsky_daily_b as b  # noqa: E402

CALM = {"warnings": "（警報・特別警報の発表中なし）", "typhoon": "台風29号"}
VLM_TROUGH = {"status": "ok", "troughs": [{"location": "沖縄付近"}]}


class TestTone(unittest.TestCase):
    def test_overstatement_without_warning(self):
        for w in ("厳重警戒", "暴風", "猛烈"):
            self.assertTrue(b.validate_tone(f"🤖x\n晴れ\n台風29号は{w}", CALM), w)

    def test_allowed_when_warning_active(self):
        f = {"warnings": "沖縄本島地方: 暴風警報（発表）"}
        self.assertEqual(b.validate_tone("🤖x\n雨\n暴風に厳重警戒", f), [])

    def test_long_line_rejected(self):
        self.assertTrue(b.validate_tone("🤖x\n" + "あ" * 101 + "\ny", CALM))
        self.assertEqual(b.validate_tone("🤖x\n" + "あ" * 100 + "\ny", CALM), [])

    def test_typhoon_first_line_rejected(self):
        self.assertTrue(b.validate_tone("🤖台風29号が北上\n晴れ\n特になし", CALM))

    def test_trough_must_be_mentioned(self):
        self.assertTrue(b.validate_tone("🤖高気圧で晴れ\n関東は曇り\n台風は離れる", CALM, VLM_TROUGH))
        self.assertEqual(b.validate_tone("🤖高気圧で晴れ\n沖縄は気圧の谷で雨\n台風は離れる", CALM, VLM_TROUGH), [])

    def test_no_trough_no_requirement(self):
        self.assertEqual(b.validate_tone("🤖高気圧で晴れ\n関東は曇り\n台風は離れる", CALM, {"status": "ok", "troughs": []}), [])


class TestHeavyRain(unittest.TestCase):
    rain = "■ 1時間降水量の日最大値（5mm以上のみ）\n  1  沖縄県  久米島町  北原  13.5  07:35"

    def test_heavy_rain_word_needs_evidence(self):
        f = dict(CALM, rain=self.rain)
        self.assertTrue(b.validate_tone("🤖x\n九州南部に大雨注意\ny", f))

    def test_ok_with_warning_or_30mm(self):
        self.assertEqual(b.validate_tone("🤖x\n大雨に注意\ny", {"warnings": "鹿児島県: 大雨警報", "rain": self.rain}), [])
        strong = "■ 1時間降水量の日最大値\n  1  鹿児島県  屋久島  尾之間  42.0  05:10"
        self.assertEqual(b.validate_tone("🤖x\n大雨に注意\ny", dict(CALM, rain=strong)), [])

    def test_max_rain_parser(self):
        self.assertEqual(b._max_rain_1h(self.rain), 13.5)
        self.assertEqual(b._max_rain_1h(""), 0.0)


class TestParsers(unittest.TestCase):
    def test_body_strips_headers(self):
        self.assertEqual(b._body("【東京都 天気概況】\n\n　晴れ。\n出典: 気象庁"), "晴れ。")

    def test_rain_sections_only(self):
        t = "■ 日最高気温の高い方から\n 1 a 30.0\n■ 1時間降水量の多い方から\n 1 久米島 4.5\n 2 x 1.0\n■ 最大風速\n 1 y 9"
        r = b._rain_sections(t)
        self.assertIn("久米島", r)
        self.assertNotIn("30.0", r)
        self.assertNotIn("最大風速", r)


if __name__ == "__main__":
    unittest.main()
