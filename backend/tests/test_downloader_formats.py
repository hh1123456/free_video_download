import unittest

from app.downloader import _format_for


class FormatSelectionTests(unittest.TestCase):
    def test_bounded_quality_falls_back_to_lowest_available_stream(self) -> None:
        fmt = _format_for(480)

        self.assertIn("bestvideo[height<=480]", fmt)
        self.assertIn("worstvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]", fmt)
        self.assertIn("worstvideo+bestaudio", fmt)


if __name__ == "__main__":
    unittest.main()
