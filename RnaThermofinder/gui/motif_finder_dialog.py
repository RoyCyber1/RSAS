"""
Motif / Sequence Finder settings dialog.
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from settings_manager import SettingsManager


# IUPAC reference for the help label
_IUPAC_HELP = (
    "Standard bases: A, C, G, U\n"
    "Degenerate codes:\n"
    "  R = A|G    Y = C|U    S = G|C    W = A|U\n"
    "  K = G|U    M = A|C    B = C|G|U  D = A|G|U\n"
    "  H = A|C|U  V = A|C|G  N = any"
)

ACCENT = "#2980b9"
ACCENT_HOVER = "#3498db"
MUTED = "#8b95a5"


class MotifFinderDialog:

    def __init__(self, parent, settings_manager: SettingsManager):
        self.parent = parent
        self.settings_manager = settings_manager
        self.result = None

        calc = settings_manager.settings.get("calculation_settings", {})
        self._initial_enabled = calc.get("motif_search_enabled", False)
        self._initial_pattern = calc.get("motif_pattern", "")

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Motif / Sequence Finder")
        self.dialog.geometry("560x680")
        self.dialog.resizable(True, True)
        self.dialog.minsize(480, 400)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

        # Centre on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        main = ctk.CTkFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        ctk.CTkLabel(main, text="Motif / Sequence Finder",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 2))
        ctk.CTkLabel(main,
                     text="Search for a custom motif in every sequence and analyse its sequestering",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(0, 14))

        # Enable toggle
        toggle_row = ctk.CTkFrame(main, fg_color="transparent")
        toggle_row.pack(fill=tk.X, pady=(0, 10))

        self.enabled_var = tk.BooleanVar(value=self._initial_enabled)
        ctk.CTkSwitch(toggle_row, text="Enable motif search during analysis",
                      variable=self.enabled_var,
                      font=ctk.CTkFont(size=13),
                      command=self._on_toggle).pack(side=tk.LEFT)

        # Pattern card
        pattern_card = ctk.CTkFrame(main, corner_radius=10)
        pattern_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(pattern_card, text="Motif Pattern",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        entry_row = ctk.CTkFrame(pattern_card, fg_color="transparent")
        entry_row.pack(fill=tk.X, padx=16, pady=(0, 4))

        self.pattern_var = tk.StringVar(value=self._initial_pattern)
        self.pattern_entry = ctk.CTkEntry(entry_row, textvariable=self.pattern_var,
                                           width=280, height=36,
                                           placeholder_text="e.g. AGGAGG, UAUAAUGU, NNUANN",
                                           font=ctk.CTkFont(family="Consolas", size=13))
        self.pattern_entry.pack(side=tk.LEFT, padx=(0, 8))

        self.validate_btn = ctk.CTkButton(entry_row, text="Validate", width=90,
                                           fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                           command=self._validate_pattern)
        self.validate_btn.pack(side=tk.LEFT)

        self.validation_label = ctk.CTkLabel(pattern_card, text="",
                                              font=ctk.CTkFont(size=11),
                                              text_color=MUTED)
        self.validation_label.pack(anchor="w", padx=16, pady=(0, 10))

        # IUPAC help card
        help_card = ctk.CTkFrame(main, corner_radius=10)
        help_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(help_card, text="IUPAC Nucleotide Codes",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(help_card, text=_IUPAC_HELP,
                     font=ctk.CTkFont(family="Consolas", size=11),
                     justify="left"
                     ).pack(anchor="w", padx=16, pady=(0, 12))

        # How it works
        how_card = ctk.CTkFrame(main, corner_radius=10)
        how_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ctk.CTkLabel(how_card, text="How It Works",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))
        how_text = (
            "1. Every input sequence is searched for occurrences of the motif.\n"
            "2. For the most-sequestered occurrence, the paired percentage is\n"
            "   computed at each configured folding temperature (MFE structure).\n"
            "3. If PF data is available, the mean unpaired probability (accessibility)\n"
            "   is reported as well.\n"
            "4. Temperature diffs show if the motif becomes more accessible at\n"
            "   elevated temperatures (thermometer-like response).\n\n"
            "Enable the motif output columns in Output Column Settings to see\n"
            "the results in CSV / Excel exports."
        )
        ctk.CTkLabel(how_card, text=how_text,
                     font=ctk.CTkFont(size=11), text_color=MUTED,
                     justify="left"
                     ).pack(anchor="w", padx=16, pady=(0, 12))

        # Buttons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=(4, 0))

        ctk.CTkButton(btn_frame, text="Save", width=120,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._save).pack(side=tk.RIGHT, padx=(8, 0))
        ctk.CTkButton(btn_frame, text="Cancel", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _on_toggle(self):
        state = "normal" if self.enabled_var.get() else "disabled"
        self.pattern_entry.configure(state=state)
        self.validate_btn.configure(state=state)

    def _validate_pattern(self):
        pattern = self.pattern_var.get().strip().upper()
        if not pattern:
            self.validation_label.configure(text="Enter a motif pattern", text_color="#e74c3c")
            return False

        valid_chars = set("ACGURYWSKMBDHVN")
        invalid = set(pattern) - valid_chars
        if invalid:
            self.validation_label.configure(
                text=f"Invalid characters: {', '.join(sorted(invalid))}",
                text_color="#e74c3c")
            return False

        if len(pattern) < 3:
            self.validation_label.configure(text="Motif should be at least 3 nt long",
                                             text_color="#f39c12")
            return True  # warning, not error

        if len(pattern) > 30:
            self.validation_label.configure(text="Motif should be 30 nt or shorter",
                                             text_color="#e74c3c")
            return False

        from RnaThermofinder.utils.motif_finder import _iupac_to_regex
        try:
            regex = _iupac_to_regex(pattern)
            if regex == pattern:
                self.validation_label.configure(
                    text=f"Valid exact pattern ({len(pattern)} nt)",
                    text_color="#27ae60")
            else:
                self.validation_label.configure(
                    text=f"Valid degenerate pattern ({len(pattern)} nt) \u2192 {regex}",
                    text_color="#27ae60")
        except ValueError as e:
            self.validation_label.configure(text=str(e), text_color="#e74c3c")
            return False

        return True

    def _save(self):
        enabled = self.enabled_var.get()
        pattern = self.pattern_var.get().strip().upper()

        if enabled and not pattern:
            messagebox.showwarning("Missing Pattern",
                                   "Please enter a motif pattern or disable the finder.",
                                   parent=self.dialog)
            return

        if enabled and not self._validate_pattern():
            return

        calc = self.settings_manager.settings.setdefault("calculation_settings", {})
        calc["motif_search_enabled"] = enabled
        calc["motif_pattern"] = pattern
        self.settings_manager.save_settings()

        self.result = {"motif_search_enabled": enabled, "motif_pattern": pattern}
        self.dialog.destroy()

    def show(self):
        self.dialog.wait_window()
        return self.result
