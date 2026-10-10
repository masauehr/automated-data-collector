import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import tsunami_guard as g  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 10, 9, 40, tzinfo=JST)


def item(kind, rdt="2026-10-10T03:37:00+09:00", eid="e1", ift="発表", ttl="津波予報", anm="中米", ser=0):
    return {"eid": eid, "rdt": rdt, "ift": ift, "ttl": ttl, "anm": anm, "ser": ser, "kind": [{"code": "100", "kind": kind}]}


class TestClassify(unittest.TestCase):
    def test_none(self):
        self.assertEqual(g.classify([], NOW)["level"], "なし")

    def test_forecast_only(self):
        st = g.classify([item("津波予報（若干の海面変動）")], NOW)
        self.assertEqual(st["level"], "津波予報")
        self.assertIn("津波予報（若干の海面変動）", st["sentence"])
        self.assertNotIn("警報", st["sentence"])

    def test_advisory_warning_major(self):
        for kind in ("津波注意報", "津波警報", "大津波警報"):
            self.assertEqual(g.classify([item(kind, ttl="津波警報・注意報・予報")], NOW)["level"], kind)

    def test_highest_wins(self):
        st = g.classify([item("津波注意報", eid="a"), item("津波警報", eid="b")], NOW)
        self.assertEqual(st["level"], "津波警報")

    def test_stale_forecast_ignored(self):
        old = item("津波予報（若干の海面変動）", rdt="2026-09-30T10:00:00+09:00")
        self.assertEqual(g.classify([old], NOW)["level"], "なし")

    def test_cancel_after_warning_same_event(self):
        w = item("津波警報", rdt="2026-10-10T01:00:00+09:00", eid="e1", ser=0)
        c = item("津波警報解除", rdt="2026-10-10T05:00:00+09:00", eid="e1", ser=1, ift="解除")
        self.assertEqual(g.classify([w, c], NOW)["level"], "なし")

    def test_downgrade_warning_to_advisory(self):
        w = item("津波警報", rdt="2026-10-10T01:00:00+09:00", eid="e1", ser=0)
        a = item("津波注意報", rdt="2026-10-10T05:00:00+09:00", eid="e1", ser=1)
        self.assertEqual(g.classify([w, a], NOW)["level"], "津波注意報")

    def test_unknown_kind_is_not_ignored(self):
        self.assertEqual(g.classify([item("未知の種別X")], NOW)["level"], "不明")

    def test_fetch_failure_is_not_none(self):
        st = g.classify(None, NOW)
        self.assertEqual(st["level"], "取得失敗")
        self.assertIn("取得できません", st["sentence"])


class TestCheckText(unittest.TestCase):
    forecast = g.classify([item("津波予報（若干の海面変動）")], NOW)
    none = g.classify([], NOW)

    def test_none_must_not_mention(self):
        self.assertTrue(g.check_text("🤖今日は晴れ。津波の心配なし", self.none))
        self.assertEqual(g.check_text("🤖今日は晴れ", self.none), [])

    def test_forecast_requires_fixed_sentence(self):
        ok = "🤖今日は晴れ\n" + self.forecast["sentence"]
        self.assertEqual(g.check_text(ok, self.forecast), [])
        self.assertTrue(g.check_text("🤖今日は晴れ", self.forecast))  # 見落とし

    def test_overstatement_rejected(self):
        for bad in ("🤖津波警報が発表", "🤖中米の地震で津波が発生", "🤖津波が到達"):
            self.assertTrue(g.check_text(bad, self.forecast), bad)
        extra = "🤖津波に警戒\n" + self.forecast["sentence"]
        self.assertTrue(g.check_text(extra, self.forecast))  # 固定文以外の津波記述

    def test_fetch_failure_requires_notice(self):
        st = g.classify(None, NOW)
        self.assertTrue(g.check_text("🤖津波の心配なし", st))
        self.assertEqual(g.check_text("🤖晴れ\n" + st["sentence"], st), [])


if __name__ == "__main__":
    unittest.main()
