"""Desktop GUI for the synchronized theme updater."""

import io
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import color_picker
from updater_core import APP_KEYS, run_updates


COLOR_INFO = (
    ("accent", "Accent", "Primary accent / cursor / lavender"),
    ("background", "Background", "Main application background"),
    ("foreground", "Foreground", "Primary text color"),
    ("highlight", "Highlight", "Secondary accent / mauve"),
    ("window", "Window", "Secondary surfaces / window background"),
)

APP_INFO = (
    ("vivaldi", "Vivaldi"),
    ("simple_new_tab", "Simple New Tab"),
    ("discord", "Discord / Vencord"),
    ("vscode", "VS Code"),
    ("wezterm", "WezTerm"),
    ("spicetify", "Spotify / Spicetify"),
)


def readable_text(hex_color):
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    return "#000000" if luminance > 160 else "#FFFFFF"


class QueueWriter(io.TextIOBase):
    def __init__(self, output_queue):
        self.output_queue = output_queue

    def write(self, text):
        if text:
            self.output_queue.put(("log", text))
        return len(text)

    def flush(self):
        return None


class ThemeUpdaterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Theme Updater V6")
        self.geometry("900x760")
        self.minsize(820, 690)

        self.output_queue = queue.Queue()
        self.worker = None

        self.mode_var = tk.StringVar(
            value="custom" if color_picker.USE_CUSTOM_COLORS else "default"
        )

        self.color_vars = {
            name: tk.StringVar(value=color_picker.CUSTOM_PALETTE[name])
            for name, _, _ in COLOR_INFO
        }

        self.app_vars = {
            key: tk.BooleanVar(value=True)
            for key, _ in APP_INFO
        }

        self.swatch_buttons = {}
        self.color_entries = {}
        self.pick_buttons = {}

        self._build_ui()
        self._apply_mode_to_controls()
        self._refresh_preview()
        self.after(80, self._drain_output_queue)

    def _build_ui(self):
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(
            outer,
            text="Theme Updater",
            font=("Segoe UI", 20, "bold"),
        )
        title.pack(anchor="w")

        subtitle = ttk.Label(
            outer,
            text=(
                "Choose Default for the fixed palette, or Custom to select "
                "your own colors with the Windows color picker."
            ),
        )
        subtitle.pack(anchor="w", pady=(2, 14))

        mode_box = ttk.LabelFrame(outer, text="Palette Mode", padding=12)
        mode_box.pack(fill="x")

        ttk.Radiobutton(
            mode_box,
            text="Default",
            value="default",
            variable=self.mode_var,
            command=self._on_mode_changed,
        ).pack(side="left", padx=(0, 18))

        ttk.Radiobutton(
            mode_box,
            text="Custom",
            value="custom",
            variable=self.mode_var,
            command=self._on_mode_changed,
        ).pack(side="left")

        self.mode_help = ttk.Label(mode_box, text="")
        self.mode_help.pack(side="right")

        colors_box = ttk.LabelFrame(outer, text="Colors", padding=12)
        colors_box.pack(fill="x", pady=(12, 0))

        colors_box.columnconfigure(2, weight=1)

        for row, (key, label, description) in enumerate(COLOR_INFO):
            ttk.Label(
                colors_box,
                text=label,
                font=("Segoe UI", 10, "bold"),
                width=12,
            ).grid(row=row, column=0, sticky="w", pady=5)

            swatch = tk.Button(
                colors_box,
                width=4,
                relief="solid",
                bd=1,
                command=lambda k=key: self._choose_color(k),
                cursor="hand2",
            )
            swatch.grid(row=row, column=1, padx=(0, 8), pady=4)
            self.swatch_buttons[key] = swatch

            entry = ttk.Entry(
                colors_box,
                textvariable=self.color_vars[key],
                width=14,
            )
            entry.grid(row=row, column=2, sticky="w", pady=4)
            entry.bind("<KeyRelease>", lambda event, k=key: self._on_hex_edited(k))
            entry.bind("<FocusOut>", lambda event, k=key: self._normalize_entry(k))
            self.color_entries[key] = entry

            choose = ttk.Button(
                colors_box,
                text="Choose Color...",
                command=lambda k=key: self._choose_color(k),
            )
            choose.grid(row=row, column=3, padx=(10, 10), pady=4)
            self.pick_buttons[key] = choose

            ttk.Label(
                colors_box,
                text=description,
            ).grid(row=row, column=4, sticky="w", pady=4)

        reset_row = ttk.Frame(colors_box)
        reset_row.grid(
            row=len(COLOR_INFO),
            column=0,
            columnspan=5,
            sticky="e",
            pady=(8, 0),
        )

        self.reset_custom_button = ttk.Button(
            reset_row,
            text="Reset Custom Colors",
            command=self._reset_custom,
        )
        self.reset_custom_button.pack(side="right")

        preview_box = ttk.LabelFrame(outer, text="Preview", padding=10)
        preview_box.pack(fill="x", pady=(12, 0))

        self.preview = tk.Frame(
            preview_box,
            height=100,
            bd=0,
            highlightthickness=0,
        )
        self.preview.pack(fill="x")
        self.preview.pack_propagate(False)

        self.preview_title = tk.Label(
            self.preview,
            text="Theme Preview",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
            padx=14,
        )
        self.preview_title.pack(fill="x", pady=(12, 4))

        preview_lower = tk.Frame(self.preview, bd=0)
        preview_lower.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.preview_lower = preview_lower

        self.preview_body = tk.Label(
            preview_lower,
            text="Foreground text",
            anchor="w",
            padx=8,
        )
        self.preview_body.pack(side="left", fill="both", expand=True)

        self.preview_accent = tk.Label(
            preview_lower,
            text=" ACCENT ",
            padx=12,
            pady=6,
        )
        self.preview_accent.pack(side="right", padx=(10, 0))

        apps_box = ttk.LabelFrame(outer, text="Applications", padding=12)
        apps_box.pack(fill="x", pady=(12, 0))

        for i, (key, label) in enumerate(APP_INFO):
            row = i // 3
            column = i % 3

            ttk.Checkbutton(
                apps_box,
                text=label,
                variable=self.app_vars[key],
            ).grid(
                row=row,
                column=column,
                sticky="w",
                padx=(0, 28),
                pady=3,
            )

        button_row = (len(APP_INFO) + 2) // 3

        ttk.Button(
            apps_box,
            text="Select All",
            command=lambda: self._set_all_apps(True),
        ).grid(row=button_row, column=0, sticky="w", pady=(10, 0))

        ttk.Button(
            apps_box,
            text="Clear All",
            command=lambda: self._set_all_apps(False),
        ).grid(row=button_row, column=1, sticky="w", pady=(10, 0))

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(14, 0))

        self.apply_button = ttk.Button(
            action_row,
            text="Apply Theme",
            command=self._apply_theme,
        )
        self.apply_button.pack(side="left")

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(action_row, textvariable=self.status_var).pack(
            side="left", padx=(12, 0)
        )

        log_box = ttk.LabelFrame(outer, text="Update Log", padding=8)
        log_box.pack(fill="both", expand=True, pady=(12, 0))

        self.log = tk.Text(
            log_box,
            wrap="word",
            height=12,
            state="disabled",
            font=("Consolas", 9),
        )
        scrollbar = ttk.Scrollbar(log_box, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)

        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _set_all_apps(self, value):
        for var in self.app_vars.values():
            var.set(value)

    def _current_display_palette(self):
        if self.mode_var.get() == "default":
            return dict(color_picker.DEFAULT_PALETTE)

        colors = {}
        for key, _, _ in COLOR_INFO:
            try:
                colors[key] = color_picker.normalize_hex(self.color_vars[key].get())
            except ValueError:
                colors[key] = color_picker.CUSTOM_PALETTE[key]
        return colors

    def _on_mode_changed(self):
        self._apply_mode_to_controls()
        self._refresh_preview()

    def _apply_mode_to_controls(self):
        custom = self.mode_var.get() == "custom"

        for key, _, _ in COLOR_INFO:
            entry = self.color_entries[key]
            pick = self.pick_buttons[key]
            swatch = self.swatch_buttons[key]

            if custom:
                entry.state(["!disabled"])
                pick.state(["!disabled"])
                swatch.configure(state="normal", cursor="hand2")
            else:
                entry.state(["disabled"])
                pick.state(["disabled"])
                swatch.configure(state="disabled", cursor="arrow")

        if custom:
            self.reset_custom_button.state(["!disabled"])
            self.mode_help.configure(text="Color selection is enabled.")
        else:
            self.reset_custom_button.state(["disabled"])
            self.mode_help.configure(text="Fixed palette — color selection disabled.")

        self._refresh_swatches()

    def _choose_color(self, key):
        if self.mode_var.get() != "custom":
            return

        current = self.color_vars[key].get()
        try:
            current = color_picker.normalize_hex(current)
        except ValueError:
            current = color_picker.CUSTOM_PALETTE[key]

        chosen = color_picker.choose_color(
            parent=self,
            initial_color=current,
            title=f"Choose {key.replace('_', ' ').title()} Color",
        )

        if chosen:
            self.color_vars[key].set(chosen)
            self._refresh_swatches()
            self._refresh_preview()

    def _on_hex_edited(self, key):
        if self.mode_var.get() != "custom":
            return
        self._refresh_swatches()
        self._refresh_preview()

    def _normalize_entry(self, key):
        if self.mode_var.get() != "custom":
            return

        try:
            normalized = color_picker.normalize_hex(self.color_vars[key].get())
        except ValueError:
            return

        self.color_vars[key].set(normalized)
        self._refresh_swatches()
        self._refresh_preview()

    def _refresh_swatches(self):
        palette = self._current_display_palette()

        for key, _, _ in COLOR_INFO:
            value = palette[key]
            self.swatch_buttons[key].configure(
                bg=value,
                activebackground=value,
                fg=readable_text(value),
                activeforeground=readable_text(value),
            )

    def _refresh_preview(self):
        palette = self._current_display_palette()
        bg = palette["background"]
        fg = palette["foreground"]
        accent = palette["accent"]
        highlight = palette["highlight"]
        window = palette["window"]

        self.preview.configure(bg=bg)
        self.preview_title.configure(
            bg=bg,
            fg=highlight,
        )
        self.preview_lower.configure(bg=bg)
        self.preview_body.configure(
            bg=window,
            fg=fg,
        )
        self.preview_accent.configure(
            bg=accent,
            fg=readable_text(accent),
        )
        self._refresh_swatches()

    def _reset_custom(self):
        color_picker.reset_custom_palette(persist=False)

        for key, _, _ in COLOR_INFO:
            self.color_vars[key].set(color_picker.CUSTOM_PALETTE[key])

        self._refresh_swatches()
        self._refresh_preview()

    def _validated_custom_colors(self):
        values = {
            key: self.color_vars[key].get()
            for key, _, _ in COLOR_INFO
        }
        return color_picker.validate_palette(values)

    def _apply_theme(self):
        if self.worker and self.worker.is_alive():
            return

        selected = [
            key
            for key in APP_KEYS
            if self.app_vars[key].get()
        ]

        if not selected:
            messagebox.showwarning(
                "No applications selected",
                "Select at least one application to update.",
                parent=self,
            )
            return

        try:
            if self.mode_var.get() == "custom":
                colors = self._validated_custom_colors()
                color_picker.use_custom_palette(colors, persist=True)

                # Show normalized values back in the entries.
                for key, value in colors.items():
                    self.color_vars[key].set(value)
            else:
                color_picker.use_default_palette(persist=True)
        except ValueError as exc:
            messagebox.showerror(
                "Invalid color",
                str(exc),
                parent=self,
            )
            return

        self._refresh_preview()
        self._clear_log()
        self.apply_button.state(["disabled"])
        self.status_var.set("Updating...")

        self.worker = threading.Thread(
            target=self._run_worker,
            args=(selected,),
            daemon=True,
        )
        self.worker.start()

    def _run_worker(self, selected):
        writer = QueueWriter(self.output_queue)
        old_stdout, old_stderr = sys.stdout, sys.stderr

        try:
            sys.stdout = writer
            sys.stderr = writer
            run_updates(selected)
        except Exception as exc:
            self.output_queue.put(("error", f"{type(exc).__name__}: {exc}"))
        else:
            self.output_queue.put(("done", "Theme update completed successfully."))
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain_output_queue(self):
        try:
            while True:
                kind, payload = self.output_queue.get_nowait()

                if kind == "log":
                    self._append_log(payload)

                elif kind == "done":
                    self.apply_button.state(["!disabled"])
                    self.status_var.set("Completed.")
                    self._append_log("\n" + payload + "\n")
                    messagebox.showinfo(
                        "Theme Updater",
                        payload,
                        parent=self,
                    )

                elif kind == "error":
                    self.apply_button.state(["!disabled"])
                    self.status_var.set("Update failed.")
                    self._append_log("\nERROR: " + payload + "\n")
                    messagebox.showerror(
                        "Theme update failed",
                        payload,
                        parent=self,
                    )
        except queue.Empty:
            pass

        self.after(80, self._drain_output_queue)


def main():
    app = ThemeUpdaterGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
