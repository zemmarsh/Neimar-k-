import os
import re
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD

import Core

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class CTkWithDnD(ctk.CTk, TkinterDnD.DnDWrapper):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


class AudioImageConverterGUI(CTkWithDnD):

    def __init__(self):
        super().__init__()

        self.title("Универсальный Конвертер Pro")
        self.geometry("540x280")
        self.resizable(False, False)

        self.file_configs = []
        self.current_mode = None
        self.last_output_dir = None
        self._drag_enter_count = 0          # счётчик событий DragEnter/DragLeave
        self._default_border = None         # исходный цвет рамки
        self._default_fg = None             # исходный цвет фона

        self._build_header()
        self._build_ui()

        # Регистрация приема файлов после инициализации UI
        self.after(200, self._setup_dnd)
        self.after(300, self._check_environment)

    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(10, 0))

        self.lbl_app_title = ctk.CTkLabel(
            self.header_frame,
            text="Media Converter Pro",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.lbl_app_title.pack(side="left")

        self.theme_switch = ctk.CTkSwitch(
            self.header_frame, text="Тёмная тема", command=self.toggle_theme
        )
        self.theme_switch.pack(side="right")
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()

    def toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    def _build_ui(self):
        # ======================================================================
        # ЗОНА СБРОСА (с поддержкой подсветки)
        # ======================================================================
        self._default_border = ("gray70", "gray30")
        self._default_fg = ("gray90", "gray15")

        self.drop_frame = ctk.CTkFrame(
            self,
            corner_radius=15,
            border_width=2,
            border_color=self._default_border,
            fg_color=self._default_fg
        )
        self.drop_frame.pack(fill="both", expand=True, padx=20, pady=15)

        self.lbl_drop_icon = ctk.CTkLabel(
            self.drop_frame, text="📁", font=ctk.CTkFont(size=40)
        )
        self.lbl_drop_icon.pack(pady=(20, 5))

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
        self.btn_select.pack(pady=(10, 15))

        # ======================================================================
        # ЗОНА НАСТРОЕК
        # ======================================================================
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.tracks_scroll_frame = ctk.CTkScrollableFrame(
            self.settings_frame,
            height=200,
            label_text="Индивидуальная настройка файлов (Параллельная обработка)",
        )
        self.tracks_scroll_frame.pack(fill="x", padx=5, pady=5)

        self.global_params_frame = ctk.CTkFrame(self.settings_frame)
        self.global_params_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_outdir = ctk.CTkLabel(self.global_params_frame, text="Сохранить в:")
        self.lbl_outdir.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.entry_outdir = ctk.CTkEntry(
            self.global_params_frame, placeholder_text="Рядом с исходниками"
        )
        self.entry_outdir.grid(row=0, column=1, padx=(10, 5), pady=5, sticky="ew")

        self.btn_browse_dir = ctk.CTkButton(
            self.global_params_frame,
            text="Обзор",
            width=60,
            command=self.select_output_dir,
        )
        self.btn_browse_dir.grid(row=0, column=2, padx=(0, 10), pady=5)

        self.global_params_frame.grid_columnconfigure(1, weight=1)

        self.status_label = ctk.CTkLabel(
            self, text="Готов к работе", text_color="gray"
        )
        self.progressbar = ctk.CTkProgressBar(self, width=560)
        self.progressbar.set(0)

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

        self.btn_open_dir = ctk.CTkButton(
            self.action_btn_frame,
            text="📁 Открыть папку",
            fg_color="#3B8ED0",
            command=self.open_output_folder,
        )

        self.btn_convert = ctk.CTkButton(
            self.action_btn_frame,
            text="Начать параллельную конвертацию",
            fg_color="green",
            hover_color="darkgreen",
            command=self.start_conversion_thread,
        )
        self.btn_convert.pack(side="right", padx=10)

    def _setup_dnd(self):
        """Привязка событий DragEnter, DragLeave и Drop к целевым виджетам."""
        targets = [self.drop_frame, self.lbl_drop_icon, self.lbl_drop_text]

        for target in targets:
            try:
                target.drop_target_register(DND_FILES)
                target.dnd_bind("<<Drop>>", self._on_file_drop)
                target.dnd_bind("<<DragEnter>>", self._on_drag_enter)
                target.dnd_bind("<<DragLeave>>", self._on_drag_leave)
            except Exception as e:
                print(f"Ошибка привязки DnD: {e}")

    def _on_drag_enter(self, event):
        """Подсветка зоны сброса синим цветом при входе перетаскиваемого файла."""
        if self._drag_enter_count == 0:
            self.drop_frame.configure(
                border_color="dodgerblue",
                fg_color=("lightblue", "darkblue")
            )
        self._drag_enter_count += 1

    def _on_drag_leave(self, event):
        """Возврат исходного стиля, когда файл покидает зону сброса."""
        self._drag_enter_count = max(0, self._drag_enter_count - 1)
        if self._drag_enter_count == 0:
            self._reset_drop_style()

    def _reset_drop_style(self):
        """Сброс оформления зоны сброса на исходное."""
        self.drop_frame.configure(
            border_color=self._default_border,
            fg_color=self._default_fg
        )
        self._drag_enter_count = 0   # гарантированный сброс счётчика

    def _parse_dnd_paths(self, raw_data: str) -> list:
        if not raw_data:
            return []

        pattern = r"\{([^}]+)\}|(\S+)"
        matches = re.findall(pattern, raw_data)

        paths = []
        for match in matches:
            p = match[0] if match[0] else match[1]
            p = p.strip("{}'\"")
            if os.path.exists(p):
                paths.append(p)

        if not paths:
            try:
                paths = [
                    f.strip("{}'\"")
                    for f in self.tk.splitlist(raw_data)
                    if os.path.exists(f.strip("{}'\""))
                ]
            except Exception:
                pass

        return paths

    def _on_file_drop(self, event):
        """Обработка события Drop с восстановлением стиля."""
        self._reset_drop_style()  # убираем подсветку после сброса

        raw_files = self._parse_dnd_paths(event.data)

        if not raw_files:
            messagebox.showwarning(
                "Внимание", "Не удалось прочитать путь к перетащенному файлу."
            )
            return

        self.process_selected_files(raw_files)

    def _check_environment(self):
        if not Core.check_ffmpeg():
            messagebox.showwarning(
                "Внимание",
                "FFmpeg не обнаружен. Конвертация видео/аудио может не работать.",
            )

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

        self.current_mode = file_type
        default_fmt = "mp3" if self.current_mode == "audio" else "png"

        self.file_configs = []
        for path in file_list:
            self.file_configs.append(
                {"path": path, "format": default_fmt, "bitrate": "192k"}
            )

        self.update_tracks_list()
        self.show_second_step()

    def update_tracks_list(self):
        for widget in self.tracks_scroll_frame.winfo_children():
            widget.destroy()

        supported_formats = (
            Core.SUPPORTED_AUDIO_FORMATS
            if self.current_mode == "audio"
            else Core.SUPPORTED_IMAGE_FORMATS
        )

        for item in self.file_configs:
            path = item["path"]
            file_name = os.path.basename(path)
            ext = os.path.splitext(file_name)[1].upper().replace(".", "")

            try:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB"
            except OSError:
                size_str = "Н/Д"

            track_frame = ctk.CTkFrame(
                self.tracks_scroll_frame, fg_color=("gray85", "gray20")
            )
            track_frame.pack(fill="x", pady=3, padx=2)

            icon = "🎵" if self.current_mode == "audio" else "🖼️"
            lbl_info = ctk.CTkLabel(
                track_frame,
                text=f"{icon} {file_name}\n   [{ext} | {size_str}]",
                font=ctk.CTkFont(size=12, weight="bold"),
                justify="left",
                width=180,
            )
            lbl_info.pack(side="left", padx=10, pady=5)

            btn_remove = ctk.CTkButton(
                track_frame,
                text="✕",
                width=28,
                height=28,
                fg_color="#D32F2F",
                hover_color="#B71C1C",
                command=lambda p=path: self.remove_track(p),
            )
            btn_remove.pack(side="right", padx=(5, 10))

            combo_fmt = ctk.CTkOptionMenu(
                track_frame,
                values=supported_formats,
                width=80,
                command=lambda val, config=item: self._on_track_format_change(
                    config, val
                ),
            )
            combo_fmt.set(item["format"])
            combo_fmt.pack(side="right", padx=5)

            combo_bit = None
            if self.current_mode == "audio":
                combo_bit = ctk.CTkOptionMenu(
                    track_frame,
                    values=["128k", "192k", "256k", "320k"],
                    width=85,
                    command=lambda val, config=item: config.update({"bitrate": val}),
                )
                combo_bit.set(item["bitrate"])
                if item["format"] in ["wav", "flac"]:
                    combo_bit.configure(state="disabled")
                combo_bit.pack(side="right", padx=5)

            item["widget_bitrate"] = combo_bit

    def _on_track_format_change(self, config_dict: dict, new_format: str):
        config_dict["format"] = new_format
        if "widget_bitrate" in config_dict and config_dict["widget_bitrate"]:
            if new_format in ["wav", "flac"]:
                config_dict["widget_bitrate"].configure(state="disabled")
            else:
                config_dict["widget_bitrate"].configure(state="normal")

    def remove_track(self, file_path):
        self.file_configs = [
            item for item in self.file_configs if item["path"] != file_path
        ]
        if not self.file_configs:
            self.reset_to_first_step()
        else:
            self.update_tracks_list()

    def show_second_step(self):
        self.drop_frame.pack_forget()
        self.geometry("620x490")

        self.settings_frame.pack(padx=15, pady=(5, 5), fill="x")
        self.status_label.pack(pady=(5, 2))
        self.progressbar.pack(pady=5)
        self.action_btn_frame.pack(pady=10, fill="x")

        self.btn_open_dir.pack_forget()
        self.status_label.configure(
            text="Готов к параллельной конвертации", text_color="gray"
        )
        self.progressbar.set(0)

    def reset_to_first_step(self):
        self.settings_frame.pack_forget()
        self.status_label.pack_forget()
        self.progressbar.pack_forget()
        self.action_btn_frame.pack_forget()

        self.file_configs = []
        self.current_mode = None

        self.geometry("540x280")
        self.drop_frame.pack(fill="both", expand=True, padx=20, pady=15)

    def select_output_dir(self):
        directory = filedialog.askdirectory(title="Выберите папку для сохранения")
        if directory:
            self.entry_outdir.delete(0, "end")
            self.entry_outdir.insert(0, directory)

    def open_output_folder(self):
        target_dir = self.last_output_dir or self.entry_outdir.get().strip()
        if target_dir and os.path.exists(target_dir):
            os.startfile(target_dir)

    def start_conversion_thread(self):
        if not self.file_configs:
            return

        self.btn_reset.configure(state="disabled")
        self.btn_convert.configure(state="disabled")
        self.btn_browse_dir.configure(state="disabled")
        self.btn_open_dir.pack_forget()
        self.progressbar.set(0)

        threading.Thread(target=self._run_conversion, daemon=True).start()

    def _run_conversion(self):
        output_dir = self.entry_outdir.get().strip() or None

        def update_progress(current, total, file_name):
            self.status_label.configure(
                text=f"Параллельная обработка ({current}/{total}): {file_name}"
            )
            self.progressbar.set(current / total)

        successful, errors = Core.batch_convert_parallel(
            tasks=self.file_configs,
            output_dir=output_dir,
            progress_callback=update_progress,
        )

        self.btn_reset.configure(state="normal")
        self.btn_convert.configure(state="normal")
        self.btn_browse_dir.configure(state="normal")

        if successful:
            self.last_output_dir = os.path.dirname(successful[0])
            self.btn_open_dir.pack(side="right", padx=10)

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
                text="Все файлы успешно обработаны!", text_color="#2FA572"
            )
            messagebox.showinfo(
                "Успех", "Многопоточная конвертация успешно завершена!"
            )


if __name__ == "__main__":
    app = AudioImageConverterGUI()
    app.mainloop()