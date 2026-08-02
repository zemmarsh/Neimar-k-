import logging
import os
import re
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from plyer import notification

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

        logging.info("Инициализация главного окна приложения")
        self.title("Универсальный Конвертер")
        self.geometry("540x280")
        self.resizable(True, True)

        self.file_configs = []
        self.current_mode = None
        self.last_output_dir = None
        self._drag_enter_count = 0
        self._default_border = None
        self._default_fg = None

        self._build_header()
        self._build_ui()

        self.after(200, self._setup_dnd)
        self.after(300, self._check_environment)

    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(10, 0))

        self.lbl_app_title = ctk.CTkLabel(
            self.header_frame,
            text="Media Converter PRO",
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
        self._default_border = ("gray70", "gray30")
        self._default_fg = ("gray90", "gray15")

        self.drop_frame = ctk.CTkFrame(
            self,
            corner_radius=15,
            border_width=2,
            border_color=self._default_border,
            fg_color=self._default_fg,
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

        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.tracks_scroll_frame = ctk.CTkScrollableFrame(
            self.settings_frame,
            height=260,
            label_text="Настройки файлов",
        )
        self.tracks_scroll_frame.pack(fill="x", padx=5, pady=5)

        self.global_params_frame = ctk.CTkFrame(self.settings_frame)
        self.global_params_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_outdir = ctk.CTkLabel(
            self.global_params_frame, text="Сохранить в:"
        )
        self.lbl_outdir.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.entry_outdir = ctk.CTkEntry(
            self.global_params_frame, placeholder_text="Рядом с исходниками"
        )
        self.entry_outdir.grid(
            row=0, column=1, padx=(10, 5), pady=5, sticky="ew"
        )

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
        self.progressbar = ctk.CTkProgressBar(self, width=640)
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
            text="Старт",
            width=120,
            fg_color="green",
            hover_color="darkgreen",
            command=self.start_conversion_thread,
        )
        self.btn_convert.pack(side="right", padx=10)

    def _setup_dnd(self):
        targets = [self.drop_frame, self.lbl_drop_icon, self.lbl_drop_text]

        for target in targets:
            try:
                target.drop_target_register(DND_FILES)
                target.dnd_bind("<<Drop>>", self._on_file_drop)
                target.dnd_bind("<<DragEnter>>", self._on_drag_enter)
                target.dnd_bind("<<DragLeave>>", self._on_drag_leave)
            except Exception as e:
                logging.error(f"Ошибка привязки DnD к элементу: {e}")

    def _on_drag_enter(self, event):
        if self._drag_enter_count == 0:
            self.drop_frame.configure(
                border_color="dodgerblue", fg_color=("lightblue", "darkblue")
            )
        self._drag_enter_count += 1

    def _on_drag_leave(self, event):
        self._drag_enter_count = max(0, self._drag_enter_count - 1)
        if self._drag_enter_count == 0:
            self._reset_drop_style()

    def _reset_drop_style(self):
        self.drop_frame.configure(
            border_color=self._default_border, fg_color=self._default_fg
        )
        self._drag_enter_count = 0

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
            except Exception as e:
                logging.warning(f"Ошибка парсинга DnD путей через tk.splitlist: {e}")

        return paths

    def _on_file_drop(self, event):
        self._reset_drop_style()
        raw_files = self._parse_dnd_paths(event.data)

        if not raw_files:
            logging.warning("Перетащенные файлы не найдены или не распознаны.")
            messagebox.showwarning(
                "Внимание", "Не удалось прочитать путь к перетащенному файлу."
            )
            return

        self.process_selected_files(raw_files)

    def _check_environment(self):
        if not Core.check_ffmpeg():
            messagebox.showwarning(
                "Внимание",
                "Не удалось инициализировать FFmpeg. Проверьте подключение к сети для первичной загрузки.",
            )

    def _parse_time_to_seconds(self, time_str: str) -> float:
        if not time_str.strip():
            return 0.0
        pattern = r"^(\d{1,2}:)?([0-5]?\d):([0-5]?\d)$"
        if not re.match(pattern, time_str.strip()):
            return -1.0
        parts = list(map(int, time_str.strip().split(":")))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return -1.0

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите файлы",
            filetypes=[
                (
                    "Все поддерживаемые",
                    "*.mp3 *.wav *.ogg *.flac *.m4a *.mp4 *.mkv *.avi *.mov *.flv *.wmv *.webm *.jpg *.jpeg *.png *.webp *.bmp",
                ),
                (
                    "Аудио и Видео",
                    "*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma *.opus *.mp4 *.mkv *.avi *.mov *.flv *.wmv *.webm",
                ),
                ("Изображения", "*.jpg *.jpeg *.png *.webp *.bmp *.ico *.tiff"),
                ("Все файлы", "*.*"),
            ],
        )
        if files:
            self.process_selected_files(list(files))

    def process_selected_files(self, file_list: list):
        logging.info(f"Получены файлы для обработки ({len(file_list)} шт.)")
        file_type = Core.detect_file_type(file_list)

        if file_type == "mixed":
            logging.warning("Пользователь выбрал одновременно видео/аудио и изображения.")
            messagebox.showerror(
                "Ошибка выбора",
                "Вы закинули одновременно медиафайлы (видео/аудио) и картинки!\n\nЗагружайте файлы одного типа за раз.",
            )
            return
        elif file_type == "unknown":
            logging.warning("Пользователь выбрал неполдерживаемые форматы.")
            messagebox.showerror(
                "Ошибка формата",
                "Среди выбранных нет поддерживаемых аудио, видео или картинок.",
            )
            return

        self.current_mode = file_type
        default_fmt = "mp3" if self.current_mode == "audio" else "png"

        self.file_configs = []
        for path in file_list:
            duration = (
                Core.get_media_duration(path)
                if self.current_mode == "audio"
                else 0
            )
            self.file_configs.append(
                {
                    "path": path,
                    "format": default_fmt,
                    "bitrate": "192k",
                    "strip_metadata": False,
                    "duration": duration,
                    "start_time": "",
                    "end_time": "",
                    "tags": {"title": "", "artist": "", "cover_path": ""},
                }
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
            ext = os.path.splitext(file_name)[1].lower()

            track_frame = ctk.CTkFrame(
                self.tracks_scroll_frame, fg_color=("gray85", "gray20")
            )
            track_frame.pack(fill="x", pady=4, padx=2)

            top_row = ctk.CTkFrame(track_frame, fg_color="transparent")
            top_row.pack(fill="x", padx=5, pady=2)

            icon = "🎬" if ext in Core.SUPPORTED_VIDEO_EXT else ("🎵" if self.current_mode == "audio" else "🖼️")

            lbl_info = ctk.CTkLabel(
                top_row,
                text=f"{icon} {file_name}",
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            )
            lbl_info.pack(side="left", padx=5)

            btn_remove = ctk.CTkButton(
                top_row,
                text="✕",
                width=24,
                height=24,
                fg_color="#D32F2F",
                hover_color="#B71C1C",
                command=lambda p=path: self.remove_track(p),
            )
            btn_remove.pack(side="right", padx=5)

            if self.current_mode == "audio":
                # Меню формата и битрейта в верхней строке справа
                combo_bit = ctk.CTkOptionMenu(
                    top_row,
                    values=["128k", "192k", "256k", "320k"],
                    width=80,
                    command=lambda val, config=item: self._on_bitrate_change(
                        config, val
                    ),
                )
                combo_bit.set(item["bitrate"])
                combo_bit.pack(side="right", padx=2)
                item["widget_bitrate"] = combo_bit

                combo_fmt = ctk.CTkOptionMenu(
                    top_row,
                    values=supported_formats,
                    width=75,
                    command=lambda val, config=item: self._on_track_format_change(
                        config, val
                    ),
                )
                combo_fmt.set(item["format"])
                combo_fmt.pack(side="right", padx=2)

                # Нижняя строка: Срез слева | Расчетный размер | Кнопка Авто | Кнопка Теги
                bottom_row = ctk.CTkFrame(track_frame, fg_color="transparent")
                bottom_row.pack(fill="x", padx=5, pady=(0, 4))

                lbl_trim = ctk.CTkLabel(bottom_row, text="Срез:", font=ctk.CTkFont(size=11))
                lbl_trim.pack(side="left", padx=(5, 2))

                entry_start = ctk.CTkEntry(bottom_row, width=65, placeholder_text="00:00:00")
                entry_start.pack(side="left", padx=2)
                entry_start.insert(0, item["start_time"])
                entry_start.bind("<KeyRelease>", lambda e, c=item, w=entry_start: c.update({"start_time": w.get().strip()}))

                lbl_dash = ctk.CTkLabel(bottom_row, text="-")
                lbl_dash.pack(side="left")

                entry_end = ctk.CTkEntry(bottom_row, width=65, placeholder_text="00:00:00")
                entry_end.pack(side="left", padx=2)
                entry_end.insert(0, item["end_time"])
                entry_end.bind("<KeyRelease>", lambda e, c=item, w=entry_end: c.update({"end_time": w.get().strip()}))

                # Кнопка тегов самая правая
                btn_tags = ctk.CTkButton(
                    bottom_row,
                    text="🏷️ Теги MP3",
                    width=85,
                    height=24,
                    fg_color="gray40",
                    state="normal" if item["format"] == "mp3" else "disabled",
                    command=lambda c=item: self.open_tags_popup(c),
                )
                btn_tags.pack(side="right", padx=5)
                item["widget_btn_tags"] = btn_tags

                # Кнопка авто левее от тегов (находится прямо под выбором битрейта)
                btn_analyze = ctk.CTkButton(
                    bottom_row,
                    text="💡 Авто",
                    width=80,
                    height=24,
                    font=ctk.CTkFont(size=11),
                    fg_color="#2b5b84",
                    hover_color="#1d3d59",
                    command=lambda c=item: self._auto_analyze_track(c),
                )
                btn_analyze.pack(side="right", padx=2)
                item["widget_btn_analyze"] = btn_analyze

                lbl_est_size = ctk.CTkLabel(
                    bottom_row, text="~0 MB", font=ctk.CTkFont(size=11), text_color="gray"
                )
                lbl_est_size.pack(side="right", padx=(0, 10))
                item["widget_size_label"] = lbl_est_size

                self._recalc_size_label(item)

            elif self.current_mode == "image":
                combo_fmt = ctk.CTkOptionMenu(
                    top_row,
                    values=supported_formats,
                    width=75,
                    command=lambda val, config=item: self._on_track_format_change(
                        config, val
                    ),
                )
                combo_fmt.set(item["format"])
                combo_fmt.pack(side="right", padx=5)

                chk_meta = ctk.CTkCheckBox(
                    top_row,
                    text="Очистить EXIF",
                    width=100,
                    command=lambda config=item: config.update(
                        {"strip_metadata": not config["strip_metadata"]}
                    ),
                )
                chk_meta.pack(side="right", padx=5)

    def _auto_analyze_track(self, config_dict: dict):
        res = Core.analyze_optimal_bitrate(config_dict["path"], config_dict["format"])
        recommended_bitrate = res["recommended_bitrate"]

        config_dict["bitrate"] = recommended_bitrate
        if "widget_bitrate" in config_dict and config_dict["widget_bitrate"]:
            config_dict["widget_bitrate"].set(recommended_bitrate)

        self._recalc_size_label(config_dict)
        messagebox.showinfo(
            "Анализ битрейта",
            f"Файл: {os.path.basename(config_dict['path'])}\n\n{res['reason']}",
        )

    def open_tags_popup(self, config_item):
        if config_item["format"] != "mp3":
            return

        popup = ctk.CTkToplevel(self)
        popup.title("Редактор MP3 тегов")
        popup.geometry("320x240")
        popup.grab_set()

        ctk.CTkLabel(popup, text="Название:").pack(anchor="w", padx=20, pady=(10, 0))
        entry_title = ctk.CTkEntry(popup, width=280)
        entry_title.insert(0, config_item["tags"].get("title", ""))
        entry_title.pack(padx=20, pady=2)

        ctk.CTkLabel(popup, text="Исполнитель:").pack(anchor="w", padx=20, pady=(5, 0))
        entry_artist = ctk.CTkEntry(popup, width=280)
        entry_artist.insert(0, config_item["tags"].get("artist", ""))
        entry_artist.pack(padx=20, pady=2)

        cover_path_var = ctk.StringVar(value=config_item["tags"].get("cover_path", ""))

        def choose_cover():
            path = filedialog.askopenfilename(filetypes=[("Картинки", "*.jpg *.jpeg *.png")])
            if path:
                cover_path_var.set(path)

        btn_cover = ctk.CTkButton(popup, text="🖼️ Выбрать обложку", command=choose_cover, fg_color="gray30")
        btn_cover.pack(padx=20, pady=10)

        def save():
            config_item["tags"]["title"] = entry_title.get().strip()
            config_item["tags"]["artist"] = entry_artist.get().strip()
            config_item["tags"]["cover_path"] = cover_path_var.get()
            popup.destroy()

        ctk.CTkButton(popup, text="Сохранить", command=save, fg_color="green").pack(padx=20, pady=5)

    def _on_track_format_change(self, config_dict: dict, new_format: str):
        config_dict["format"] = new_format

        is_raw = new_format in ["wav", "flac"]
        if "widget_bitrate" in config_dict and config_dict["widget_bitrate"]:
            config_dict["widget_bitrate"].configure(state="disabled" if is_raw else "normal")

        if "widget_btn_analyze" in config_dict and config_dict["widget_btn_analyze"]:
            config_dict["widget_btn_analyze"].configure(state="disabled" if is_raw else "normal")

        if "widget_btn_tags" in config_dict and config_dict["widget_btn_tags"]:
            config_dict["widget_btn_tags"].configure(state="normal" if new_format == "mp3" else "disabled")

        self._recalc_size_label(config_dict)

    def _on_bitrate_change(self, config_dict: dict, new_bitrate: str):
        config_dict["bitrate"] = new_bitrate
        self._recalc_size_label(config_dict)

    def _recalc_size_label(self, config_dict: dict):
        if "widget_size_label" in config_dict and config_dict["widget_size_label"]:
            if config_dict["format"] in ["wav", "flac"]:
                config_dict["widget_size_label"].configure(text="~RAW")
            else:
                mb = Core.estimate_audio_size(
                    config_dict["duration"], config_dict["bitrate"]
                )
                config_dict["widget_size_label"].configure(
                    text=f"~{mb:.1f} MB" if mb > 0 else "Н/Д"
                )

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
        self.geometry("680x560")

        self.settings_frame.pack(padx=15, pady=(5, 5), fill="x")
        self.status_label.pack(pady=(5, 2))
        self.progressbar.pack(pady=5)
        self.action_btn_frame.pack(pady=10, fill="x")

        self.btn_open_dir.pack_forget()
        self.status_label.configure(text="Готов к работе", text_color="gray")
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

        for item in self.file_configs:
            file_name = os.path.basename(item["path"])

            if not os.path.exists(item["path"]):
                messagebox.showerror("Ошибка", f"Файл не найден:\n{file_name}")
                return

            if self.current_mode == "audio":
                s_sec = self._parse_time_to_seconds(item["start_time"])
                e_sec = self._parse_time_to_seconds(item["end_time"])

                if s_sec == -1.0:
                    messagebox.showerror(
                        "Ошибка среза",
                        f"Файл {file_name}:\nНеверный формат времени начала (используйте ЧЧ:ММ:СС или ММ:СС)",
                    )
                    return
                if e_sec == -1.0:
                    messagebox.showerror(
                        "Ошибка среза",
                        f"Файл {file_name}:\nНеверный формат времени конца (используйте ЧЧ:ММ:СС или ММ:СС)",
                    )
                    return

                if s_sec > 0 and e_sec > 0 and s_sec >= e_sec:
                    messagebox.showerror(
                        "Ошибка логики",
                        f"Файл {file_name}:\nВремя начала не может быть больше или равно времени конца!",
                    )
                    return

        self.btn_reset.configure(state="disabled")
        self.btn_convert.configure(state="disabled")
        self.btn_browse_dir.configure(state="disabled")
        self.btn_open_dir.pack_forget()
        self.progressbar.set(0)

        threading.Thread(target=self._run_conversion, daemon=True).start()

    def _run_conversion(self):
        output_dir = self.entry_outdir.get().strip() or None

        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                logging.error(f"Не удалось создать директорию {output_dir}: {e}")

        def update_progress(current, total, file_name):
            self.status_label.configure(
                text=f"Обработка ({current}/{total}): {file_name}"
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

        try:
            notification.notify(
                title="Media Converter PRO",
                message=f"Обработано файлов: {len(successful)}. Ошибок: {len(errors)}.",
                timeout=5,
            )
        except Exception as e:
            logging.error(f"Ошибка вызова уведомления: {e}")

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
            messagebox.showinfo("Успех", "Готово! Все файлы обработаны.")


if __name__ == "__main__":
    app = AudioImageConverterGUI()
    app.mainloop()