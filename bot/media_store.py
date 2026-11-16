"""Saytga rasm/video yuklash (faqat owner). Fayllar MEDIA_DIR ga saqlanadi va /media/... orqali beriladi.

Rasm: kichraytiriladi (Pillow). Video: 720p H.264 mp4 ga o'giriladi (burilgan videolar ham to'g'rilanadi),
buning uchun ffmpeg kerak (imageio-ffmpeg paketi bilan keladi). Ishlov berish fonda ketadi.
"""
import asyncio
import logging
import os
import shutil
import uuid

import config
import db

log = logging.getLogger("humo")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp"}
SECTIONS = {"gallery", "videos", "certs", "wards"}
MAX_BYTES = 200 * 1024 * 1024


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return shutil.which("ffmpeg")


def kind_of(filename: str) -> str | None:
    ext = os.path.splitext(filename)[1].lower()
    return "image" if ext in IMAGE_EXT else "video" if ext in VIDEO_EXT else None


async def save_upload(field, filename: str) -> tuple[str, int]:
    """Multipart maydonini diskka oqim bilan yozadi. (yo'l, hajm) qaytaradi."""
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    path = os.path.join(config.MEDIA_DIR, f"tmp_{uuid.uuid4().hex}{os.path.splitext(filename)[1].lower()}")
    size = 0
    with open(path, "wb") as f:
        while True:
            chunk = await field.read_chunk(1024 * 256)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                f.close()
                os.remove(path)
                raise ValueError("too_big")
            f.write(chunk)
    return path, size


async def process(mid: int, tmp: str, kind: str) -> None:
    """Fonda: optimallashtiradi, tayyor bo'lsa status='ready' qiladi."""
    name = uuid.uuid4().hex
    try:
        if kind == "image":
            out = os.path.join(config.MEDIA_DIR, name + ".jpg")
            try:
                from PIL import Image, ImageOps
                im = ImageOps.exif_transpose(Image.open(tmp)).convert("RGB")
                im.thumbnail((1600, 1600))
                im.save(out, "JPEG", quality=82, optimize=True)
            except Exception as e:  # noqa: BLE001
                log.warning("Rasm optimallashmadi (%s), asl fayl saqlandi", e)
                out = os.path.join(config.MEDIA_DIR, name + os.path.splitext(tmp)[1])
                shutil.copyfile(tmp, out)
        else:
            out = os.path.join(config.MEDIA_DIR, name + ".mp4")
            ff, ok = _ffmpeg(), False
            if ff:
                proc = await asyncio.create_subprocess_exec(
                    ff, "-y", "-i", tmp, "-vf", "scale='min(720,iw)':-2", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                try:
                    ok = await asyncio.wait_for(proc.wait(), timeout=900) == 0
                except asyncio.TimeoutError:
                    proc.kill()
            if not ok:  # ffmpeg yo'q yoki xato: asl faylni (mp4/webm/mov) o'zgartirmasdan saqlaymiz
                log.warning("Video o'girilmadi, asl fayl saqlandi")
                out = os.path.join(config.MEDIA_DIR, name + os.path.splitext(tmp)[1])
                shutil.copyfile(tmp, out)
        await db.update_media(mid, file=os.path.basename(out), status="ready")
    except Exception as e:  # noqa: BLE001
        log.error("Media ishlovi xatosi: %s", e)
        await db.update_media(mid, status="failed")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


async def remove_files(row: dict) -> None:
    path = os.path.join(config.MEDIA_DIR, os.path.basename(row.get("file") or ""))
    if row.get("file") and os.path.exists(path):
        os.remove(path)
