import unittest

from app.downloader import _base_opts, friendly_error


class DownloaderErrorTests(unittest.TestCase):
    def test_douyin_opts_do_not_send_bilibili_origin_headers(self) -> None:
        headers = _base_opts("https://v.douyin.com/xujb7b1B7IQ")["http_headers"]

        self.assertNotIn("Referer", headers)
        self.assertNotIn("Origin", headers)

    def test_bilibili_opts_keep_bilibili_origin_headers(self) -> None:
        headers = _base_opts("https://www.bilibili.com/video/BV1mAAmzqEfP")["http_headers"]

        self.assertEqual(headers["Referer"], "https://www.bilibili.com/")
        self.assertEqual(headers["Origin"], "https://www.bilibili.com")

    def test_winerror_10013_is_translated(self) -> None:
        exc = Exception(
            "ERROR: [BiliBili] x: Unable to download webpage: [WinError 10013] "
            "以一种访问权限不允许的方式做了一个访问套接字的尝试。"
        )
        msg = friendly_error(exc)
        self.assertIn("网络", msg)
        self.assertIn("10013", msg)


if __name__ == "__main__":
    unittest.main()
