import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Импортируем логику ядра
import Core

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class AudioConverterGUI(ctk.CTk):

  def __init__(self):
    super().__init__()

    self.title("Аудио Конвертер")
    self.geometry("580x470")
    self.resizable(False, False)

    self.selected_files = []

    self._build_ui()
    self._check_environment()

  def _build_ui(self):
    # === Заголовок ===
    self.title_label = ctk.CTkLabel(
        self, text="Аудио Конвертер", font=ctk.CTkFont(size=22, weight="bold")
    )
    self.title_label.pack(pady=(15, 10))

    # === Выбор файлов ===
    self.file_frame = ctk.CTkFrame(self)
    self.file_frame.pack(padx=20, pady=5, fill="x")

    self.btn_select = ctk.CTkButton(
        self.file_frame, text="Выбрать файлы", command=self.select_files
    )
    self.btn_select.pack(side="left", padx=10, pady=10)

    self.lbl_files_count = ctk.CTkLabel(
        self.file_frame, text="Файлы не выбраны", text_color="gray"
    )
    self.lbl_files_count.pack(side="left", padx=10, pady=10)

    # === Настройки конвертации ===
    self.settings_frame = ctk.CTkFrame(self)
    self.settings_frame.pack(padx=20, pady=10, fill="x")

    # Целевой формат
    self.lbl_format = ctk.CTkLabel(self.settings_frame, text="Формат:")
    self.lbl_format.grid(row=0, column=0, padx=10, pady=10, sticky="w")

    self.combo_format = ctk.CTkOptionMenu(
        self.settings_frame, values=Core.SUPPORTED_FORMATS
    )
    self.combo_format.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    self.combo_format.set("mp3")

    # Битрейт
    self.lbl_bitrate = ctk.CTkLabel(self.settings_frame, text="Битрейт:")
    self.lbl_bitrate.grid(row=1, column=0, padx=10, pady=10, sticky="w")

    self.combo_bitrate = ctk.CTkOptionMenu(
        self.settings_frame, values=["128k", "192k", "256k", "320k"]
    )
    self.combo_bitrate.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
    self.combo_bitrate.set("192k")

    # Папка сохранения
    self.lbl_outdir = ctk.CTkLabel(self.settings_frame, text="Сохранить в:")
    self.lbl_outdir.grid(row=2, column=0, padx=10, pady=10, sticky="w")

    self.entry_outdir = ctk.CTkEntry(
        self.settings_frame, placeholder_text="Рядом с исходным файлом"
    )
    self.entry_outdir.grid(row=2, column=1, padx=(10, 5), pady=10, sticky="ew")

    self.btn_browse_dir = ctk.CTkButton(
        self.settings_frame,
        text="Обзор",
        width=60,
        command=self.select_output_dir,
    )
    self.btn_browse_dir.grid(row=2, column=2, padx=(0, 10), pady=10)

    self.settings_frame.grid_columnconfigure(1, weight=1)

    # === Прогресс и Статус ===
    self.status_label = ctk.CTkLabel(
        self, text="Готов к работе", text_color="gray"
    )
    self.status_label.pack(pady=(10, 5))

    self.progressbar = ctk.CTkProgressBar(self, width=440)
    self.progressbar.pack(pady=5)
    self.progressbar.set(0)

    # === Кнопка старта ===
    self.btn_convert = ctk.CTkButton(
        self,
        text="Начать конвертацию",
        fg_color="green",
        hover_color="darkgreen",
        command=self.start_conversion_thread,
    )
    self.btn_convert.pack(pady=15)

  def _check_environment(self):
    if not Core.check_ffmpeg():
      messagebox.showerror(
          "Ошибка окружения",
          "FFmpeg не обнаружен в вашей системе!\n\n"
          "Установите FFmpeg и добавьте его в системные переменные PATH, "
          "иначе конвертация будет невозможна.",
      )

  def select_files(self):
    files = filedialog.askopenfilenames(
        title="Выберите аудиофайлы",
        filetypes=[
            (
                "Аудиофайлы",
                "*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma *.opus *.ape",
            ),
            ("Все файлы", "*.*"),
        ],
    )
    if files:
      self.selected_files = list(files)
      count = len(self.selected_files)
      self.lbl_files_count.configure(
          text=f"Выбрано файлов: {count}", text_color="white"
      )
      self.status_label.configure(text="Готов к конвертации", text_color="gray")

  def select_output_dir(self):
    directory = filedialog.askdirectory(title="Выберите папку для сохранения")
    if directory:
      self.entry_outdir.delete(0, "end")
      self.entry_outdir.insert(0, directory)

  def start_conversion_thread(self):
    if not self.selected_files:
      messagebox.showwarning(
          "Внимание", "Пожалуйста, выберите файлы для конвертации!"
      )
      return

    self.btn_select.configure(state="disabled")
    self.btn_convert.configure(state="disabled")
    self.btn_browse_dir.configure(state="disabled")
    self.progressbar.set(0)

    threading.Thread(target=self._run_conversion, daemon=True).start()

  def _run_conversion(self):
    target_format = self.combo_format.get()
    bitrate = self.combo_bitrate.get()
    output_dir = self.entry_outdir.get().strip() or None

    def update_progress(current, total, file_name):
      self.status_label.configure(
          text=f"Обработка ({current}/{total}): {file_name}"
      )
      self.progressbar.set(current / total)

    successful, errors = Core.batch_convert_audio(
        files=self.selected_files,
        output_format=target_format,
        output_dir=output_dir,
        bitrate=bitrate,
        progress_callback=update_progress,
    )

    self.btn_select.configure(state="normal")
    self.btn_convert.configure(state="normal")
    self.btn_browse_dir.configure(state="normal")

    if errors:
      self.status_label.configure(
          text=f"Завершено с ошибками ({len(errors)})", text_color="orange"
      )
      err_details = "\n".join(
          [f"- {os.path.basename(f)}: {e}" for f, e in errors[:3]]
      )
      messagebox.showwarning(
          "Ошибки при обработке",
          f"Успешно: {len(successful)}\nОшибок: {len(errors)}\n\nДетали:\n{err_details}",
      )
    else:
      self.status_label.configure(
          text="Конвертация успешно завершена!", text_color="#2FA572"
      )
      messagebox.showinfo("Успех", "Все файлы успешно обработаны!")


if __name__ == "__main__":
  app = AudioConverterGUI()
  app.mainloop()