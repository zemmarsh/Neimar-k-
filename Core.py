import importlib.util
import logging
import os
import shutil
import subprocess
from PIL import Image

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Поддерживаемые расширения файлов
AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".aac",
    ".m4a",
    ".wma",
    ".opus",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".ico", ".tiff"}

SUPPORTED_AUDIO_FORMATS = ["mp3", "wav", "ogg", "flac", "aac", "m4a"]
SUPPORTED_IMAGE_FORMATS = ["jpg", "png", "webp", "bmp", "ico"]


def detect_file_type(file_paths: list) -> str:
    """Определяет общий тип файлов ('audio', 'image', 'mixed', 'unknown')."""
    if not file_paths:
        return "unknown"

    types = set()
    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS:
            types.add("audio")
        elif ext in IMAGE_EXTENSIONS:
            types.add("image")
        else:
            types.add("unknown")

    if len(types) == 1:
        return types.pop()
    return "mixed"


def get_ffmpeg_exe() -> str:
    """Находит путь к FFmpeg."""
    local_path = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
    if os.path.exists(local_path):
        return local_path

    try:
        import imageio_ffmpeg

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    except ImportError:
        pass

    if shutil.which("ffmpeg"):
        return "ffmpeg"

    raise RuntimeError("FFmpeg не обнаружен в системе.")


def check_ffmpeg() -> bool:
    """Мгновенная проверка наличия FFmpeg без долгих вызовов subprocess."""
    try:
        local_path = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
        if os.path.exists(local_path):
            return True

        if importlib.util.find_spec("imageio_ffmpeg") is not None:
            return True

        if shutil.which("ffmpeg") is not None:
            return True

        return False
    except Exception:
        return False


def convert_audio_file(
    input_path: str,
    output_format: str,
    output_dir: str = None,
    bitrate: str = "192k",
) -> str:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Файл не найден: {input_path}")

    output_format = output_format.lower().strip(".")
    if output_dir is None or output_dir.strip() == "":
        output_dir = os.path.dirname(input_path)

    os.makedirs(output_dir, exist_ok=True)

    filename_without_ext = os.path.splitext(os.path.basename(input_path))[0]
    output_filename = f"{filename_without_ext}.{output_format}"
    output_path = os.path.join(output_dir, output_filename)

    ffmpeg_bin = get_ffmpeg_exe()
    command = [ffmpeg_bin, "-y", "-i", input_path]

    # Настройка битрейта только для кодеков со сжатием
    if output_format not in ["wav", "flac"]:
        command.extend(["-b:a", bitrate])

    command.append(output_path)

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if process.returncode != 0:
        if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
            try:
                os.remove(output_path)
            except OSError:
                pass
        error_msg = process.stderr.strip() or "Ошибка FFmpeg"
        raise RuntimeError(f"Ошибка конвертации: {error_msg}")

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError("Ошибка: Выходной файл пуст.")

    return output_path


def convert_image_file(
    input_path: str,
    output_format: str,
    output_dir: str = None,
    quality: int = 90,
) -> str:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Файл не найден: {input_path}")

    output_format = output_format.lower().strip(".").replace("jpeg", "jpg")
    if output_dir is None or output_dir.strip() == "":
        output_dir = os.path.dirname(input_path)

    os.makedirs(output_dir, exist_ok=True)

    filename_without_ext = os.path.splitext(os.path.basename(input_path))[0]
    output_filename = f"{filename_without_ext}.{output_format}"
    output_path = os.path.join(output_dir, output_filename)

    with Image.open(input_path) as img:
        if output_format in ["jpg", "jpeg"] and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        if output_format == "ico":
            img.save(output_path, format="ICO", sizes=[(256, 256)])
        elif output_format in ["jpg", "jpeg", "webp"]:
            img.save(output_path, quality=quality)
        else:
            img.save(output_path)

    return output_path


def convert_file(
    input_path: str,
    output_format: str,
    output_dir: str = None,
    bitrate: str = "192k",
) -> str:
    ext = os.path.splitext(input_path)[1].lower()

    if ext in AUDIO_EXTENSIONS:
        return convert_audio_file(input_path, output_format, output_dir, bitrate)
    elif ext in IMAGE_EXTENSIONS:
        return convert_image_file(input_path, output_format, output_dir)
    else:
        raise ValueError(f"Неподдерживаемый формат: {ext}")


def batch_convert(
    files: list,
    output_format: str,
    output_dir: str = None,
    bitrate: str = "192k",
    progress_callback=None,
) -> tuple[list, list]:
    successful = []
    errors = []
    total = len(files)

    for index, file_path in enumerate(files, start=1):
        file_name = os.path.basename(file_path)
        if progress_callback:
            progress_callback(index, total, file_name)

        try:
            res_path = convert_file(file_path, output_format, output_dir, bitrate)
            successful.append(res_path)
        except Exception as e:
            errors.append((file_path, str(e)))

    return successful, errors