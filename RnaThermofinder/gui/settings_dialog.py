"""
Settings dialogs for analysis parameters and performance.
"""

import os
import tkinter as tk
import customtkinter as ctk

from settings_manager import DEFAULT_TEMPERATURES

ACCENT = "#2980b9"


class AnalysisSettingsDialog:
    """Hairpin detection method + folding temperatures."""

    MAX_TEMPS = 5

    def __init__(self, parent, current_settings=None, csv_settings_manager=None):
        self.result = None
        self.csv_settings_manager = csv_settings_manager

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Analysis Settings")
        self.dialog.geometry("620x560")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.settings = current_settings or {
            'hairpin_detection_method': 'terminal',
        }

        self._create_widgets()

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        main = ctk.CTkFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(main, text="Analysis Settings",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 14))

        tabs = ctk.CTkTabview(main, corner_radius=10)
        tabs.pack(fill=tk.BOTH, expand=True)

        self._create_detection_tab(tabs.add("Hairpin Detection"))
        self._create_temps_tab(tabs.add("Folding Temperatures"))

        # Buttons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=(14, 0))

        ctk.CTkButton(btn_frame, text="Reset Defaults", width=130,
                      fg_color="gray40", hover_color="gray50",
                      command=self._reset_defaults).pack(side=tk.LEFT)
        ctk.CTkButton(btn_frame, text="Cancel", width=90,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ctk.CTkButton(btn_frame, text="Save", width=90,
                      fg_color=ACCENT,
                      command=self._save_settings).pack(side=tk.RIGHT)

    def _create_detection_tab(self, tab):
        ctk.CTkLabel(tab, text="Hairpin Detection Method:",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(8, 12))

        self.hairpin_method_var = tk.StringVar(
            value=self.settings.get('hairpin_detection_method', 'terminal'))

        ctk.CTkRadioButton(tab, text="Terminal Hairpin (original method)",
                           variable=self.hairpin_method_var, value="terminal"
                           ).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(tab,
                     text="Finds the rightmost stem-loop in the full structure.\n"
                          "This is the original algorithm used in RSAS.",
                     font=ctk.CTkFont(size=11), text_color="gray"
                     ).pack(anchor="w", padx=(28, 0), pady=(0, 14))

        ctk.CTkRadioButton(tab, text="RBS-Containing Hairpin (new method)",
                           variable=self.hairpin_method_var, value="rbs_based"
                           ).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(tab,
                     text="Finds the hairpin that sequesters the RBS (Shine-Dalgarno).\n"
                          "Falls back to AUG-containing hairpin for fourU-type thermometers.\n"
                          "If hairpin > 80 nt, cuts a window around the RBS instead.\n"
                          "Typical thermometer hairpin: 20-80 nt.",
                     font=ctk.CTkFont(size=11), text_color="gray"
                     ).pack(anchor="w", padx=(28, 0), pady=(0, 14))

        ctk.CTkLabel(tab,
                     text="Both methods feed the extracted hairpin into the same downstream\n"
                          "analysis pipeline (MFE, composition, quality score, etc.).",
                     font=ctk.CTkFont(size=11), text_color="#666666"
                     ).pack(anchor="w", pady=(10, 0))

        ctk.CTkLabel(tab,
                     text="Note: MFE/composition ranges are now configured in the\n"
                          "Terminal Hairpin Quality Score Builder.",
                     font=ctk.CTkFont(size=11), text_color="#888888"
                     ).pack(anchor="w", pady=(20, 0))

    def _create_temps_tab(self, tab):
        ctk.CTkLabel(tab, text="Folding Temperatures:",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(8, 4))

        ctk.CTkLabel(tab,
                     text="Configure the temperatures (\u00b0C) used for RNA folding.\n"
                          "The first (lowest) temperature is the base temperature for\n"
                          "hairpin detection and the primary structure fold.\n"
                          "You can set 1 to 5 unique temperatures.",
                     font=ctk.CTkFont(size=11), text_color="gray"
                     ).pack(anchor="w", pady=(0, 10))

        # Load current temps
        if self.csv_settings_manager:
            current_temps = self.csv_settings_manager.get_temperatures()
        else:
            current_temps = list(DEFAULT_TEMPERATURES)

        # Container for temperature entry rows
        self._temp_rows_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self._temp_rows_frame.pack(fill=tk.X, pady=(0, 8))

        self._temp_entries = []  # list of (frame, entry_var) tuples

        for t in current_temps:
            self._add_temp_row(t)

        # Add / Remove buttons
        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(4, 10))

        self._add_temp_btn = ctk.CTkButton(
            btn_row, text="+ Add Temperature", width=140,
            fg_color="#27ae60", hover_color="#2ecc71",
            command=self._add_temp_row_default)
        self._add_temp_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._temp_status_label = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._temp_status_label.pack(side=tk.LEFT)

        self._update_temp_buttons()

        # Info
        ctk.CTkLabel(tab,
                     text="Values are sorted automatically on save. Duplicate values\n"
                          "are merged. Temperatures must be positive numbers.\n\n"
                          "Default: 25, 37, 42",
                     font=ctk.CTkFont(size=11), text_color="#666666",
                     justify="left").pack(anchor="w", pady=(6, 0))

    def _add_temp_row(self, value=37):
        row = ctk.CTkFrame(self._temp_rows_frame, fg_color="transparent")
        row.pack(fill=tk.X, pady=2)

        var = tk.StringVar(value=str(value))
        idx = len(self._temp_entries) + 1

        ctk.CTkLabel(row, text=f"T{idx}:", font=ctk.CTkFont(size=12),
                     width=30).pack(side=tk.LEFT, padx=(0, 4))
        entry = ctk.CTkEntry(row, textvariable=var, width=80)
        entry.pack(side=tk.LEFT, padx=(0, 4))
        ctk.CTkLabel(row, text="\u00b0C", font=ctk.CTkFont(size=12)).pack(side=tk.LEFT)

        # Remove button
        remove_btn = ctk.CTkButton(
            row, text="\u2715", width=30, height=24,
            fg_color="gray40", hover_color="#c0392b",
            command=lambda r=row, v=var: self._remove_temp_row(r, v))
        remove_btn.pack(side=tk.LEFT, padx=(10, 0))

        self._temp_entries.append((row, var))
        self._update_temp_buttons()

    def _add_temp_row_default(self):
        if len(self._temp_entries) >= self.MAX_TEMPS:
            return
        self._add_temp_row(37)

    def _remove_temp_row(self, row_frame, var):
        if len(self._temp_entries) <= 1:
            return  # Must keep at least one
        self._temp_entries = [(r, v) for r, v in self._temp_entries
                              if r is not row_frame]
        row_frame.destroy()
        # Re-number labels
        for i, (r, v) in enumerate(self._temp_entries):
            for child in r.winfo_children():
                if isinstance(child, ctk.CTkLabel) and child.cget("text").startswith("T"):
                    child.configure(text=f"T{i + 1}:")
                    break
        self._update_temp_buttons()

    def _update_temp_buttons(self):
        n = len(self._temp_entries)
        if hasattr(self, '_add_temp_btn'):
            if n >= self.MAX_TEMPS:
                self._add_temp_btn.configure(state="disabled")
            else:
                self._add_temp_btn.configure(state="normal")
        if hasattr(self, '_temp_status_label'):
            self._temp_status_label.configure(text=f"{n}/{self.MAX_TEMPS} temperatures")

    def _get_temps_from_ui(self):
        """Parse temp entries, deduplicate, sort. Returns list or None."""
        raw = []
        for _, var in self._temp_entries:
            txt = var.get().strip()
            if not txt:
                continue
            try:
                val = float(txt)
                if val <= 0:
                    return None  # Non-positive
                raw.append(int(val) if val == int(val) else val)
            except ValueError:
                return None
        if not raw:
            return None
        # Deduplicate and sort
        temps = sorted(set(int(t) for t in raw))
        if len(temps) < 1 or len(temps) > self.MAX_TEMPS:
            return None
        return temps

    def _save_settings(self):
        temps = self._get_temps_from_ui()
        if temps is None:
            if hasattr(self, '_temp_status_label'):
                self._temp_status_label.configure(
                    text="Invalid: enter 1-5 unique positive numbers",
                    text_color="#e74c3c")
            return

        if self.csv_settings_manager:
            # Save folding temperatures
            self.csv_settings_manager.set_temperatures(temps)
            self.csv_settings_manager.save_settings()

        self.result = {
            'hairpin_detection_method': self.hairpin_method_var.get(),
            'folding_temperatures': temps,
        }
        self.dialog.destroy()

    def _reset_defaults(self):
        self.hairpin_method_var.set('terminal')

        # Reset temperatures
        for row_frame, _ in self._temp_entries:
            row_frame.destroy()
        self._temp_entries.clear()
        for t in DEFAULT_TEMPERATURES:
            self._add_temp_row(t)

    def show(self):
        self.dialog.wait_window()
        return self.result


