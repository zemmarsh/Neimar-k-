import logging
import os
import subprocess

# ==============================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ И ГЛОБАЛЬНЫХ КОНСТАНТ
# ==============================================================================
# Настраиваем формат вывода логов: дата/время - уровень ошибки - сообщение
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Список форматов, которые отображаются пользователю в графическом интерфейсе
SUPPORTED_FORMATS = ["mp3", "wav", "ogg", "flac", "aac", "m4a"]


# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С FFMPEG
# ==============================================================================
def get_ffmpeg_exe() -> str:
  """Динамически определяет путь к исполняемому файлу FFmpeg.

  Приоритет поиска:
  1. Системный FFmpeg (прописанный в переменной окружения PATH).
  2. Встроенный бинарник из библиотеки imageio-ffmpeg.
  3. Локальный файл ffmpeg.exe в папке проекта.
  """
  # 1. Пробуем запустить системный FFmpeg
  try:
    subprocess.run(
        ["ffmpeg", "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return "ffmpeg"  # Если операционная система его находит, возвращаем имя команды
  except (FileNotFoundError, subprocess.CalledProcessError):
    pass

  # 2. Если системного нет, ищем путь внутри установленного пакета imageio-ffmpeg
  try:
    import imageio_ffmpeg

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    if os.path.exists(ffmpeg_path):
      return ffmpeg_path
  except ImportError:
    pass

  # 3. Фолбэк: проверяем, лежит ли ffmpeg.exe прямо в папке с этим скриптом
  local_path = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
  if os.path.exists(local_path):
    return local_path

  # Если ничего не нашли — генерируем исключение
  raise RuntimeError(
      "FFmpeg не обнаружен ни в системе, ни в библиотеке imageio-ffmpeg."
  )


def check_ffmpeg() -> bool:
  """Проверяет доступность FFmpeg в системе перед запуском конвертации.

  Возвращает True, если FFmpeg готов к работе, и False в противном случае.
  """
  try:
    # Получаем путь к исполняемому файлу
    ffmpeg_bin = get_ffmpeg_exe()

    # Запускаем короткую тестовую команду -version
    subprocess.run(
        [ffmpeg_bin, "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return True
  except Exception as e:
    # Записываем ошибку в консоль/лог для отладки
    logging.error(f"Не удалось запустить FFmpeg: {e}")
    return False


# ==============================================================================
# ОСНОВНАЯ ЛОГИКА КОНВЕРТАЦИИ
# ==============================================================================
def convert_audio_file(
    input_path: str,
    output_format: str,
    output_dir: str = None,
    bitrate: str = "192k",
) -> str:
  """Конвертирует один аудиофайл с помощью прямого вызова процесса FFmpeg.

  :param input_path: Абсолютный или относительный путь к исходному файлу.
  :param output_format: Расширение целевого формата (например, 'mp3', 'wav').
  :param output_dir: Папка для сохранения (если None — сохранит в папку с
  исходником).
  :param bitrate: Битрейт для сжатых форматов (по умолчанию '192k').
  :return: Полный путь к созданному файлу.
  """
  # 1. Проверяем, существует ли исходный файл на диске
  if not os.path.exists(input_path):
    raise FileNotFoundError(f"Исходный файл не найден: {input_path}")

  # 2. Очищаем имя формата от точек и лишних пробелов, приводим к нижнему регистру
  output_format = output_format.lower().strip(".")

  # 3. Если директория сохранения не задана пользователем — сохраняем рядом с исходным файлом
  if output_dir is None or output_dir.strip() == "":
    output_dir = os.path.dirname(input_path)

  # Создаем целевую папку, если ее еще не существует на диске
  os.makedirs(output_dir, exist_ok=True)

  # 4. Формируем имя и полный путь для создаваемого файла
  # splitext выделяет имя файла без расширения (например, "song" из "song.wav")
  filename_without_ext = os.path.splitext(os.path.basename(input_path))[0]
  output_filename = f"{filename_without_ext}.{output_format}"
  output_path = os.path.join(output_dir, output_filename)

  # 5. Получаем путь к исполняемому файлу FFmpeg
  ffmpeg_bin = get_ffmpeg_exe()

  # 6. Собираем список аргументов для команды консоли:
  # -y  -> Автоматически перезаписывать существующий файл без запросов
  # -i  -> Входной файл
  command = [ffmpeg_bin, "-y", "-i", input_path]

  # Для несжатых или Lossless-форматов (WAV, FLAC) битрейт задавать не нужно
  if output_format not in ["wav", "flac"]:
    command.extend(["-b:a", bitrate])

  # Последний аргумент команды — путь к выходному файлу
  command.append(output_path)
  logging.info(f"Запуск команды FFmpeg: {' '.join(command)}")

  # 7. Запускаем изолированный процесс FFmpeg в операционной системе
  process = subprocess.run(
      command,
      stdout=subprocess.PIPE,  # Перехватываем стандартный вывод, чтобы не засорять консоль
      stderr=subprocess.PIPE,  # Перехватываем сообщения об ошибках
      text=True,  # Декодируем байты в текст
      encoding="utf-8",
      errors="replace",  # Заменяем некорректные символы, если в путях есть специфическая кодировка
  )

  # 8. Обработка аварийного завершения FFmpeg (если код возврата не равен 0)
  if process.returncode != 0:
    # Если на диске успел создаться пустой файл-фантом — удаляем его
    if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
      try:
        os.remove(output_path)
      except OSError:
        pass

    # Вытаскиваем текст ошибки, полученный от FFmpeg
    error_msg = process.stderr.strip() or "Неизвестная ошибка FFmpeg"
    raise RuntimeError(f"Ошибка конвертации: {error_msg}")

  # 9. Финальная страховочная проверка: существование и размер файла > 0 байт
  if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
    if os.path.exists(output_path):
      os.remove(output_path)
    raise RuntimeError("Ошибка: Выходной файл создался пустым (0 байт).")

  logging.info(f"Файл успешно создан: {output_path}")
  return output_path


def batch_convert_audio(
    files: list,
    output_format: str,
    output_dir: str = None,
    bitrate: str = "192k",
    progress_callback=None,
) -> tuple[list, list]:
  """Выполняет последовательную конвертацию списка файлов.

  :param files: Список путей к файлам.
  :param output_format: Целевой формат.
  :param output_dir: Папка назначения.
  :param bitrate: Качество звука.
  :param progress_callback: Функция обратного вызова для GUI (передает current,
  total, filename).
  :return: Кортеж из двух списков: ([успешно_созданные_файлы],
  [(файл_с_ошибкой, текст_ошибки)])
  """
  successful = []  # Список путей успешно готовых файлов
  errors = []  # Список кортежей с файлами, на которых произошел сбой
  total = len(files)

  # Перебираем все полученные файлы, отсчитывая порядковый номер с 1
  for index, file_path in enumerate(files, start=1):
    file_name = os.path.basename(file_path)

    # Уведомляем графический интерфейс о текущем прогрессе
    if progress_callback:
      progress_callback(index, total, file_name)

    try:
      # Попытка сконвертировать отдельный файл
      res_path = convert_audio_file(
          file_path, output_format, output_dir, bitrate
      )
      successful.append(res_path)
    except Exception as e:
      # Если один файл упал с ошибкой, мы перехватываем её и продолжаем цикл по другим файлам
      errors.append((file_path, str(e)))

  # Возвращаем результаты пакетной обработки
  return successful, errors