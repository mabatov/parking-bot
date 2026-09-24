"""Read one frame from the configured RTSP camera without writing it to disk."""

import asyncio

from loguru import logger

from config import config


class CameraError(Exception):
    """A camera failure that can be shown to a Telegram user."""


async def capture_frame(upscale: bool = False) -> bytes:
    # Preserve the old Telegram photo size; the analysis uses the native frame.
    scale = ["-vf", "scale=iw*2:ih*2"] if upscale else []
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp", "-i", config.rtsp_url,
            *scale,
            "-frames:v", "1", "-q:v", "1", "-c:v", "mjpeg",
            "-f", "image2pipe", "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        logger.warning("Не удалось запустить ffmpeg: {}", type(exc).__name__)
        raise CameraError("Не удалось запустить получение кадра с камеры.") from None

    try:
        frame, _stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        process.kill()
        await process.communicate()
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise CameraError("Камера слишком долго не отвечает.") from None

    if process.returncode != 0 or not frame:
        # ffmpeg diagnostics can contain RTSP credentials; keep them out of logs.
        logger.warning("ffmpeg не получил кадр, код выхода: {}", process.returncode)
        raise CameraError("Не удалось получить кадр с камеры.")
    return frame