class PerformanceSettingsDialog:
    """CPU core count for parallel processing."""

    def __init__(self, parent, csv_settings_manager=None):
        self.result = None
        self.csv_settings_manager = csv_settings_manager

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Performance Settings")
        self.dialog.geometry("480x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        main = ctk.CTkFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(main, text="Performance Settings",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 14))

        # CPU cores
        ctk.CTkLabel(main, text="Parallel Processing:",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(8, 14))

        self.system_cores = os.cpu_count() or 1
        current_cores = 1
        if self.csv_settings_manager:
            perf = self.csv_settings_manager.settings.get("performance_settings", {})
            current_cores = max(1, perf.get("num_cpu_cores", 1))

        row = ctk.CTkFrame(main, fg_color="transparent")
        row.pack(anchor="w", pady=4)
        ctk.CTkLabel(row, text="CPU Cores:", font=ctk.CTkFont(size=12)).pack(side=tk.LEFT, padx=(0, 10))

        self.cpu_cores_var = tk.IntVar(value=current_cores)
        ctk.CTkEntry(row, textvariable=self.cpu_cores_var, width=60).pack(side=tk.LEFT)

        ctk.CTkLabel(main,
                     text=f"Your system has {self.system_cores} core(s). You can use 1 to {self.system_cores}.",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", pady=(6, 2))

        ctk.CTkLabel(main,
                     text="Recommendation: Use 1 for small runs; for 100+ sequences, try 2-4 cores.",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", pady=(0, 14))

        ctk.CTkLabel(main,
                     text="Parallel processing distributes sequences across multiple\n"
                          "CPU cores for faster analysis. Each core processes sequences\n"
                          "independently using the same folding parameters.\n\n"
                          "Default is 1 core (sequential). Increase to 2 or more for\n"
                          "parallel runs. More cores = faster but higher memory usage.",
                     font=ctk.CTkFont(size=11), text_color="#666666",
                     justify="left").pack(anchor="w")

        # Buttons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=(14, 0))

        ctk.CTkButton(btn_frame, text="Cancel", width=90,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ctk.CTkButton(btn_frame, text="Save", width=90,
                      fg_color=ACCENT,
                      command=self._save_settings).pack(side=tk.RIGHT)

    def _save_settings(self):
        num_cores = max(1, min(self.cpu_cores_var.get(), self.system_cores))

        if self.csv_settings_manager:
            perf = self.csv_settings_manager.settings.setdefault("performance_settings", {})
            perf["num_cpu_cores"] = num_cores
            self.csv_settings_manager.save_settings()

        self.result = {'num_cpu_cores': num_cores}
        self.dialog.destroy()

    def show(self):
        self.dialog.wait_window()
        return self.result


SettingsDialogModern = AnalysisSettingsDialog
