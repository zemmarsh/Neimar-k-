import json
import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
import static_ffmpeg

# Настройка логирования с ограничением размера и ротацией
file_handler = RotatingFileHandler(
    "app.log",
    maxBytes=1024 * 1024,  # Максимум 1 МБ на файл
    backupCount=2,         # Хранить не более 2 старых архивов (app.log.1, app.log.2)
    encoding="utf-8"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        file_handler,
        logging.StreamHandler(),
    ],
)

try:
    static_ffmpeg.add_paths()
    logging.info("static-ffmpeg успешно инициализирован.")
except Exception as e:
    logging.error("Ошибка инициализации static-ffmpeg", exc_info=True)

SUPPORTED_AUDIO_EXT = (
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".m4a",
    ".aac",
    ".wma",
    ".opus",
)
SUPPORTED_VIDEO_EXT = (
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".flv",
    ".wmv",
    ".webm",
)
SUPPORTED_IMAGE_EXT = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".ico",
    ".tiff",
)

SUPPORTED_AUDIO_FORMATS = ["mp3", "wav", "ogg", "flac", "m4a"]
SUPPORTED_IMAGE_FORMATS = ["png", "jpg", "webp", "bmp", "ico"]


def check_ffmpeg() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logging.warning(f"Проверка FFmpeg завершилась неудачей: {e}")
        return False


def get_media_duration(file_path: str) -> float:
    """Получает длительность медиафайла в секундах через ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        logging.warning(f"Не удалось получить длительность для {file_path}: {e}")
        return 0.0


def estimate_audio_size(duration_sec: float, bitrate_str: str) -> float:
    """Рассчитывает примерный размер итогового аудиофайла в МБ."""
    if not duration_sec or duration_sec <= 0:
        return 0.0
    try:
        bitrate_kbps = int(bitrate_str.replace("k", ""))
        return (bitrate_kbps * duration_sec) / (8 * 1024)
    except ValueError as e:
        logging.warning(f"Ошибка парсинга битрейта ({bitrate_str}): {e}")
        return 0.0


def detect_file_type(file_paths: list) -> str:
    has_audio_or_video = False
    has_image = False

    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        if ext in SUPPORTED_AUDIO_EXT or ext in SUPPORTED_VIDEO_EXT:
            has_audio_or_video = True
        elif ext in SUPPORTED_IMAGE_EXT:
            has_image = True
        else:
            logging.info(f"Обнаружен неизвестный формат файла: {path}")
            return "unknown"

    if has_audio_or_video and has_image:
        return "mixed"
    elif has_audio_or_video:
        return "audio"
    elif has_image:
        return "image"

    return "unknown"


def convert_audio_or_video(
    input_path: str,
    output_format: str,
    bitrate: str = "192k",
    output_dir: str = None,
    start_time: str = "",
    end_time: str = "",
    tags: dict = None,
) -> str:
    if not output_dir:
        output_dir = os.path.dirname(input_path)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{output_format.lower()}")

    logging.info(f"Старт FFmpeg конвертации: {input_path} -> {output_path}")

    cmd = ["ffmpeg", "-y"]

    if start_time.strip():
        cmd.extend(["-ss", start_time.strip()])
    if end_time.strip():
        cmd.extend(["-to", end_time.strip()])

    cmd.extend(["-i", input_path, "-vn"])

    if output_format.lower() in ["mp3", "m4a"]:
        cmd.extend(["-b:a", bitrate])

    cmd.append(output_path)

    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode != 0:
        logging.error(f"Ошибка FFmpeg при обработке {input_path}:\n{result.stderr}")
        raise RuntimeError(
            f"Ошибка FFmpeg при обработке {os.path.basename(input_path)}:\n{result.stderr}"
        )

    if output_format.lower() == "mp3" and tags:
        apply_mp3_tags(output_path, tags)

    logging.info(f"Успешно конвертировано: {output_path}")
    return output_path


def apply_mp3_tags(file_path: str, tags: dict):
    """Применяет ID3 теги и обложку к MP3 файлу."""
    try:
        try:
            audio = EasyID3(file_path)
        except Exception:
            audio = EasyID3()
            audio.filename = file_path

        if tags.get("title"):
            audio["title"] = tags["title"]
        if tags.get("artist"):
            audio["artist"] = tags["artist"]
        audio.save(file_path)

        if tags.get("cover_path") and os.path.exists(tags["cover_path"]):
            id3 = ID3(file_path)
            with open(tags["cover_path"], "rb") as albumart:
                id3.add(
                    APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=albumart.read(),
                    )
                )
            id3.save(file_path)
        logging.info(f"Теги успешно применены к {file_path}")
    except Exception as e:
        logging.error(f"Ошибка сохранения ID3-тегов для {file_path}", exc_info=True)


def convert_image(
    input_path: str,
    output_format: str,
    output_dir: str = None,
    strip_metadata: bool = False,
) -> str:
    if not output_dir:
        output_dir = os.path.dirname(input_path)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{output_format.lower()}")

    logging.info(f"Старт конвертации изображения: {input_path} -> {output_path}")

    with Image.open(input_path) as img:
        target_fmt = output_format.upper()
        if target_fmt == "JPG":
            target_fmt = "JPEG"

        if target_fmt in ["JPEG", "BMP"] and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        if strip_metadata:
            data = list(img.getdata())
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(data)
            clean_img.save(output_path, format=target_fmt)
        else:
            img.save(output_path, format=target_fmt)

    logging.info(f"Изображение успешно сохранено: {output_path}")
    return output_path


def process_single_file(task: dict, output_dir: str = None) -> str:
    path = task["path"]
    target_format = task["format"]
    bitrate = task.get("bitrate", "192k")
    strip_metadata = task.get("strip_metadata", False)

    ext = os.path.splitext(path)[1].lower()

    if ext in SUPPORTED_AUDIO_EXT or ext in SUPPORTED_VIDEO_EXT:
        return convert_audio_or_video(
            input_path=path,
            output_format=target_format,
            bitrate=bitrate,
            output_dir=output_dir,
            start_time=task.get("start_time", ""),
            end_time=task.get("end_time", ""),
            tags=task.get("tags", {}),
        )
    elif ext in SUPPORTED_IMAGE_EXT:
        return convert_image(
            input_path=path,
            output_format=target_format,
            output_dir=output_dir,
            strip_metadata=strip_metadata,
        )
    else:
        err_msg = f"Неподдерживаемый формат файла: {ext}"
        logging.error(err_msg)
        raise ValueError(err_msg)


def batch_convert_parallel(
    tasks: list, output_dir: str = None, progress_callback=None
) -> tuple:
    successful = []
    errors = []
    total = len(tasks)
    completed = 0

    logging.info(f"Запуск пакетной конвертации. Всего задач: {total}")

    def worker(task):
        nonlocal completed
        try:
            res_path = process_single_file(task, output_dir)
            successful.append(res_path)
        except Exception as e:
            logging.error(f"Сбой обработки файла {task['path']}", exc_info=True)
            errors.append((task["path"], str(e)))
        finally:
            completed += 1
            if progress_callback:
                progress_callback(
                    completed, total, os.path.basename(task["path"])
                )

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(worker, t) for t in tasks]
        for f in futures:
            f.result()

    logging.info(
        f"Пакетная конвертация завершена. Успешно: {len(successful)}, Ошибок: {len(errors)}"
    )
    return successful, errors