"""
CSV Output Column Settings Dialog — CustomTkinter edition.
Drop-in replacement for settings_dialog_csv.py with dark-mode support.
Preserves all features: collapsible groups, search, presets, dependency indicators.
Temperature-aware: column groups, dependencies, and presets are generated
dynamically from the configured folding temperature list.
"""

import sys
import tkinter as tk
from tkinter import simpledialog
import customtkinter as ctk

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent.as_posix()))
from settings_manager import SettingsManager, DEFAULT_TEMPERATURES


# ─────────────────────────────────────────────────────────────────────────────
# Tooltip (lightweight CTk-aware)
# ─────────────────────────────────────────────────────────────────────────────
class _Tip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self._tw = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def update_text(self, t):
        self.text = t

    def _show(self, _evt=None):
        if not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tw = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify=tk.LEFT,
                 background="#f8f9fa", relief=tk.SOLID, borderwidth=1,
                 foreground="#2c3e50", font=("Segoe UI", 9),
                 padx=6, pady=4).pack()

    def _hide(self, _evt=None):
        if self._tw:
            self._tw.destroy()
            self._tw = None


# ─────────────────────────────────────────────────────────────────────────────
# Inline Toast for dialogs (self-contained, auto-dismiss)
# ─────────────────────────────────────────────────────────────────────────────
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
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
class SettingsDialogCSVModern:
    """Output Column Configuration dialog (CustomTkinter).

    Column groups, dependencies, and built-in presets are generated
    dynamically from the configured folding temperatures.
    """

    ACCENT = "#2980b9"

    # ─────────────────────────────────────────────────────────────────
    # Dynamic builders (replace former class-level constants)
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_column_groups(temps):
        """Build the COLUMN_GROUPS list for the given temperatures."""
        base = temps[0]
        t_first = temps[0]
        groups = []

        # Basic Information
        groups.append(("Basic Information", [
            ("name", "Name (Sequence ID)"),
            ("original_sequence", "Complete Sequence"),
            ("original_structure", "Complete Structure (dot-bracket)"),
        ]))

        # Full-Length Structures (non-base temps)
        fl_struct = [(f"full_structure_{t}", f"Full Structure at {t}\u00b0C")
                     for t in temps if t != base]
        if fl_struct:
            groups.append(("Full-Length Structures", fl_struct))

        # Complete Sequence MFE at Temperatures
        groups.append(("Complete Sequence MFE at Temperatures",
                       [(f"original_mfe_{t}", f"Original MFE at {t}\u00b0C") for t in temps]))

        # Complete Sequence Composition
        groups.append(("Complete Sequence Composition", [
            ("original_au_percent", "Original AU Percentage"),
            ("original_gc_percent", "Original GC Percentage"),
            ("original_gu_percent", "Original GU Percentage"),
        ]))

        # Complete Sequence Range Checks
        rc = [(f"original_mfe_{t}_in_range", f"Original MFE {t}\u00b0C In Range") for t in temps]
        rc += [("original_au_in_range", "Original AU% In Range"),
               ("original_gc_in_range", "Original GC% In Range"),
               ("original_gu_in_range", "Original GU% In Range")]
        groups.append(("Complete Sequence Range Checks", rc))

        # RBS Full Length Settings
        rbs_fl = []
        for t in temps:
            rbs_fl += [(f"full_rbs_{t}_seq", f"Full RBS {t}\u00b0C Sequence"),
                       (f"full_rbs_{t}_struct", f"Full RBS {t}\u00b0C Structure"),
                       (f"full_rbs_{t}_paired", f"Full RBS {t}\u00b0C Paired%")]
        if len(temps) >= 2:
            rbs_fl.append((f"rbs_seq_diff_{temps[-1]}_{t_first}",
                          f"RBS Sequestering \u0394({temps[-1]}-{t_first})"))
        if len(temps) >= 3:
            rbs_fl.append((f"rbs_seq_diff_{temps[-2]}_{t_first}",
                          f"RBS Sequestering \u0394({temps[-2]}-{t_first})"))
        groups.append(("RBS Full Length Settings", rbs_fl))

        # Terminal Hairpin Information
        groups.append(("Terminal Hairpin Information", [
            ("hairpin_detection_method", "Hairpin Detection Method"),
            ("hairpin_sequence", "Hairpin Sequence"),
            ("hairpin_structure", "Hairpin Structure"),
        ]))

        # Hairpin Composition
        groups.append(("Hairpin Composition", [
            ("hairpin_au_percent", "Hairpin AU Percentage"),
            ("hairpin_gc_percent", "Hairpin GC Percentage"),
            ("hairpin_gu_percent", "Hairpin GU Percentage"),
        ]))

        # Hairpin MFE at Temperatures
        groups.append(("Hairpin MFE at Temperatures",
                       [(f"mfe_{t}c_hairpin", f"Hairpin MFE at {t}\u00b0C") for t in temps]))

        # Hairpin MFE Range Checks
        groups.append(("Hairpin MFE Range Checks",
                       [(f"mfe_{t}_in_range_hairpin", f"Hairpin MFE {t}\u00b0C In Range") for t in temps]))

        # Hairpin Composition Range Checks
        groups.append(("Hairpin Composition Range Checks", [
            ("au_in_range_hairpin", "Hairpin AU% In Range"),
            ("gc_in_range_hairpin", "Hairpin GC% In Range"),
            ("gu_in_range_hairpin", "Hairpin GU% In Range"),
        ]))

        # RBS Analysis
        groups.append(("RBS Analysis", [
            ("rbs_sequence", "RBS Sequence"),
            ("rbs_structure", "RBS Structure"),
            ("rbs_paired_percent", "RBS Paired Percentage"),
        ]))

        # Quality Metrics
        groups.append(("Quality Metrics \u2014 Terminal Hairpin", [
            ("hp_quality_score", "Terminal Hairpin Quality Score (criteria passed)"),
            ("hp_quality_score_weighted", "Terminal Hairpin Quality Score (weighted %)"),
            ("hp_quality_score_class", "Terminal Hairpin Quality Score Class (tier)"),
            ("hp_quality_score_breakdown", "Terminal Hairpin Quality Score Breakdown"),
        ]))
        groups.append(("Quality Metrics \u2014 Full-Length", [
            ("fl_quality_score", "Full-Length Quality Score (criteria passed)"),
            ("fl_quality_score_weighted", "Full-Length Quality Score (weighted %)"),
            ("fl_quality_score_class", "Full-Length Quality Score Class (tier)"),
            ("fl_quality_score_breakdown", "Full-Length Quality Score Breakdown"),
        ]))

        # Partition Function — Full Sequence
        pf_full = []
        for t in temps:
            pf_full.append((f"pf_full_ensemble_{t}", f"PF Ensemble Energy at {t}\u00b0C"))
        for t in temps:
            pf_full.append((f"pf_full_mean_paired_{t}", f"PF Mean Paired Probability at {t}\u00b0C"))
        groups.append(("Partition Function \u2014 Full Sequence", pf_full))

        # Partition Function — Hairpin
        pf_hp = []
        for t in temps:
            pf_hp.append((f"pf_hp_ensemble_{t}", f"PF Hairpin Ensemble Energy at {t}\u00b0C"))
        for t in temps:
            pf_hp.append((f"pf_hp_mean_paired_{t}", f"PF Hairpin Mean Paired Prob at {t}\u00b0C"))
        groups.append(("Partition Function \u2014 Hairpin", pf_hp))

        # Partition Function — RBS Accessibility
        pf_rbs = [(f"pf_rbs_access_{t}", f"PF RBS Accessibility at {t}\u00b0C (%)") for t in temps]
        if len(temps) >= 2:
            pf_rbs.append((f"pf_rbs_diff_{temps[-1]}_{t_first}",
                          f"PF RBS Accessibility \u0394({temps[-1]}-{t_first})"))
        if len(temps) >= 3:
            pf_rbs.append((f"pf_rbs_diff_{temps[-2]}_{t_first}",
                          f"PF RBS Accessibility \u0394({temps[-2]}-{t_first})"))
        groups.append(("Partition Function \u2014 RBS Accessibility", pf_rbs))

        # PF Ensemble Range Checks (Hairpin)
        groups.append(("PF Ensemble Range Checks (Hairpin)",
                       [(f"pf_hp_ensemble_{t}_in_range", f"PF Ensemble {t}\u00b0C In Range")
                        for t in temps]))

        # RBS Range Check
        groups.append(("RBS Range Check", [
            ("rbs_paired_in_range", "RBS Paired % In Range"),
        ]))

        # Motif / Sequence Finder
        motif_cols = [
            ("motif_pattern",    "Motif Pattern"),
            ("motif_count",      "Motif Match Count"),
            ("motif_match_seq",  "Best Motif Match Sequence"),
            ("motif_match_pos",  "Best Motif Match Position"),
        ]
        for t in temps:
            motif_cols += [
                (f"motif_paired_pct_{t}", f"Motif Paired % at {t}\u00b0C"),
                (f"motif_struct_{t}",     f"Motif Structure at {t}\u00b0C"),
                (f"motif_pf_access_{t}",  f"Motif PF Accessibility at {t}\u00b0C"),
            ]
        if len(temps) >= 2:
            motif_cols += [
                (f"motif_paired_diff_{temps[-1]}_{t_first}",
                 f"Motif Paired \u0394({temps[-1]}-{t_first})"),
                (f"motif_pf_diff_{temps[-1]}_{t_first}",
                 f"Motif PF Access \u0394({temps[-1]}-{t_first})"),
            ]
        if len(temps) >= 3:
            motif_cols += [
                (f"motif_paired_diff_{temps[-2]}_{t_first}",
                 f"Motif Paired \u0394({temps[-2]}-{t_first})"),
                (f"motif_pf_diff_{temps[-2]}_{t_first}",
                 f"Motif PF Access \u0394({temps[-2]}-{t_first})"),
            ]
        groups.append(("Motif / Sequence Finder", motif_cols))

        return groups

    @staticmethod
    def _build_column_dependencies(temps):
        """Build the COLUMN_DEPENDENCIES dict for the given temperatures."""
        t_first = temps[0]
        deps = {}

        # Original MFE range checks
        for t in temps:
            deps[f"original_mfe_{t}_in_range"] = [f"original_mfe_{t}"]

        # Composition range checks (not temp-dependent)
        deps["original_au_in_range"] = ["original_au_percent"]
        deps["original_gc_in_range"] = ["original_gc_percent"]
        deps["original_gu_in_range"] = ["original_gu_percent"]

        # Hairpin MFE range checks
        for t in temps:
            deps[f"mfe_{t}_in_range_hairpin"] = [f"mfe_{t}c_hairpin"]

        deps["au_in_range_hairpin"] = ["hairpin_au_percent"]
        deps["gc_in_range_hairpin"] = ["hairpin_gc_percent"]
        deps["gu_in_range_hairpin"] = ["hairpin_gu_percent"]

        # RBS diffs
        if len(temps) >= 2:
            deps[f"rbs_seq_diff_{temps[-1]}_{t_first}"] = [
                f"full_rbs_{temps[-1]}_paired", f"full_rbs_{t_first}_paired"]
            deps[f"pf_rbs_diff_{temps[-1]}_{t_first}"] = [
                f"pf_rbs_access_{temps[-1]}", f"pf_rbs_access_{t_first}"]
        if len(temps) >= 3:
            deps[f"rbs_seq_diff_{temps[-2]}_{t_first}"] = [
                f"full_rbs_{temps[-2]}_paired", f"full_rbs_{t_first}_paired"]
            deps[f"pf_rbs_diff_{temps[-2]}_{t_first}"] = [
                f"pf_rbs_access_{temps[-2]}", f"pf_rbs_access_{t_first}"]

        # Quality scores (no deps)
        for prefix in ("hp_", "fl_"):
            for suffix in ("quality_score", "quality_score_weighted",
                           "quality_score_class", "quality_score_breakdown"):
                deps[f"{prefix}{suffix}"] = []

        # PF ensemble range checks
        for t in temps:
            deps[f"pf_hp_ensemble_{t}_in_range"] = [f"pf_hp_ensemble_{t}"]

        deps["rbs_paired_in_range"] = ["rbs_paired_percent"]
        deps["hairpin_detection_method"] = []

        # Motif diffs depend on per-temp motif paired %
        if len(temps) >= 2:
            deps[f"motif_paired_diff_{temps[-1]}_{t_first}"] = [
                f"motif_paired_pct_{temps[-1]}", f"motif_paired_pct_{t_first}"]
            deps[f"motif_pf_diff_{temps[-1]}_{t_first}"] = [
                f"motif_pf_access_{temps[-1]}", f"motif_pf_access_{t_first}"]
        if len(temps) >= 3:
            deps[f"motif_paired_diff_{temps[-2]}_{t_first}"] = [
                f"motif_paired_pct_{temps[-2]}", f"motif_paired_pct_{t_first}"]
            deps[f"motif_pf_diff_{temps[-2]}_{t_first}"] = [
                f"motif_pf_access_{temps[-2]}", f"motif_pf_access_{t_first}"]

        return deps

    @staticmethod
    def _build_builtin_presets(temps, column_groups):
        """Build the BUILTIN_PRESETS dict for the given temperatures."""
        t_first = temps[0]

        # Collect all column keys from groups
        all_keys = {}
        for _, cols in column_groups:
            for k, _ in cols:
                all_keys[k] = False

        def _make_config(enable_patterns=None, enable_exact=None):
            """Create a config dict — all False, then enable matching keys."""
            cfg = dict(all_keys)
            # Always enable basics
            cfg["name"] = True
            cfg["original_sequence"] = True
            cfg["original_structure"] = True
            if enable_exact:
                for k in enable_exact:
                    if k in cfg:
                        cfg[k] = True
            if enable_patterns:
                for k in cfg:
                    for pat in enable_patterns:
                        if k.startswith(pat):
                            cfg[k] = True
            return cfg

        # Hairpin Analysis preset
        hp_exact = [
            "hairpin_detection_method", "hairpin_sequence", "hairpin_structure",
            "hairpin_au_percent", "hairpin_gc_percent", "hairpin_gu_percent",
            "au_in_range_hairpin", "gc_in_range_hairpin", "gu_in_range_hairpin",
            "rbs_sequence", "rbs_structure", "rbs_paired_percent",
            "hp_quality_score", "hp_quality_score_weighted", "hp_quality_score_class",
        ]
        for t in temps:
            hp_exact += [f"mfe_{t}c_hairpin", f"mfe_{t}_in_range_hairpin"]
        hairpin_cfg = _make_config(enable_exact=hp_exact)

        # Full Sequence preset
        fs_exact = list(hp_exact)  # includes hairpin basics
        fs_exact += ["original_au_percent", "original_gc_percent", "original_gu_percent",
                     "original_au_in_range", "original_gc_in_range", "original_gu_in_range"]
        for t in temps:
            fs_exact += [f"original_mfe_{t}", f"original_mfe_{t}_in_range"]
        # Remove hairpin range checks from full-seq preset
        full_seq_cfg = _make_config(enable_exact=fs_exact)
        for t in temps:
            full_seq_cfg[f"mfe_{t}_in_range_hairpin"] = False
        full_seq_cfg["au_in_range_hairpin"] = False
        full_seq_cfg["gc_in_range_hairpin"] = False
        full_seq_cfg["gu_in_range_hairpin"] = False

        # Riboswitch preset — everything on
        ribo_cfg = {k: True for k in all_keys}

        return {
            "hairpin": {
                "name": "Hairpin Analysis",
                "description": "Hairpin-focused analysis with quality scoring",
                "config": hairpin_cfg,
            },
            "full_sequence": {
                "name": "Full Sequence",
                "description": "Complete sequence MFE & composition at all temperatures",
                "config": full_seq_cfg,
            },
            "riboswitch": {
                "name": "Riboswitch",
                "description": "RBS sequestering with partition function data",
                "config": ribo_cfg,
            },
        }

    def __init__(self, parent, settings_manager: SettingsManager):
        # ── Resolve temperatures and build dynamic structures ──
        self._temps = settings_manager.get_temperatures()
        self.COLUMN_GROUPS = self._build_column_groups(self._temps)
        self.COLUMN_DEPENDENCIES = self._build_column_dependencies(self._temps)
        self.BUILTIN_PRESETS = self._build_builtin_presets(self._temps, self.COLUMN_GROUPS)
        self.parent = parent
        self.settings_manager = settings_manager
        self.checkboxes: dict[str, tk.BooleanVar] = {}
        self.checkbox_widgets: dict[str, ctk.CTkCheckBox] = {}
        self.checkbox_frames: dict[str, ctk.CTkFrame] = {}
        self.group_collapsed: dict[str, bool] = {}
        self.group_content_frames: dict[str, ctk.CTkFrame] = {}
        self.group_containers: dict[str, ctk.CTkFrame] = {}
        self.group_header_btns: dict[str, ctk.CTkButton] = {}
        self.group_columns: dict[str, list] = {}
        self._applying_preset = False
        self._suppress_trace = False

        # Reverse deps
        self._reverse_deps: dict[str, list] = {}
        for derived, sources in self.COLUMN_DEPENDENCIES.items():
            for s in sources:
                self._reverse_deps.setdefault(s, []).append(derived)

        # Full-export preset (dynamic)
        all_keys = {}
        for _, cols in self.COLUMN_GROUPS:
            for k, _ in cols:
                all_keys[k] = True
        self.BUILTIN_PRESETS["full_export"] = {
            "name": "Full Export",
            "description": "All columns enabled",
            "config": all_keys,
        }

        # Dialog window
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Output Column Settings")
        self.dialog.geometry("880x920")
        self.dialog.minsize(780, 700)
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    # ─────────────────────────────────────────────────────────────────────
    def _toast(self, message: str, kind: str = "info", duration: int = 2500):
        _DialogToast(self.dialog, message, kind, duration).show()

    # ─────────────────────────────────────────────────────────────────────
    def _create_widgets(self):
        main = ctk.CTkFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=14, pady=(6, 10))
        main.grid_rowconfigure(2, weight=1)   # columns area expands
        main.grid_columnconfigure(0, weight=1)

        # ── Compact top bar: title + search + action buttons in one row ──
        top_bar = ctk.CTkFrame(main, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(top_bar, text="Output Column Configuration",
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(side=tk.LEFT, padx=(0, 12))

        # Search inline with title
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_columns())
        ctk.CTkEntry(top_bar, textvariable=self.search_var, width=160,
                     height=28, placeholder_text="Filter columns...",
                     font=ctk.CTkFont(size=11)).pack(side=tk.LEFT, padx=(0, 8))

        # Action buttons — compact, right-aligned
        for text, cmd in [("Select All", self._select_all),
                          ("None", self._deselect_all),
                          ("Expand", self._expand_all),
                          ("Collapse", self._collapse_all)]:
            ctk.CTkButton(top_bar, text=text, width=68, height=26,
                          font=ctk.CTkFont(size=10), corner_radius=4,
                          fg_color="gray40", hover_color="gray50",
                          command=cmd).pack(side=tk.LEFT, padx=1)

        # Info label (right side)
        self.info_var = tk.StringVar()
        ctk.CTkLabel(top_bar, textvariable=self.info_var,
                     font=ctk.CTkFont(size=10), text_color="gray"
                     ).pack(side=tk.RIGHT, padx=(8, 0))

        # ── Presets row: collapsible, single compact card ────────────────
        self._create_presets(main, row=1)

        # ── Scrollable columns area — gets ALL remaining space ───────────
        self._create_columns_area(main, row=2)

        # ── Bottom: status + buttons ─────────────────────────────────────
        bot = ctk.CTkFrame(main, fg_color="transparent")
        bot.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        self.status_var = tk.StringVar()
        ctk.CTkLabel(bot, textvariable=self.status_var,
                     font=ctk.CTkFont(size=10), text_color="gray"
                     ).pack(side=tk.LEFT)

        ctk.CTkButton(bot, text="Save Settings", width=120,
                      fg_color=self.ACCENT,
                      command=self._save_settings).pack(side=tk.RIGHT, padx=(8, 0))
        ctk.CTkButton(bot, text="Cancel", width=80,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ctk.CTkButton(bot, text="Reset Defaults", width=120,
                      fg_color="gray40", hover_color="gray50",
                      command=self._reset_to_defaults).pack(side=tk.RIGHT)

        self._update_status()

    # ─────────────────────────────────────────────────────────────────────
    def _create_presets(self, parent, row):
        card = ctk.CTkFrame(parent, corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 4))

        # Single row: Built-in presets + Custom presets — all inline
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill=tk.X, padx=10, pady=(5, 2))

        ctk.CTkLabel(row1, text="Presets:",
                     font=ctk.CTkFont(size=11, weight="bold")
                     ).pack(side=tk.LEFT, padx=(0, 6))

        for pk in ("hairpin", "full_sequence", "riboswitch", "full_export"):
            meta = self.BUILTIN_PRESETS[pk]
            b = ctk.CTkButton(row1, text=meta["name"], width=100, height=24,
                              font=ctk.CTkFont(size=10), corner_radius=4,
                              fg_color="gray40", hover_color="gray50",
                              command=lambda k=pk: self._apply_builtin(k))
            b.pack(side=tk.LEFT, padx=2)
            cnt = sum(1 for v in meta["config"].values() if v)
            _Tip(b, f"{meta['description']}\n{cnt}/{len(meta['config'])} columns")

        # Custom presets — second compact row
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill=tk.X, padx=10, pady=(0, 5))

        ctk.CTkLabel(row2, text="Custom:", font=ctk.CTkFont(size=10)
                     ).pack(side=tk.LEFT, padx=(0, 4))

        self.custom_combo = ctk.CTkComboBox(row2, width=150, height=24,
                                            state="readonly", values=[],
                                            font=ctk.CTkFont(size=10))
        self.custom_combo.pack(side=tk.LEFT, padx=2)
        self._refresh_custom()

        for text, cmd in [("Load", self._load_custom),
                          ("Delete", self._delete_custom),
                          ("Save As…", self._save_custom)]:
            ctk.CTkButton(row2, text=text, width=56, height=22,
                          font=ctk.CTkFont(size=9), corner_radius=4,
                          fg_color="gray40", hover_color="gray50",
                          command=cmd).pack(side=tk.LEFT, padx=2)

    # ─────────────────────────────────────────────────────────────────────
    def _create_columns_area(self, parent, row):
        scroll = ctk.CTkScrollableFrame(parent, corner_radius=10)
        scroll.grid(row=row, column=0, sticky="nsew", pady=(0, 4))

        current = self.settings_manager.settings["csv_output_columns"]

        for group_name, columns in self.COLUMN_GROUPS:
            self.group_columns[group_name] = columns
            # Start collapsed — cleaner look, user expands what they need
            self.group_collapsed[group_name] = True

            container = ctk.CTkFrame(scroll, fg_color="transparent")
            container.pack(fill=tk.X, pady=(1, 0))
            self.group_containers[group_name] = container

            # Header row: collapse button + All/None inline (single compact row)
            hdr_row = ctk.CTkFrame(container, fg_color="transparent", height=26)
            hdr_row.pack(fill=tk.X)
            hdr_row.pack_propagate(False)

            hdr = ctk.CTkButton(
                hdr_row, text="", anchor="w", height=26,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                text_color=("gray10", "gray90"),
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda g=group_name: self._toggle_group(g),
            )
            hdr.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.group_header_btns[group_name] = hdr

            ctk.CTkButton(hdr_row, text="All", width=32, height=20,
                          font=ctk.CTkFont(size=9), corner_radius=4,
                          fg_color="gray40", hover_color="gray50",
                          command=lambda g=group_name: self._select_group(g)
                          ).pack(side=tk.RIGHT, padx=(0, 2))
            ctk.CTkButton(hdr_row, text="None", width=38, height=20,
                          font=ctk.CTkFont(size=9), corner_radius=4,
                          fg_color="gray40", hover_color="gray50",
                          command=lambda g=group_name: self._deselect_group(g)
                          ).pack(side=tk.RIGHT, padx=(0, 2))

            # Thin separator
            ctk.CTkFrame(container, height=1,
                         fg_color=("gray78", "gray32")).pack(fill=tk.X, padx=4)

            # Content frame (collapsible) — starts hidden since collapsed
            content = ctk.CTkFrame(container, fg_color="transparent")
            # Don't pack — starts collapsed
            self.group_content_frames[group_name] = content

            for key, label in columns:
                fr = ctk.CTkFrame(content, fg_color="transparent", height=22)
                fr.pack(anchor="w", fill=tk.X, padx=(18, 0), pady=0)
                fr.pack_propagate(False)
                self.checkbox_frames[key] = fr

                var = tk.BooleanVar(value=current.get(key, False))
                cb = ctk.CTkCheckBox(fr, text=label, variable=var,
                                     font=ctk.CTkFont(size=11),
                                     height=18, checkbox_width=16,
                                     checkbox_height=16, corner_radius=3,
                                     border_width=2)
                cb.pack(side=tk.LEFT)
                self.checkboxes[key] = var
                self.checkbox_widgets[key] = cb

                if key in self.COLUMN_DEPENDENCIES:
                    deps = [self._col_label(d) for d in self.COLUMN_DEPENDENCIES[key]]
                    lbl = ctk.CTkLabel(fr, text="\u26d3",
                                       font=ctk.CTkFont(size=8),
                                       text_color="gray")
                    lbl.pack(side=tk.LEFT, padx=(3, 0))
                    _Tip(lbl, "Depends on: " + ", ".join(deps))

                var.trace_add("write", lambda *a, k=key: self._on_cb_changed(k))

            self._update_header(group_name)

    # ─────────────────────────────────────────────────────────────────────
    # Group operations
    # ─────────────────────────────────────────────────────────────────────
    def _toggle_group(self, g):
        if self.group_collapsed[g]:
            self.group_content_frames[g].pack(fill=tk.X)
            self.group_collapsed[g] = False
        else:
            self.group_content_frames[g].pack_forget()
            self.group_collapsed[g] = True
        self._update_header(g)

    def _update_header(self, g):
        cols = self.group_columns[g]
        en = sum(1 for k, _ in cols if self.checkboxes.get(k, tk.BooleanVar()).get())
        arrow = "\u25b6" if self.group_collapsed[g] else "\u25bc"
        self.group_header_btns[g].configure(text=f"  {arrow}  {g}  ({en}/{len(cols)})")

    def _expand_all(self):
        for g in self.group_columns:
            if self.group_collapsed[g]:
                self.group_content_frames[g].pack(fill=tk.X)
                self.group_collapsed[g] = False
                self._update_header(g)

    def _collapse_all(self):
        for g in self.group_columns:
            if not self.group_collapsed[g]:
                self.group_content_frames[g].pack_forget()
                self.group_collapsed[g] = True
                self._update_header(g)

    # ─────────────────────────────────────────────────────────────────────
    # Select / deselect
    # ─────────────────────────────────────────────────────────────────────
    def _select_all(self):
        self._suppress_trace = True
        for v in self.checkboxes.values():
            v.set(True)
        self._suppress_trace = False
        self._refresh_headers()
        self._update_status()

    def _deselect_all(self):
        self._suppress_trace = True
        for v in self.checkboxes.values():
            v.set(False)
        self._suppress_trace = False
        self._refresh_headers()
        self._update_status()

    def _select_group(self, g):
        self._suppress_trace = True
        for k, _ in self.group_columns[g]:
            if k in self.checkboxes:
                self.checkboxes[k].set(True)
        self._suppress_trace = False
        for k, _ in self.group_columns[g]:
            if k in self.COLUMN_DEPENDENCIES:
                self._auto_deps(k)
        self._update_header(g)
        self._update_status()

    def _deselect_group(self, g):
        self._suppress_trace = True
        for k, _ in self.group_columns[g]:
            if k in self.checkboxes:
                self.checkboxes[k].set(False)
        self._suppress_trace = False
        self._update_header(g)
        self._update_status()

    def _refresh_headers(self):
        for g in self.group_columns:
            self._update_header(g)

    # ─────────────────────────────────────────────────────────────────────
    # Search / filter
    # ─────────────────────────────────────────────────────────────────────
    def _filter_columns(self):
        q = self.search_var.get().strip().lower()
        if not q:
            # Restore all
            for g, cols in self.group_columns.items():
                for k, _ in cols:
                    self.checkbox_frames[k].pack(anchor="w", fill=tk.X, padx=(18, 0), pady=0)
                self.group_containers[g].pack(fill=tk.X, pady=(1, 0))
                if not self.group_collapsed[g]:
                    self.group_content_frames[g].pack(fill=tk.X)
                self._update_header(g)
            return

        for g, cols in self.group_columns.items():
            vis = 0
            for k, label in cols:
                if q in label.lower() or q in k.lower():
                    self.checkbox_frames[k].pack(anchor="w", fill=tk.X, padx=(18, 0), pady=0)
                    vis += 1
                else:
                    self.checkbox_frames[k].pack_forget()
            if vis == 0:
                self.group_containers[g].pack_forget()
            else:
                self.group_containers[g].pack(fill=tk.X, pady=(1, 0))
                self.group_content_frames[g].pack(fill=tk.X)
                self.group_collapsed[g] = False
                self._update_header(g)

    # ─────────────────────────────────────────────────────────────────────
    # Dependency handling
    # ─────────────────────────────────────────────────────────────────────
    def _on_cb_changed(self, key):
        if self._suppress_trace or self._applying_preset:
            return
        var = self.checkboxes.get(key)
        if not var:
            return
        if var.get() and key in self.COLUMN_DEPENDENCIES:
            self._auto_deps(key)
        elif not var.get() and key in self._reverse_deps:
            active = [self._col_label(d) for d in self._reverse_deps[key]
                      if self.checkboxes.get(d, tk.BooleanVar()).get()]
            if active:
                self.info_var.set(
                    f'Note: "{self._col_label(key)}" is used by: {", ".join(active[:3])}'
                )
                self.dialog.after(5000, lambda: self.info_var.set(""))

        for g, cols in self.group_columns.items():
            if key in [k for k, _ in cols]:
                self._update_header(g)
                break
        self._update_status()

    def _auto_deps(self, key):
        if key not in self.COLUMN_DEPENDENCIES:
            return
        changed_groups = set()
        for src in self.COLUMN_DEPENDENCIES[key]:
            v = self.checkboxes.get(src)
            if v and not v.get():
                self._suppress_trace = True
                v.set(True)
                self._suppress_trace = False
                for g, cols in self.group_columns.items():
                    if src in [k for k, _ in cols]:
                        changed_groups.add(g)
        for g in changed_groups:
            self._update_header(g)

    def _col_label(self, key):
        for _, cols in self.COLUMN_GROUPS:
            for k, lbl in cols:
                if k == key:
                    return lbl
        return key

    # ─────────────────────────────────────────────────────────────────────
    # Presets
    # ─────────────────────────────────────────────────────────────────────
    def _apply_builtin(self, pk):
        meta = self.BUILTIN_PRESETS[pk]
        self._apply_config(meta["config"])
        cnt = sum(1 for v in meta["config"].values() if v)
        self.info_var.set(f"{meta['name']}: {cnt}/{len(meta['config'])} columns")

    def _apply_config(self, cfg):
        self._applying_preset = True
        self._suppress_trace = True
        for k, v in cfg.items():
            if k in self.checkboxes:
                self.checkboxes[k].set(v)
        self._suppress_trace = False
        self._applying_preset = False
        self._refresh_headers()
        self._update_status()

    def _refresh_custom(self):
        names = sorted(self.settings_manager.get_custom_presets().keys())
        self.custom_combo.configure(values=names)
        if names:
            self.custom_combo.set(names[0])
        else:
            self.custom_combo.set("")

    def _load_custom(self):
        name = self.custom_combo.get()
        if not name:
            self._toast("Select a custom preset first", "warning")
            return
        presets = self.settings_manager.get_custom_presets()
        if name in presets:
            self._apply_config(presets[name])
            cnt = sum(1 for v in presets[name].values() if v)
            self.info_var.set(f'Custom "{name}": {cnt} columns loaded')

    def _save_custom(self):
        name = simpledialog.askstring("Save Preset", "Preset name:",
                                      parent=self.dialog)
        if not name or not name.strip():
            return
        name = name.strip()
        existing = self.settings_manager.get_custom_presets()
        if name in existing:
            # Use a simple confirmation dialog (CTk)
            confirm = ctk.CTkInputDialog(text=f'Preset "{name}" exists. Type YES to overwrite.',
                                         title="Overwrite?")
            val = confirm.get_input()
            if not val or val.strip().upper() != "YES":
                return
        cfg = {k: v.get() for k, v in self.checkboxes.items()}
        if self.settings_manager.save_custom_preset(name, cfg):
            self._refresh_custom()
            self.custom_combo.set(name)
            self._toast(f'Preset "{name}" saved', "success")

    def _delete_custom(self):
        name = self.custom_combo.get()
        if not name:
            return
        confirm = ctk.CTkInputDialog(text=f'Delete preset "{name}"? Type YES to confirm.',
                                     title="Delete Preset")
        val = confirm.get_input()
        if val and val.strip().upper() == "YES":
            if self.settings_manager.delete_custom_preset(name):
                self._refresh_custom()
                self._toast(f'Preset "{name}" deleted', "info")

    # ─────────────────────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────────────────────
    def _update_status(self):
        cnt = sum(1 for v in self.checkboxes.values() if v.get())
        self.status_var.set(f"{cnt} of {len(self.checkboxes)} columns selected")

    # ─────────────────────────────────────────────────────────────────────
    # Reset / Save
    # ─────────────────────────────────────────────────────────────────────
    def _reset_to_defaults(self):
        confirm = ctk.CTkInputDialog(text="Reset all columns to defaults? Type YES to confirm.",
                                     title="Reset Defaults")
        val = confirm.get_input()
        if val and val.strip().upper() == "YES":
            self.settings_manager.reset_to_defaults()
            self._apply_config(self.settings_manager.settings["csv_output_columns"])
            self._toast("Defaults restored", "success")

    def _save_settings(self):
        for k, v in self.checkboxes.items():
            self.settings_manager.settings["csv_output_columns"][k] = v.get()

        # Auto-enable calculations
        cols = self.settings_manager.settings["csv_output_columns"]
        calc = self.settings_manager.settings.get("calculation_settings", {})

        calc["calculate_original_mfe_temps"] = any(
            cols.get(k, False) for k in cols if k.startswith("original_mfe_"))
        calc["calculate_original_composition"] = any(
            cols.get(k, False) for k in ("original_au_percent", "original_gc_percent", "original_gu_percent"))
        calc["calculate_original_range_checks"] = any(
            cols.get(k, False) for k in cols
            if k.startswith("original_mfe_") and k.endswith("_in_range")
            or k in ("original_au_in_range", "original_gc_in_range", "original_gu_in_range"))

        rbs_keys = [k for k in cols if k.startswith("full_rbs_") or k.startswith("rbs_seq_diff_")]
        calc["calculate_rbs_full_length"] = any(cols.get(k, False) for k in rbs_keys)

        # Structures / RBS need original MFE temps
        struct_rbs = [k for k in cols if k.startswith("full_structure_") or k.startswith("full_rbs_")
                      or k.startswith("rbs_seq_diff_")]
        if any(cols.get(k, False) for k in struct_rbs):
            calc["calculate_original_mfe_temps"] = True

        pf_keys = [k for k in cols if k.startswith("pf_")]
        if any(cols.get(k, False) for k in pf_keys):
            calc["calculate_original_mfe_temps"] = True

        # Auto-enable motif search when any motif column is selected
        motif_keys = [k for k in cols if k.startswith("motif_")]
        motif_needed = any(cols.get(k, False) for k in motif_keys)
        calc["motif_search_enabled"] = motif_needed
        # Motif sequestering at all temps needs original MFE temps
        if motif_needed:
            calc["calculate_original_mfe_temps"] = True

        self.settings_manager.settings["calculation_settings"] = calc

        if self.settings_manager.save_settings():
            self._toast("Output settings saved — calculations optimised", "success")
            self.dialog.after(1200, self.dialog.destroy)
        else:
            self._toast("Failed to save settings", "error")

    # ─────────────────────────────────────────────────────────────────────
    def show(self):
        self.dialog.wait_window()
