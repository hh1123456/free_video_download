import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import config
from app.downloader import _base_opts, friendly_error, normalize_video_url


class DownloaderErrorTests(unittest.TestCase):
    def test_douyin_opts_do_not_send_bilibili_origin_headers(self) -> None:
        headers = _base_opts("https://v.douyin.com/xujb7b1B7IQ")["http_headers"]

        self.assertNotIn("Referer", headers)
        self.assertNotIn("Origin", headers)

    def test_bilibili_opts_keep_bilibili_origin_headers(self) -> None:
        headers = _base_opts("https://www.bilibili.com/video/BV1mAAmzqEfP")["http_headers"]

        self.assertEqual(headers["Referer"], "https://www.bilibili.com/")
        self.assertEqual(headers["Origin"], "https://www.bilibili.com")

    def test_get_cookies_file_prefers_douyin_cookie_for_douyin_urls(self) -> None:
        with TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            cookies_dir = base_dir / "backend" / "cookies"
            cookies_dir.mkdir(parents=True)
            douyin_cookie = cookies_dir / "douyin.txt"
            douyin_cookie.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            bilibili_cookie = cookies_dir / "bilibili.txt"
            bilibili_cookie.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

            with patch.object(config, "BASE_DIR", base_dir):
                self.assertEqual(
                    config.get_cookies_file("https://www.douyin.com/video/7667735259081506659"),
                    str(douyin_cookie),
                )

    def test_get_cookies_file_prefers_bilibili_cookie_for_bilibili_urls(self) -> None:
        with TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            cookies_dir = base_dir / "backend" / "cookies"
            cookies_dir.mkdir(parents=True)
            douyin_cookie = cookies_dir / "douyin.txt"
            douyin_cookie.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            bilibili_cookie = cookies_dir / "bilibili.txt"
            bilibili_cookie.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

            with patch.object(config, "BASE_DIR", base_dir):
                self.assertEqual(
                    config.get_cookies_file("https://www.bilibili.com/video/BV1mAAmzqEfP"),
                    str(bilibili_cookie),
                )

    def test_douyin_modal_url_normalizes_to_video_url(self) -> None:
        url = (
            "https://www.douyin.com/user/self?from_tab_name=main"
            "&modal_id=7667735259081506659&showTab=favorite_collection"
        )

        self.assertEqual(
            normalize_video_url(url),
            "https://www.douyin.com/video/7667735259081506659",
        )

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
