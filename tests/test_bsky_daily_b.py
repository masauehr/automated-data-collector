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


class TestWarningForecast(unittest.TestCase):
    def test_unbacked_prediction_rejected(self):
        f = {"warnings": "（警報・特別警報の発表中なし）", "warn_outlook": []}
        self.assertTrue(b.validate_warning_forecast("🤖x\ny\n明日の波浪警報に備え、強風にも警戒を。", f))

    def test_other_phrasing_rejected(self):
        f = {"warnings": "（警報・特別警報の発表中なし）", "warn_outlook": []}
        self.assertTrue(b.validate_warning_forecast("🤖x\ny\n波浪警報22日発表予定。", f))

    def test_prediction_allowed_with_outlook(self):
        f = {"warnings": "（警報・特別警報の発表中なし）", "warn_outlook": ["波"]}
        self.assertEqual(b.validate_warning_forecast("🤖x\ny\n明日の波浪警報に備え。", f), [])

    def test_active_warning_and_plain_mention_allowed(self):
        f = {"warnings": "新潟県: 大雨警報（発表）", "warn_outlook": []}
        self.assertEqual(b.validate_warning_forecast("🤖x\ny\n新潟で大雨警報が発表中。明日にかけて大雨警報に引き続き警戒。", f), [])
        self.assertEqual(b.validate_warning_forecast("🤖x\ny\n警報級の可能性あり。", {}), [])

    def test_outlook_kinds_parse(self):
        txt = "うるま市・波  注 注 警 注\n那覇市・風  注 注 ・ ・\n久米島町・波高(m)  1 2"
        self.assertEqual(b._outlook_kinds(txt), {"波"})


if __name__ == "__main__":
    unittest.main()


class TestRainPop(unittest.TestCase):
    fc = "■ 天気\n  10月15日(木): 晴れ\n■ 降水確率\n  10月15日(木): 12-18h:10% 18-24h:20%\n  10月16日(金): 0-6h:70%\n"

    def test_today_pop_takes_first_day_max(self):
        self.assertEqual(b._today_pop(self.fc), 20)
        self.assertIsNone(b._today_pop("■ 天気\n  晴れ"))

    def test_low_pop_rain_rejected(self):
        f = {"pop": {"473000": 10, "474000": 10}}
        self.assertTrue(b.validate_rain_pop("🤖x\n沖縄先島は湿った空気で雨\ny", f))

    def test_high_pop_ok(self):
        f = {"pop": {"473000": 60, "474000": 10}}
        self.assertEqual(b.validate_rain_pop("🤖x\n先島は雨\ny", f), [])

    def test_tomorrow_and_unknown_are_skipped(self):
        f = {"pop": {"473000": 10, "474000": 10}}
        self.assertEqual(b.validate_rain_pop("🤖x\n先島は明日雨\ny", f), [])
        self.assertEqual(b.validate_rain_pop("🤖x\n先島は雨\ny", {"pop": {"473000": None, "474000": None}}), [])
        self.assertEqual(b.validate_rain_pop("🤖x\n先島は雨\ny", {}), [])

    def test_sakishima_uses_its_own_pop_not_okinawa(self):
        f = {"pop": {"471000": 80, "473000": 10, "474000": 10}}
        self.assertTrue(b.validate_rain_pop("🤖x\n沖縄先島は雨\ny", f))

    def test_local_rain_ok_but_dominant_rain_rejected(self):
        f = {"pop": {"471000": 20, "472000": 20}}
        for w in ("沖縄は局地的にわか雨", "沖縄は所により雨", "沖縄はところにより雨", "沖縄は局地的に強い雨", "沖縄は曇りや雨の所あり"):
            self.assertEqual(b.validate_rain_pop(f"🤖x\n{w}\ny", f), [], w)
        for w in ("沖縄は曇り時々雨", "沖縄は曇りのち雨", "沖縄は雨"):
            self.assertTrue(b.validate_rain_pop(f"🤖x\n{w}\ny", f), w)

    def test_other_date_clause_skipped(self):
        from datetime import datetime
        f = {"pop": {"011000": 10, "012000": 10, "016000": 10}}
        d = (b.datetime.now(b.JST).day % 28) + 1  # 今日と別の日
        self.assertEqual(b.validate_rain_pop(f"🤖x\n{d}日は北海道で一時雨\ny", f), [])
        self.assertTrue(b.validate_rain_pop(f"🤖x\n{b.datetime.now(b.JST).day}日は北海道で雨\ny", f))


class TestNotifyText(unittest.TestCase):
    base = {"date": "2026-10-16", "generated_at": "2026-10-16T09:42:02+09:00", "text": "🤖x\ny\nz", "problems": []}

    def test_success_skipped_failed(self):
        ok = b._notify_text({**self.base, "posted": True, "post_result": "投稿完了: at://x"})
        self.assertIn("投稿しました", ok)
        sk = b._notify_text({**self.base, "posted": False, "post_skipped": "不合格", "problems": ["沖縄が雨"]})
        self.assertIn("見送り", sk); self.assertIn("沖縄が雨", sk); self.assertIn("再実行", sk)
        ng = b._notify_text({**self.base, "posted": False, "post_result": "認証エラー"})
        self.assertIn("失敗", ng); self.assertIn("認証エラー", ng)


class TestTropicalDepression(unittest.TestCase):
    def test_fix_td_name(self):
        self.assertEqual(b.fix_td_name("■ 台風a号　発表\n実況: 熱帯低気圧"), "■ 熱帯低気圧　発表\n実況: 熱帯低気圧")
        self.assertEqual(b.fix_td_name("台風29号（コグマ）"), "台風29号（コグマ）")

    def test_td_written_as_typhoon_rejected(self):
        self.assertTrue(any("熱帯低気圧" in x for x in b.validate("🤖x\ny\n台風a号は日本に影響なし", {"typhoon": "熱帯低気圧", "warnings": "（警報・特別警報の発表中なし）"})))

    def test_rain_belongs_to_nearest_region(self):
        f = {"pop": {"011000": 80, "012000": 80, "016000": 80, "473000": 10, "474000": 10}}
        self.assertEqual(b.validate_rain_pop("🤖x\n北海道の雷雨と先島の高波に注意\ny", f), [])
        self.assertTrue(b.validate_rain_pop("🤖x\n北海道は晴れ、先島は雨\ny", f))