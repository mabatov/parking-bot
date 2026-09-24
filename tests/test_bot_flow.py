import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image

os.environ.setdefault("admin_telegram_id", "123")
os.environ.setdefault("bot_token", "123:FAKE")
os.environ.setdefault("logging_bot_token", "123:FAKE")
os.environ.setdefault("rtsp_url", "rtsp://localhost/stream")
os.environ.setdefault("db_user", "postgres")
os.environ.setdefault("db_password", "postgres")
os.environ.setdefault("db_host", "db")
os.environ.setdefault("db_port", "5432")
os.environ.setdefault("db_name", "parking_bot")

import bot
from parking_analysis import ParkingAnalysis, Space


class Message:
    def __init__(self):
        self.texts = []
        self.photos = []

    async def reply_text(self, text, **_kwargs):
        self.texts.append(text)

    async def reply_photo(self, photo, caption=None):
        self.photos.append((photo.read(), caption))


class ParkingBotFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_photo_still_uses_camera_without_analysis(self):
        camera_image = io.BytesIO()
        Image.new("RGB", (400, 300), "white").save(camera_image, "JPEG")
        message = Message()
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123, username="admin"), message=message)
        with (patch.object(bot, "sql_operations", SimpleNamespace(check_user_access=AsyncMock(return_value=True)), create=True),
              patch.object(bot, "capture_frame", AsyncMock(return_value=camera_image.getvalue())) as camera,
              patch.object(bot, "analyze_parking", AsyncMock()) as analyze,
              patch.object(bot, "send_log", AsyncMock())):
            await bot.handle_photo_request(update, None)

        camera.assert_awaited_once_with(upscale=True)
        analyze.assert_not_awaited()
        self.assertEqual(len(message.photos), 1)

    async def test_authorized_analysis_and_cooldown(self):
        camera_image = io.BytesIO()
        Image.new("RGB", (400, 300), "white").save(camera_image, "JPEG")
        space = Space("free", 0.95, ((100, 100), (300, 100), (300, 300), (100, 300)))
        analysis = ParkingAnalysis((space,), "")
        message = Message()
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123), message=message)

        with (patch.object(bot.config, "openai_api_key", "fake-key"),
              patch.object(bot, "sql_operations", SimpleNamespace(check_user_access=AsyncMock(return_value=True)), create=True),
              patch.object(bot, "capture_frame", AsyncMock(return_value=camera_image.getvalue())),
              patch.object(bot, "analyze_parking", AsyncMock(return_value=analysis)) as analyze,
              patch.object(bot, "send_log", AsyncMock()),
              patch.object(bot, "last_analysis_at", float("-inf"))):
            await bot.handle_parking_request(update, None)
            await bot.handle_parking_request(update, None)

        self.assertEqual(analyze.await_count, 1)
        self.assertEqual(len(message.photos), 1)
        self.assertIn("свободно 1", message.photos[0][1])
        self.assertTrue(any("Новый анализ будет доступен" in text for text in message.texts))

    async def test_unknown_user_cannot_send_camera_frame_to_api(self):
        message = Message()
        update = SimpleNamespace(effective_user=SimpleNamespace(id=999), message=message)
        with (patch.object(bot.config, "openai_api_key", "fake-key"),
              patch.object(bot, "sql_operations", SimpleNamespace(check_user_access=AsyncMock(return_value=False)), create=True),
              patch.object(bot, "capture_frame", AsyncMock()) as camera,
              patch.object(bot, "analyze_parking", AsyncMock()) as analyze):
            await bot.handle_parking_request(update, None)

        camera.assert_not_awaited()
        analyze.assert_not_awaited()
        self.assertIn("нет доступа", message.texts[0])


if __name__ == "__main__":
    unittest.main()
