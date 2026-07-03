import unittest
from unittest.mock import patch

from app import ai
from app.main import app
from fastapi.testclient import TestClient


class FetchTranscriptTests(unittest.TestCase):
    def test_extracts_bvid_from_bilibili_url(self) -> None:
        self.assertEqual(
            ai._extract_bilibili_bvid("https://bilibili.com/video/BV1mAAmzqEfP"),
            "BV1mAAmzqEfP",
        )

    def test_parses_bilibili_subtitle_json(self) -> None:
        data = {
            "body": [
                {"from": 1.2, "content": "第一句"},
                {"from": 3.8, "content": "第二句"},
            ]
        }

        self.assertEqual(
            ai._parse_bilibili_json_subtitle(data),
            [
                {"start": 1, "start_str": "0:01", "text": "第一句"},
                {"start": 3, "start_str": "0:03", "text": "第二句"},
            ],
        )

    def test_fetch_transcript_falls_back_to_bilibili_player_subtitles(self) -> None:
        fake_info = {
            "title": "demo",
            "duration": 10,
            "webpage_url": "https://bilibili.com/video/BV1mAAmzqEfP",
            "thumbnail": None,
            "extractor_key": "BiliBili",
            "subtitles": {},
            "automatic_captions": {},
        }
        segments = [{"start": 1, "start_str": "0:01", "text": "字幕内容"}]

        with patch.object(ai, "_base_opts", return_value={}), \
             patch.object(ai.yt_dlp, "YoutubeDL") as youtube_dl, \
             patch.object(ai, "_download_bilibili_player_subtitles", return_value=("zh", segments)):
            youtube_dl.return_value.__enter__.return_value.extract_info.return_value = fake_info

            result = ai.fetch_transcript("https://bilibili.com/video/BV1mAAmzqEfP")

        self.assertEqual(result["source"], "subtitle")
        self.assertEqual(result["lang"], "zh")
        self.assertEqual(result["segments"], segments)

    def test_fetch_transcript_uses_bilibili_subtitles_when_ytdlp_extract_fails(self) -> None:
        segments = [{"start": 1, "start_str": "0:01", "text": "字幕内容"}]

        with patch.object(ai, "_base_opts", return_value={}), \
             patch.object(ai.yt_dlp, "YoutubeDL") as youtube_dl, \
             patch.object(ai, "_download_bilibili_player_subtitles", return_value=("zh", segments)):
            youtube_dl.return_value.__enter__.return_value.extract_info.side_effect = Exception("ssl timeout")

            result = ai.fetch_transcript("https://bilibili.com/video/BV1mAAmzqEfP")

        self.assertEqual(result["source"], "subtitle")
        self.assertEqual(result["lang"], "zh")
        self.assertEqual(result["segments"], segments)

    def test_asr_hub_download_error_is_translated_to_actionable_message(self) -> None:
        fake_info = {
            "title": "demo",
            "duration": 10,
            "webpage_url": "https://www.bilibili.com/video/BV1dojW6uEn3",
            "thumbnail": None,
            "extractor_key": "BiliBili",
            "subtitles": {},
            "automatic_captions": {},
        }
        hub_error = Exception(
            "An error happened while trying to locate the file on the Hub and we cannot "
            "find the requested files in the local cache."
        )

        with patch.object(ai, "_base_opts", return_value={}), \
             patch.object(ai.yt_dlp, "YoutubeDL") as youtube_dl, \
             patch.object(ai.config, "ENABLE_ASR", True), \
             patch.object(ai, "_asr_transcribe", side_effect=hub_error):
            youtube_dl.return_value.__enter__.return_value.extract_info.return_value = fake_info

            with self.assertRaisesRegex(ValueError, "Whisper.*Hugging Face|Whisper.*模型"):
                ai.fetch_transcript("https://www.bilibili.com/video/BV1dojW6uEn3")

    def test_bilibili_without_subtitles_and_cookies_has_clear_guidance(self) -> None:
        fake_info = {
            "title": "demo",
            "duration": 10,
            "webpage_url": "https://www.bilibili.com/video/BV1dojW6uEn3",
            "thumbnail": None,
            "extractor_key": "BiliBili",
            "subtitles": {},
            "automatic_captions": {},
        }

        with patch.object(ai, "_base_opts", return_value={}), \
             patch.object(ai.yt_dlp, "YoutubeDL") as youtube_dl, \
             patch.object(ai.config, "ENABLE_ASR", False), \
             patch.object(ai, "get_cookies_file", return_value=None):
            youtube_dl.return_value.__enter__.return_value.extract_info.return_value = fake_info

            with self.assertRaisesRegex(ValueError, "cookies.txt|ENABLE_ASR=1"):
                ai.fetch_transcript("https://www.bilibili.com/video/BV1dojW6uEn3")

    def test_segments_to_srt_formats_numbered_cues(self) -> None:
        segments = [
            {"start": 1, "text": "第一句"},
            {"start": 4, "text": "第二句\n换行"},
        ]

        self.assertEqual(
            ai.segments_to_srt(segments),
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "第一句\n\n"
            "2\n"
            "00:00:04,000 --> 00:00:07,000\n"
            "第二句 换行\n",
        )

    def test_summary_manager_returns_srt_for_completed_task(self) -> None:
        manager = ai.AISummaryManager()
        task_id = "task-1"
        manager._tasks[task_id] = {
            "id": task_id,
            "status": "completed",
            "title": "演示/视频",
            "_segments": [{"start": 2, "text": "字幕内容"}],
            "created_at": 0,
        }

        download = manager.get_transcript_download(task_id)

        self.assertEqual(download["title"], "演示_视频")
        self.assertIn("00:00:02,000 --> 00:00:05,000", download["content"])
        self.assertIn("字幕内容", download["content"])

    def test_summary_manager_refuses_transcript_before_segments_are_available(self) -> None:
        manager = ai.AISummaryManager()
        manager._tasks["task-1"] = {
            "id": "task-1",
            "status": "fetching",
            "title": "demo",
            "_segments": [{"start": 2, "text": "字幕内容"}],
            "created_at": 0,
        }

        self.assertIsNone(manager.get_transcript_download("task-1"))

    def test_summary_manager_returns_srt_while_enriching(self) -> None:
        manager = ai.AISummaryManager()
        manager._tasks["task-1"] = {
            "id": "task-1",
            "status": "enriching",
            "title": "demo",
            "_segments": [{"start": 2, "text": "字幕内容"}],
            "created_at": 0,
        }

        download = manager.get_transcript_download("task-1")

        self.assertIsNotNone(download)
        self.assertIn("00:00:02,000 --> 00:00:05,000", download["content"])

    def test_normalizes_streamed_summary_json(self) -> None:
        raw = '```json\n{"overview":"demo","key_points":["a"],"outline":[],"mindmap_markdown":"# demo"}\n```'

        data = ai._normalize_summary_json(raw)

        self.assertEqual(data["overview"], "demo")
        self.assertEqual(data["key_points"], ["a"])

    def test_summarize_streaming_reports_partial_text(self) -> None:
        class Delta:
            content = '{"overview":"demo","key_points":[],"outline":[{"time":"0:01","title":"part","points":["detail"]}],"mindmap_markdown":"# demo"}'

        class Choice:
            delta = Delta()

        class Chunk:
            choices = [Choice()]

        partials = []

        with patch.object(ai, "_client") as client:
            client.return_value.chat.completions.create.return_value = [Chunk()]
            result = ai.summarize("字幕", "标题", on_delta=partials.append)

        self.assertEqual(result["overview"], "demo")
        self.assertEqual(result["outline"][0]["points"], ["detail"])
        self.assertTrue(partials)
        self.assertIn("demo", partials[-1])
        self.assertNotIn("overview", partials[-1])

    def test_summarize_backfills_explanatory_points_for_outline_titles(self) -> None:
        class Delta:
            content = (
                '{"overview":"demo overview","key_points":["full explanation from key point"],'
                '"outline":[{"time":"0:01","title":"项目介绍：AI热点监控工具"}],'
                '"mindmap_markdown":"# demo"}'
            )

        class Choice:
            delta = Delta()

        class Chunk:
            choices = [Choice()]

        with patch.object(ai, "_client") as client:
            client.return_value.chat.completions.create.return_value = [Chunk()]
            result = ai.summarize("[0:01] 这里详细介绍 AI 热点监控工具的背景、价值和使用方式。", "标题")

        self.assertTrue(result["outline"][0]["points"])
        self.assertGreaterEqual(len(result["outline"][0]["points"][0]), 30)
        self.assertIn("项目介绍", result["outline"][0]["points"][0])

    def test_summary_manager_exposes_fast_result_before_enrichment_completes(self) -> None:
        manager = ai.AISummaryManager()
        states = []

        def fake_fetch(_url, on_stage=None):
            return {
                "segments": [{"start": 1, "start_str": "0:01", "text": "hello"}],
                "title": "demo",
                "lang": "zh",
                "source": "subtitle",
                "webpage_url": "https://example.com/video",
            }

        def fake_fast(_transcript, _title, on_delta=None):
            return {
                "overview": "fast overview",
                "key_points": [],
                "outline": [{"time": "0:01", "seconds": 1, "title": "快速大纲", "points": []}],
                "mindmap_markdown": "",
            }

        def fake_enrich(_transcript, _title, fast_result, on_delta=None):
            states.append(manager.get("task-1"))
            enriched = dict(fast_result)
            enriched["outline"] = [{"time": "0:01", "seconds": 1, "title": "快速大纲", "points": ["详细解释"]}]
            enriched["mindmap_markdown"] = "# demo"
            return enriched

        manager._tasks["task-1"] = {
            "id": "task-1",
            "url": "https://example.com/video",
            "status": "queued",
            "stage": "排队中...",
            "error": None,
            "title": None,
            "lang": None,
            "source": None,
            "webpage_url": "https://example.com/video",
            "result": None,
            "partial": "",
            "created_at": 0,
        }

        with patch.object(ai, "fetch_transcript", side_effect=fake_fetch), \
             patch.object(ai, "summarize_fast", side_effect=fake_fast), \
             patch.object(ai, "enrich_summary", side_effect=fake_enrich):
            manager._run("task-1", "https://example.com/video")

        self.assertTrue(states)
        self.assertEqual(states[0]["status"], "enriching")
        self.assertEqual(states[0]["result"]["overview"], "fast overview")
        self.assertEqual(manager.get("task-1")["status"], "completed")
        self.assertEqual(manager.get("task-1")["result"]["outline"][0]["points"], ["详细解释"])

    def test_summary_partial_text_extracts_incomplete_json_preview(self) -> None:
        partial = '{"overview":"这是一个逐步生成的摘要","key_points":["第一点","第二'

        preview = ai._summary_partial_text(partial)

        self.assertIn("概要", preview)
        self.assertIn("这是一个逐步生成的摘要", preview)
        self.assertIn("第一点", preview)
        self.assertNotIn("overview", preview)

    def test_summary_status_exposes_public_segments_for_frontend_download(self) -> None:
        manager = ai.AISummaryManager()
        manager._tasks["task-1"] = {
            "id": "task-1",
            "status": "completed",
            "title": "demo",
            "_segments": [{"start": 1, "start_str": "0:01", "text": "hello"}],
            "_transcript_text": "[0:01] hello",
            "created_at": 0,
        }

        public = manager.get("task-1")

        self.assertEqual(public["segments"], [{"start": 1, "start_str": "0:01", "text": "hello"}])
        self.assertNotIn("_segments", public)
        self.assertNotIn("_transcript_text", public)

    def test_transcript_srt_endpoint_returns_attachment(self) -> None:
        task_id = "download-task"
        ai.ai_manager._tasks[task_id] = {
            "id": task_id,
            "status": "completed",
            "title": "demo",
            "_segments": [{"start": 1, "text": "字幕内容"}],
            "created_at": 0,
        }

        client = TestClient(app)
        login = client.post(
            "/api/auth/login",
            json={"username": "player", "password": "295056"},
        )
        self.assertEqual(login.status_code, 200)

        response = client.get(f"/api/ai/transcript/{task_id}.srt")

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn("demo.srt", response.headers["content-disposition"])
        self.assertIn("00:00:01,000", response.text)

        ai.ai_manager._tasks.pop(task_id, None)


class SummaryPromptContractTests(unittest.TestCase):
    def test_detail_prompt_requests_deep_interesting_emphasized_output(self) -> None:
        prompt = ai._DETAIL_SUMMARY_SYSTEM

        self.assertIn("深度", prompt)
        self.assertIn("有趣", prompt)
        self.assertIn("**", prompt)
        self.assertIn("💡洞察", prompt)
        self.assertIn("🎯重点", prompt)
        self.assertIn("⚠️边界", prompt)
        self.assertIn("不准编造", prompt)
        self.assertIn("从字幕看", prompt)

    def test_single_pass_prompt_matches_deep_summary_contract(self) -> None:
        prompt = ai._SUMMARY_SYSTEM

        self.assertIn("深度", prompt)
        self.assertIn("隐藏逻辑", prompt)
        self.assertIn("反直觉", prompt)
        self.assertIn("**", prompt)
        self.assertIn("mindmap_markdown", prompt)


if __name__ == "__main__":
    unittest.main()
