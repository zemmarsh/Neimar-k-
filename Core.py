import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import static_ffmpeg

# Автоматически загружает бинарники FFmpeg при первом запуске и добавляет их в PATH
try:
    static_ffmpeg.add_paths()
except Exception as e:
    print(f"Ошибка инициализации static-ffmpeg: {e}")

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
    """Проверка доступности FFmpeg."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def detect_file_type(file_paths: list) -> str:
    """Определяет тип пакета файлов: 'audio' (включает видео для извлечения звука) или 'image'."""
    has_audio_or_video = False
    has_image = False

    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        if ext in SUPPORTED_AUDIO_EXT or ext in SUPPORTED_VIDEO_EXT:
            has_audio_or_video = True
        elif ext in SUPPORTED_IMAGE_EXT:
            has_image = True
        else:
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
) -> str:
    """Конвертирует аудио или извлекает аудиодорожку из видео через FFmpeg."""
    if not output_dir:
        output_dir = os.path.dirname(input_path)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{output_format.lower()}")

    cmd = ["ffmpeg", "-y", "-i", input_path, "-vn"]

    if output_format.lower() in ["mp3", "m4a"]:
        cmd.extend(["-b:a", bitrate])

    cmd.append(output_path)

    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Ошибка FFmpeg при обработке {os.path.basename(input_path)}:\n{result.stderr}"
        )

    return output_path


def convert_image(
    input_path: str,
    output_format: str,
    output_dir: str = None,
    strip_metadata: bool = False,
) -> str:
    """Конвертирует изображение. Если strip_metadata=True, удаляет EXIF/метаданные."""
    if not output_dir:
        output_dir = os.path.dirname(input_path)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{output_format.lower()}")

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

    return output_path


def process_single_file(task: dict, output_dir: str = None) -> str:
    """Обрабатывает один файл на основе его конфигурации."""
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
        )
    elif ext in SUPPORTED_IMAGE_EXT:
        return convert_image(
            input_path=path,
            output_format=target_format,
            output_dir=output_dir,
            strip_metadata=strip_metadata,
        )
    else:
        raise ValueError(f"Неподдерживаемый формат: {ext}")


def batch_convert_parallel(
    tasks: list, output_dir: str = None, progress_callback=None
) -> tuple:
    """Параллельная обработка списка файлов."""
    successful = []
    errors = []
    total = len(tasks)
    completed = 0

    def worker(task):
        nonlocal completed
        try:
            res_path = process_single_file(task, output_dir)
            successful.append(res_path)
        except Exception as e:
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

    return successful, errors