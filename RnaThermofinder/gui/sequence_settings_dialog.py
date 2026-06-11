"""
Sequence preprocessing settings dialog (CustomTkinter).
"""

import tkinter as tk
import customtkinter as ctk
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings_manager import SettingsManager

#Toast dialog
class _DialogToast(ctk.CTkFrame):
    _COLORS = {
        "info":    ("#2980b9", "#ffffff"),
        "success": ("#27ae60", "#ffffff"),
        "error":   ("#e74c3c", "#ffffff"),
        "warning": ("#f39c12", "#ffffff"),
    }

    def __init__(self, master, message: str, kind: str = "info", duration: int = 2500):
        bg, fg = self._COLORS.get(kind, self._COLORS["info"])
        super().__init__(master, fg_color=bg, corner_radius=8, height=36)
        ctk.CTkLabel(self, text=message, text_color=fg,
                     font=ctk.CTkFont(size=12)).pack(padx=14, pady=7)
        self._duration = duration

    def show(self):
        self.place(relx=0.5, rely=0.0, anchor="n", y=6)
        self.lift()
        self.after(self._duration, self._dismiss)

    def _dismiss(self):
        try:
            self.place_forget()
            self.destroy()
        except tk.TclError:
            pass

class SequenceSettingsDialogModern:
    """Dialog for configuring sequence preprocessing options (CTk)."""

    ACCENT = "#2980b9"

    def __init__(self, parent, settings_manager: SettingsManager):
        self.parent = parent
        self.settings_manager = settings_manager
        self.dialog = None

        self.append_enabled_var = None
        self.append_sequence_var = None
        self.append_position_var = None
        self.preview_var = None

    def show(self):
        self.dialog = ctk.CTkToplevel(self.parent)
        self.dialog.title("Sequence Processing Settings")
        self.dialog.geometry("720x520")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.after(100, self._try_grab)

        self._create_widgets()
        self._load_current_settings()
        self._update_preview()

        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_window()

    def _try_grab(self):
        """Safely grab focus — delayed for macOS compatibility."""
        try:
            if self.dialog.winfo_exists():
                self.dialog.grab_set()
        except tk.TclError:
            pass

    def _toast(self, message: str, kind: str = "info", duration: int = 2500):
        _DialogToast(self.dialog, message, kind, duration).show()

    def _create_widgets(self):
        main = ctk.CTkFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(main, text="Sequence Preprocessing Options",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 16))

        # ── Append Section ───────────────────────────────────────────────
        append_card = ctk.CTkFrame(main, corner_radius=10)
        append_card.pack(fill=tk.X, pady=(0, 12))

        ctk.CTkLabel(append_card, text="Append Sequence",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 6))

        self.append_enabled_var = tk.BooleanVar()
        ctk.CTkCheckBox(append_card, text="Enable sequence appending",
                        variable=self.append_enabled_var,
                        command=self._on_enable_changed
                        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Sequence input row
        seq_row = ctk.CTkFrame(append_card, fg_color="transparent")
        seq_row.pack(fill=tk.X, padx=16, pady=(0, 8))

        ctk.CTkLabel(seq_row, text="Sequence:").pack(side=tk.LEFT, padx=(0, 8))
        self.append_sequence_var = tk.StringVar()
        ctk.CTkEntry(seq_row, textvariable=self.append_sequence_var, width=140
                     ).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(seq_row, text="Validate", width=80,
                      command=self._validate_sequence).pack(side=tk.LEFT)

        self.append_sequence_var.trace_add("write", lambda *a: self._update_preview())

        # Position
        pos_row = ctk.CTkFrame(append_card, fg_color="transparent")
        pos_row.pack(fill=tk.X, padx=16, pady=(0, 8))

        ctk.CTkLabel(pos_row, text="Position:").pack(side=tk.LEFT, padx=(0, 8))
        self.append_position_var = tk.StringVar(value="end")
        ctk.CTkRadioButton(pos_row, text="Start (5' end)",
                           variable=self.append_position_var, value="start",
                           command=self._update_preview).pack(side=tk.LEFT, padx=(0, 14))
        ctk.CTkRadioButton(pos_row, text="End (3' end)",
                           variable=self.append_position_var, value="end",
                           command=self._update_preview).pack(side=tk.LEFT)

        ctk.CTkLabel(append_card,
                     text="Tip: AUG is commonly appended to study RNA thermometer hairpin melting effects",
                     font=ctk.CTkFont(size=11), text_color="gray"
                     ).pack(anchor="w", padx=16, pady=(0, 14))

        #Preview Section
        preview_card = ctk.CTkFrame(main, corner_radius=10)
        preview_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        ctk.CTkLabel(preview_card, text="Preview",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 6))

        self.preview_var = tk.StringVar()
        ctk.CTkLabel(preview_card, textvariable=self.preview_var,
                     font=ctk.CTkFont(family="Consolas", size=12),
                     text_color=self.ACCENT, justify="left"
                     ).pack(anchor="w", padx=16, pady=(0, 14))

        # Buttons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill=tk.X)

        ctk.CTkButton(btn_frame, text="Save Settings", width=140,
                      fg_color=self.ACCENT,
                      command=self._save_settings).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(btn_frame, text="Cancel", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.LEFT)

    def _load_current_settings(self):
        seq = self.settings_manager.settings.get("sequence_processing", {})
        self.append_enabled_var.set(seq.get("append_sequence_enabled", False))
        self.append_sequence_var.set(seq.get("append_sequence", "AUG"))
        self.append_position_var.set(seq.get("append_position", "end"))

    def _on_enable_changed(self):
        self._update_preview()

    def _validate_sequence(self):
        sequence = self.append_sequence_var.get().upper()
        if not sequence:
            self._toast("Please enter a sequence to append", "warning")
            return False

        invalid = set(sequence) - set("ACGU")
        if invalid:
            self._toast(f"Invalid characters: {', '.join(sorted(invalid))} — only A, C, G, U allowed", "error")
            return False

        self._toast(f"Sequence '{sequence}' is valid", "success")
        self.append_sequence_var.set(sequence)
        return True

    def _update_preview(self):
        if not self.append_enabled_var.get():
            self.preview_var.set("Appending disabled.\n\n"
                                "Original: AUGCGAUUCGAGCUAG\n"
                                "Result:   AUGCGAUUCGAGCUAG")
            return

        seq = self.append_sequence_var.get().upper()
        pos = self.append_position_var.get()
        example = "AUGCGAUUCGAGCUAG"
        result = (seq + example) if pos == "start" else (example + seq)
        text = f"Original: {example}\nResult:   {result}"
        if seq:
            end_label = "5' end (start)" if pos == "start" else "3' end (end)"
            text += f"\n\nAppended '{seq}' at {end_label}"
        self.preview_var.set(text)

    def _save_settings(self):
        if self.append_enabled_var.get():
            if not self._validate_sequence():
                return

        self.settings_manager.settings["sequence_processing"] = {
            "append_sequence_enabled": self.append_enabled_var.get(),
            "append_sequence": self.append_sequence_var.get().upper(),
            "append_position": self.append_position_var.get(),
        }
        self.settings_manager.save_settings()
        self._toast("Sequence processing settings saved", "success", duration=1000)
        # Close dialog after short delay so user sees the toast
        self.dialog.after(1200, self.dialog.destroy)
