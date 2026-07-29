import unittest

from app.chinese import to_simplified_chinese


class ChineseConversionTests(unittest.TestCase):
    def test_converts_traditional_chinese_to_simplified(self) -> None:
        self.assertEqual(to_simplified_chinese("繁體字幕，下載後可以閱讀。"), "繁体字幕，下载后可以阅读。")

    def test_preserves_non_chinese_text(self) -> None:
        self.assertEqual(to_simplified_chinese("Agent demo 123"), "Agent demo 123")


if __name__ == "__main__":
    unittest.main()
