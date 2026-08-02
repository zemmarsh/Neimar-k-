import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from tkinterdnd2 import DND_FILES, TkinterDnD

import Core

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class AudioImageConverterGUI(ctk.CTk):

    def __init__(self):
        super().__init__()

        # Быстрая инициализация окна без блокировок
        self.title("Универсальный Конвертер")
        self.geometry("450x250")
        self.resizable(False, False)

        self.selected_files = []
        self.current_mode = None

        self._build_ui()

        # Отложенный вызов подгрузки тяжелых компонентов (10 мс и 100 мс)
        self.after(10, self._init_dnd_lazy)
        self.after(100, self._check_environment)

    def _init_dnd_lazy(self):
        """Ленивая подгрузка Drag-and-Drop."""
        try:
            TkinterDnD._require(self)
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self._on_file_drop)
        except Exception as e:
            print(f"Предупреждение: DnD недоступен: {e}")

    def _check_environment(self):
        """Быстрая фоновая проверка наличия FFmpeg."""
        if not Core.check_ffmpeg():
            messagebox.showwarning(
                "Внимание",
                "FFmpeg не обнаружен. Конвертация видео/аудио может не работать.",
            )

    def _build_ui(self):
        # ======================================================================
        # ЭТАП 1: ЗОНА ВЫБОРА / СБРОСА ФАЙЛОВ
        # ======================================================================
        self.drop_frame = ctk.CTkFrame(
            self,
            corner_radius=15,
            border_width=2,
            border_color=("gray70", "gray30"),
        )
        self.drop_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.lbl_drop_icon = ctk.CTkLabel(
            self.drop_frame, text="📁", font=ctk.CTkFont(size=40)
        )
        self.lbl_drop_icon.pack(pady=(25, 5))

        self.lbl_drop_text = ctk.CTkLabel(
            self.drop_frame,
            text="Перетащите файлы сюда\nили выберите через кнопку",
            font=ctk.CTkFont(size=14),
            justify="center",
        )
        self.lbl_drop_text.pack(pady=5)

        self.btn_select = ctk.CTkButton(
            self.drop_frame, text="Выбрать файлы", command=self.select_files
        )
        self.btn_select.pack(pady=(10, 20))

        # ======================================================================
        # ЭТАП 2: НАСТРОЙКИ И КОНВЕРТАЦИЯ
        # ======================================================================
        self.settings_frame = ctk.CTkFrame(self)

        self.lbl_files_info = ctk.CTkLabel(
            self.settings_frame,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.lbl_files_info.grid(
            row=0, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="w"
        )

        # Выбор формата
        self.lbl_format = ctk.CTkLabel(self.settings_frame, text="Формат:")
        self.lbl_format.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.combo_format = ctk.CTkOptionMenu(
            self.settings_frame,
            values=[],
            command=self._on_format_change,  # Динамически скрывает битрейт
        )
        self.combo_format.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Настройка битрейта (скрывается когда не нужна)
        self.lbl_bitrate = ctk.CTkLabel(self.settings_frame, text="Битрейт:")
        self.combo_bitrate = ctk.CTkOptionMenu(
            self.settings_frame, values=["128k", "192k", "256k", "320k"]
        )
        self.combo_bitrate.set("192k")

        # Папка сохранения
        self.lbl_outdir = ctk.CTkLabel(self.settings_frame, text="Сохранить в:")
        self.lbl_outdir.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        self.entry_outdir = ctk.CTkEntry(
            self.settings_frame, placeholder_text="Рядом с исходниками"
        )
        self.entry_outdir.grid(row=3, column=1, padx=(10, 5), pady=5, sticky="ew")

        self.btn_browse_dir = ctk.CTkButton(
            self.settings_frame,
            text="Обзор",
            width=60,
            command=self.select_output_dir,
        )
        self.btn_browse_dir.grid(row=3, column=2, padx=(0, 10), pady=5)

        self.settings_frame.grid_columnconfigure(1, weight=1)

        # Прогресс
        self.status_label = ctk.CTkLabel(
            self, text="Готов к работе", text_color="gray"
        )
        self.progressbar = ctk.CTkProgressBar(self, width=440)
        self.progressbar.set(0)

        # Кнопки действия
        self.action_btn_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.btn_reset = ctk.CTkButton(
            self.action_btn_frame,
            text="← Выбрать другие",
            fg_color="transparent",
            border_width=1,
            text_color=("black", "white"),
            command=self.reset_to_first_step,
        )
        self.btn_reset.pack(side="left", padx=10)

        self.btn_convert = ctk.CTkButton(
            self.action_btn_frame,
            text="Начать конвертацию",
            fg_color="green",
            hover_color="darkgreen",
            command=self.start_conversion_thread,
        )
        self.btn_convert.pack(side="right", padx=10)

    def _on_file_drop(self, event):
        data = event.data
        if data.startswith("{") and data.endswith("}"):
            data = data[1:-1]

        raw_files = self.tk.splitlist(data)
        self.process_selected_files(raw_files)

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите файлы",
            filetypes=[
                (
                    "Все поддерживаемые",
                    "*.mp3 *.wav *.ogg *.flac *.m4a *.jpg *.jpeg *.png *.webp *.bmp",
                ),
                ("Аудиофайлы", "*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma *.opus"),
                ("Изображения", "*.jpg *.jpeg *.png *.webp *.bmp *.ico *.tiff"),
                ("Все файлы", "*.*"),
            ],
        )
        if files:
            self.process_selected_files(list(files))

    def process_selected_files(self, file_list: list):
        file_type = Core.detect_file_type(file_list)

        if file_type == "mixed":
            messagebox.showerror(
                "Ошибка выбора",
                "Вы закинули одновременно и аудио, и картинки!\n\nЗагружайте файлы одного типа за раз.",
            )
            return
        elif file_type == "unknown":
            messagebox.showerror(
                "Ошибка формата",
                "Среди выбранных нет поддерживаемых аудио или картинок.",
            )
            return

        self.selected_files = file_list
        self.current_mode = file_type
        count = len(self.selected_files)

        if self.current_mode == "audio":
            self.lbl_files_info.configure(
                text=f"🎵 Выбрано аудиофайлов: {count}", text_color="#2FA572"
            )
            self.combo_format.configure(values=Core.SUPPORTED_AUDIO_FORMATS)
            self.combo_format.set("mp3")
        elif self.current_mode == "image":
            self.lbl_files_info.configure(
                text=f"🖼️ Выбрано картинок: {count}", text_color="#3B8ED0"
            )
            self.combo_format.configure(values=Core.SUPPORTED_IMAGE_FORMATS)
            self.combo_format.set("png")

        # Обновляем видимость битрейта
        self._on_format_change(self.combo_format.get())
        self.show_second_step()

    def _on_format_change(self, selected_format: str):
        """Скрывает битрейт для картинок и несжимаемых аудио (WAV, FLAC)."""
        if self.current_mode == "audio" and selected_format not in ["wav", "flac"]:
            self.lbl_bitrate.grid(row=2, column=0, padx=10, pady=5, sticky="w")
            self.combo_bitrate.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        else:
            self.lbl_bitrate.grid_forget()
            self.combo_bitrate.grid_forget()

    def show_second_step(self):
        self.drop_frame.pack_forget()

        # Если битрейт скрыт, делаем окно чуть компактнее
        window_height = (
            "360"
            if (
                self.current_mode == "audio"
                and self.combo_format.get() not in ["wav", "flac"]
            )
            else "320"
        )
        self.geometry(f"520x{window_height}")

        self.settings_frame.pack(padx=20, pady=(15, 5), fill="x")
        self.status_label.pack(pady=(10, 2))
        self.progressbar.pack(pady=5)
        self.action_btn_frame.pack(pady=15, fill="x")

        self.status_label.configure(text="Готов к конвертации", text_color="gray")
        self.progressbar.set(0)

    def reset_to_first_step(self):
        self.settings_frame.pack_forget()
        self.status_label.pack_forget()
        self.progressbar.pack_forget()
        self.action_btn_frame.pack_forget()

        self.selected_files = []
        self.current_mode = None

        self.geometry("450x250")
        self.drop_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def select_output_dir(self):
        directory = filedialog.askdirectory(title="Выберите папку для сохранения")
        if directory:
            self.entry_outdir.delete(0, "end")
            self.entry_outdir.insert(0, directory)

    def start_conversion_thread(self):
        if not self.selected_files:
            return

        self.btn_reset.configure(state="disabled")
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

        successful, errors = Core.batch_convert(
            files=self.selected_files,
            output_format=target_format,
            output_dir=output_dir,
            bitrate=bitrate,
            progress_callback=update_progress,
        )

        self.btn_reset.configure(state="normal")
        self.btn_convert.configure(state="normal")
        self.btn_browse_dir.configure(state="normal")

        if errors:
            self.status_label.configure(
                text=f"Завершено с ошибками ({len(errors)})",
                text_color="orange",
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
                text="Все файлы успешно обработаны!", text_color="#2FA572"
            )
            messagebox.showinfo("Успех", "Конвертация успешно завершена!")


if __name__ == "__main__":
    app = AudioImageConverterGUI()
    app.mainloop()