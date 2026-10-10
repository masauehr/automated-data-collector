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


if __name__ == "__main__":
    unittest.main()
