"""
RSAS: RNA Structure Analysis Suite — CustomTkinter Modern UI
Sidebar navigation, tabbed results, drag-and-drop, determinate progress,
recent files, keyboard shortcuts, toast notifications — all CustomTkinter.
"""

import json
import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

# ── project imports ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings_manager import SettingsManager
from RnaThermofinder.core import FastaParse, HairpinAnalysis

# Dialog imports (CTk-based)
from .settings_dialog import AnalysisSettingsDialog, PerformanceSettingsDialog, SettingsDialogModern
from .settings_dialog_csv import SettingsDialogCSVModern
from .sequence_settings_dialog import SequenceSettingsDialogModern
from .upstream_extractor_dialog import SequenceExtractorDialog
from .quality_score_builder import QualityScoreBuilderDialog
from .motif_finder_dialog import MotifFinderDialog
from .synthetic_pool_dialog import SyntheticPoolDialog


# ═══════════════════════════════════════════════════════════════════════════
# Colour tokens  (shared across light + dark)
# ═══════════════════════════════════════════════════════════════════════════
ACCENT        = "#2980b9"
ACCENT_HOVER  = "#3498db"
SUCCESS       = "#27ae60"
SUCCESS_HOVER = "#2ecc71"
ERROR         = "#e74c3c"
WARN          = "#f39c12"
HEADER_BG     = "#1a1d23"          # near-black header
SIDEBAR_BG    = ("#f0f2f5", "#1e2128")  # light / dark
SIDEBAR_HOVER = ("#e2e6ea", "#2a2f38")
SIDEBAR_SEL   = ("#dce3ea", "#313842")
MUTED         = "#8b95a5"
BADGE_BG      = "#e74c3c"
RECENT_BG     = ("#ffffff", "#22272e")
RECENT_HOVER  = ("#f5f7fa", "#2d333b")

RECENT_FILES_PATH = Path(__file__).parent.parent.parent / ".recent_files.json"
MAX_RECENT = 5


# ═══════════════════════════════════════════════════════════════════════════
# Toast notification (non-blocking, auto-dismiss)
# ═══════════════════════════════════════════════════════════════════════════
class Toast(ctk.CTkFrame):
    """Slide-in notification that auto-dismisses."""

    _COLORS = {
        "info":    ("#2980b9", "#ffffff"),
        "success": ("#27ae60", "#ffffff"),
        "error":   ("#e74c3c", "#ffffff"),
        "warning": ("#f39c12", "#ffffff"),
    }

    def __init__(self, master, message: str, kind: str = "info", duration: int = 3500):
        bg, fg = self._COLORS.get(kind, self._COLORS["info"])
        super().__init__(master, fg_color=bg, corner_radius=8, height=40)

        self._label = ctk.CTkLabel(
            self, text=message,
            text_color=fg,
            font=ctk.CTkFont(size=13),
        )
        self._label.pack(padx=16, pady=8)
        self._duration = duration

    def show(self):
        self.place(relx=0.5, rely=0.0, anchor="n", y=8)
        self.lift()
        self.after(self._duration, self._dismiss)

    def _dismiss(self):
        try:
            self.place_forget()
            self.destroy()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar button
# ═══════════════════════════════════════════════════════════════════════════
class SidebarButton(ctk.CTkButton):
    """Sidebar nav button with selected-state highlighting."""

    def __init__(self, master, text, icon="", command=None, **kw):
        display = f"  {icon}  {text}" if icon else f"  {text}"
        super().__init__(
            master,
            text=display,
            command=command,
            anchor="w",
            height=40,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color=SIDEBAR_HOVER,
            text_color=("gray10", "gray90"),
            **kw,
        )
        self._selected = False

    def set_selected(self, sel: bool):
        self._selected = sel
        self.configure(fg_color=SIDEBAR_SEL if sel else "transparent")


# ═══════════════════════════════════════════════════════════════════════════
# Main GUI
# ═══════════════════════════════════════════════════════════════════════════
class RSASApp:
    """Main GUI — sidebar + tabbed content area."""

    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("RSAS: RNA Structure Analysis Suite v3.0.0")
        self.root.geometry("1200x780")
        self.root.minsize(900, 600)

        # ── state ────────────────────────────────────────────────────────
        self.sequences = []
        self.results = []
        self.analysis_settings = {
            "hairpin_detection_method": "terminal",
        }
        self.status_var = tk.StringVar(value="Ready")

        # CSV / settings manager
        self.csv_settings_manager = SettingsManager("csv_output_settings.json")
        calc = self.csv_settings_manager.settings.get("calculation_settings", {})
        self.analysis_settings["hairpin_detection_method"] = calc.get(
            "hairpin_detection_method", "terminal"
        )
        perf = self.csv_settings_manager.settings.get("performance_settings", {})
        self.analysis_settings["num_cpu_cores"] = perf.get("num_cpu_cores", 1)

        # Output dir
        project_root = Path(__file__).parent.parent.parent
        self.output_dir = project_root / "Data" / "Outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Recent files
        self._recent_files: list[str] = self._load_recent_files()

        # ── build UI ─────────────────────────────────────────────────────
        self._build_layout()
        self._bind_shortcuts()

    # ──────────────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────────────
    def _build_layout(self):
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # ── Header bar ───────────────────────────────────────────────────
        header = ctk.CTkFrame(self.root, fg_color=HEADER_BG, height=50, corner_radius=0)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_propagate(False)

        # RNA icon (simple text glyph)
        ctk.CTkLabel(
            header, text="\u2699",  # gear/atom fallback
            font=ctk.CTkFont(size=22),
            text_color="#4fc3f7",
        ).pack(side=tk.LEFT, padx=(18, 6))

        ctk.CTkLabel(
            header, text="RSAS",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#ffffff",
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(
            header, text="RNA Structure Analysis Suite",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        ).pack(side=tk.LEFT, padx=(8, 0))

        ctk.CTkLabel(
            header, text="v3.0.0",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # Right side: appearance toggle
        self._appearance_var = ctk.StringVar(value=ctk.get_appearance_mode())
        appearance_menu = ctk.CTkOptionMenu(
            header,
            values=["System", "Light", "Dark"],
            variable=self._appearance_var,
            command=lambda v: ctk.set_appearance_mode(v),
            width=100,
            height=28,
            font=ctk.CTkFont(size=11),
        )
        appearance_menu.pack(side=tk.RIGHT, padx=18)
        ctk.CTkLabel(header, text="Theme:", text_color=MUTED,
                     font=ctk.CTkFont(size=11)).pack(side=tk.RIGHT)

        # ── Sidebar ─────────────────────────────────────────────────────
        self._sidebar = ctk.CTkFrame(self.root, width=200, corner_radius=0,
                                     fg_color=SIDEBAR_BG)
        self._sidebar.grid(row=1, column=0, sticky="ns")
        self._sidebar.grid_propagate(False)

        self._sidebar_buttons: dict[str, SidebarButton] = {}
        nav_items = [
            ("analyze",  "Analyze",           "\u25b6"),
            ("results",  "Results",           "\u2630"),
            ("settings", "Settings",          "\u2699"),
            ("upstream", "Sequence Extractor", "\u21c5"),
            ("pool",     "Synthetic Pool",     "\u2261"),
        ]
        ctk.CTkLabel(self._sidebar, text="NAVIGATION",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=16, pady=(18, 6))

        for key, label, icon in nav_items:
            btn = SidebarButton(
                self._sidebar, text=label, icon=icon,
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._sidebar_buttons[key] = btn

        # Sidebar bottom: keyboard shortcuts hint
        shortcut_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        shortcut_frame.pack(side=tk.BOTTOM, fill="x", padx=12, pady=12)
        mod = "Cmd" if sys.platform == "darwin" else "Ctrl"
        hints = [
            f"{mod}+O  Open file",
            f"{mod}+R  Run analysis",
            f"{mod}+E  Export",
        ]
        ctk.CTkLabel(shortcut_frame, text="SHORTCUTS",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=MUTED).pack(anchor="w", pady=(0, 4))
        for h in hints:
            ctk.CTkLabel(shortcut_frame, text=h,
                         font=ctk.CTkFont(size=10),
                         text_color=MUTED).pack(anchor="w")

        # ── Content area ─────────────────────────────────────────────────
        self._content = ctk.CTkFrame(self.root, fg_color="transparent")
        self._content.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Build pages (stacked)
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._build_analyze_page()
        self._build_results_page()
        self._build_settings_page()
        self._build_upstream_page()
        self._build_pool_page()

        # Show default page
        self._show_page("analyze")

        # ── Status bar ───────────────────────────────────────────────────
        status = ctk.CTkFrame(self.root, height=28, corner_radius=0,
                              fg_color=("gray90", "gray17"))
        status.grid(row=2, column=0, columnspan=2, sticky="ew")
        status.grid_propagate(False)
        ctk.CTkLabel(status, textvariable=self.status_var,
                     font=ctk.CTkFont(size=11), anchor="w",
                     ).pack(fill="x", padx=14, pady=3)

    # ──────────────────────────────────────────────────────────────────────
    # Page switching
    # ──────────────────────────────────────────────────────────────────────
    def _show_page(self, key: str):
        for name, page in self._pages.items():
            page.grid_forget()
        self._pages[key].grid(row=0, column=0, sticky="nsew")
        for name, btn in self._sidebar_buttons.items():
            btn.set_selected(name == key)

    # ──────────────────────────────────────────────────────────────────────
    # Page: Analyze
    # ──────────────────────────────────────────────────────────────────────
    def _build_analyze_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        self._pages["analyze"] = page

        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(3, weight=1)  # log area grows

        # ── File input section ───────────────────────────────────────────
        input_card = ctk.CTkFrame(page, corner_radius=10)
        input_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        input_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_card, text="Input File",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     ).grid(row=0, column=0, columnspan=3, sticky="w",
                            padx=16, pady=(14, 4))

        self.file_path_var = tk.StringVar()
        self._file_entry = ctk.CTkEntry(
            input_card, textvariable=self.file_path_var,
            placeholder_text="Drop a file here or click Browse  (FASTA / CSV / TSV / GenBank)",
            height=38,
        )
        self._file_entry.grid(row=1, column=0, columnspan=2, sticky="ew",
                              padx=(16, 8), pady=(0, 14))

        browse_btn = ctk.CTkButton(
            input_card, text="Browse", width=90, height=38,
            command=self.browse_file,
        )
        browse_btn.grid(row=1, column=2, padx=(0, 16), pady=(0, 14))

        # Drag-and-drop (bind on the entry widget + the entire card)
        for w in (self._file_entry, input_card):
            w.bind("<Button-1>", lambda e: None)  # don't steal focus
        self._setup_dnd(input_card)

        # ── File badge (shows count after loading) ───────────────────────
        self._file_badge_var = tk.StringVar(value="")
        self._file_badge = ctk.CTkLabel(
            input_card, textvariable=self._file_badge_var,
            font=ctk.CTkFont(size=11), text_color=SUCCESS,
        )
        self._file_badge.grid(row=2, column=0, columnspan=3, sticky="w",
                              padx=16, pady=(0, 8))

        # ── Recent files ─────────────────────────────────────────────────
        self._recent_frame = ctk.CTkFrame(page, corner_radius=10)
        self._recent_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        self._rebuild_recent_files_ui()

        # ── Action buttons ───────────────────────────────────────────────
        btn_row = ctk.CTkFrame(page, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))

        self.analyze_btn = ctk.CTkButton(
            btn_row, text="\u25b6  Run Analysis", width=160, height=40,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.run_analysis,
        )
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="Clear", width=80, height=40,
            fg_color="gray40", hover_color="gray50",
            command=self.clear_output,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.export_btn = ctk.CTkButton(
            btn_row, text="Export", width=100, height=40,
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            command=self.export_results, state=tk.DISABLED,
        )
        self.export_btn.pack(side=tk.LEFT)

        # ── Progress ─────────────────────────────────────────────────────
        progress_frame = ctk.CTkFrame(page, fg_color="transparent")
        progress_frame.grid(row=3, column=0, sticky="new", padx=20, pady=(0, 4))
        progress_frame.grid_columnconfigure(0, weight=1)

        self._progress_label_var = tk.StringVar(value="")
        ctk.CTkLabel(progress_frame, textvariable=self._progress_label_var,
                     font=ctk.CTkFont(size=11), text_color=MUTED,
                     ).grid(row=0, column=0, sticky="w")

        self.progress = ctk.CTkProgressBar(progress_frame, height=6, mode="determinate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        self.progress.set(0)

        # ── Log output ───────────────────────────────────────────────────
        log_frame = ctk.CTkFrame(page, corner_radius=10)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 12))
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(log_frame, text="Analysis Log",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     ).grid(row=0, column=0, sticky="nw", padx=14, pady=(10, 0))

        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word", corner_radius=6, border_width=0,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 10))
        log_frame.grid_rowconfigure(1, weight=1)

    # ──────────────────────────────────────────────────────────────────────
    # Page: Results (tabbed)
    # ──────────────────────────────────────────────────────────────────────
    def _build_results_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        self._pages["results"] = page
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)

        self._results_tabview = ctk.CTkTabview(page, corner_radius=10)
        self._results_tabview.grid(row=0, column=0, sticky="nsew", padx=20, pady=16)

        # Tab 1: Summary table
        tab_table = self._results_tabview.add("Results Table")
        tab_table.grid_rowconfigure(0, weight=1)
        tab_table.grid_columnconfigure(0, weight=1)

        self._results_table_text = ctk.CTkTextbox(
            tab_table, font=ctk.CTkFont(family="Consolas", size=11),
            wrap="none", corner_radius=6,
        )
        self._results_table_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Tab 2: Structure preview
        tab_struct = self._results_tabview.add("Structure Preview")
        tab_struct.grid_rowconfigure(0, weight=1)
        tab_struct.grid_columnconfigure(0, weight=1)

        self._structure_text = ctk.CTkTextbox(
            tab_struct, font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word", corner_radius=6,
        )
        self._structure_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Tab 3: Full log (mirror)
        tab_log = self._results_tabview.add("Full Log")
        tab_log.grid_rowconfigure(0, weight=1)
        tab_log.grid_columnconfigure(0, weight=1)

        self._results_log_text = ctk.CTkTextbox(
            tab_log, font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word", corner_radius=6,
        )
        self._results_log_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    # ──────────────────────────────────────────────────────────────────────
    # Page: Settings (cards)
    # ──────────────────────────────────────────────────────────────────────
    def _build_settings_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        self._pages["settings"] = page
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(page, text="Settings",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     ).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 12))

        cards_data = [
            ("Analysis Settings",
             "Hairpin detection method and folding temperatures",
             self.open_settings),
            ("Performance",
             "CPU core count for parallel processing",
             self.open_performance_settings),
            ("Terminal Hairpin Quality Score Builder",
             "Configure hairpin scoring criteria, weights, tolerance, and profiles",
             self.open_quality_score_builder),
            ("Full-Length Quality Score Builder",
             "Configure full-length scoring criteria for cancer research workflows",
             self.open_full_length_quality_score_builder),
            ("Output Columns",
             "Choose which columns to export to CSV / Excel",
             self.open_csv_settings),
            ("Sequence Options",
             "Prepend or append nucleotides (e.g. AUG) before analysis",
             self.open_sequence_settings),
            ("Motif / Sequence Finder",
             "Search for a custom motif and analyse its sequestering at each temperature",
             self.open_motif_finder),
        ]

        for i, (title, desc, cmd) in enumerate(cards_data):
            card = ctk.CTkFrame(page, corner_radius=10)
            card.grid(row=i + 1, column=0, sticky="ew", padx=24, pady=4)
            card.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(card, text=title,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 2))
            ctk.CTkLabel(card, text=desc,
                         font=ctk.CTkFont(size=12),
                         text_color=MUTED,
                         ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 14))
            ctk.CTkButton(
                card, text="Open", width=80,
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=cmd,
            ).grid(row=0, column=1, rowspan=2, sticky="e", padx=16)

    # ──────────────────────────────────────────────────────────────────────
    # Page: Sequence Extractor
    # ──────────────────────────────────────────────────────────────────────
    def _build_upstream_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        self._pages["upstream"] = page
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(page, text="Sequence Extractor",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     ).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(page, text="Extract upstream, downstream, or flanking sequences from genes using local files or fetch from NCBI",
                     font=ctk.CTkFont(size=12), text_color=MUTED,
                     ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 12))

        ctk.CTkButton(
            page, text="Open Sequence Extractor", width=220, height=42,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_upstream_extractor,
        ).grid(row=2, column=0, sticky="w", padx=24, pady=8)

    # ──────────────────────────────────────────────────────────────────────
    # Page: Synthetic Pool Generator
    # ──────────────────────────────────────────────────────────────────────
    def _build_pool_page(self):
        page = ctk.CTkFrame(self._content, fg_color="transparent")
        self._pages["pool"] = page
        page.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(page, text="Synthetic Pool Generator",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     ).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(page, text="Generate random RNA sequence pools with fixed motif inserts and optional composition filtering",
                     font=ctk.CTkFont(size=12), text_color=MUTED,
                     ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 12))

        ctk.CTkButton(
            page, text="Open Synthetic Pool Generator", width=240, height=42,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_pool_generator,
        ).grid(row=2, column=0, sticky="w", padx=24, pady=8)

    # ──────────────────────────────────────────────────────────────────────
    # Drag-and-drop (tkdnd fallback: OS file drop via tkinter)
    # ──────────────────────────────────────────────────────────────────────
    def _setup_dnd(self, widget):
        """Best-effort drag-and-drop.  Works when TkDND is available."""
        try:
            # Try tkdnd (requires python-tkdnd or TkinterDnD2)
            widget.drop_target_register("DND_Files")
            widget.dnd_bind("<<Drop>>", self._on_file_drop)
        except Exception:
            pass  # DnD not available — Browse button still works

    def _on_file_drop(self, event):
        path = event.data.strip().strip("{}")
        if os.path.isfile(path):
            self.file_path_var.set(path)
            self._add_recent_file(path)
            self._toast("File loaded", "info")

    # ──────────────────────────────────────────────────────────────────────
    # Keyboard shortcuts
    # ──────────────────────────────────────────────────────────────────────
    def _bind_shortcuts(self):
        mod = "Command" if sys.platform == "darwin" else "Control"
        self.root.bind(f"<{mod}-o>", lambda e: self.browse_file())
        self.root.bind(f"<{mod}-r>", lambda e: self.run_analysis())
        self.root.bind(f"<{mod}-e>", lambda e: self.export_results())

    # ──────────────────────────────────────────────────────────────────────
    # Recent files
    # ──────────────────────────────────────────────────────────────────────
    def _load_recent_files(self) -> list[str]:
        try:
            if RECENT_FILES_PATH.exists():
                return json.loads(RECENT_FILES_PATH.read_text())[:MAX_RECENT]
        except Exception:
            pass
        return []

    def _save_recent_files(self):
        try:
            RECENT_FILES_PATH.write_text(json.dumps(self._recent_files[:MAX_RECENT]))
        except Exception:
            pass

    def _add_recent_file(self, path: str):
        path = str(Path(path).resolve())
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:MAX_RECENT]
        self._save_recent_files()
        self._rebuild_recent_files_ui()

    def _rebuild_recent_files_ui(self):
        for child in self._recent_frame.winfo_children():
            child.destroy()

        if not self._recent_files:
            self._recent_frame.grid_remove()
            return

        self._recent_frame.grid()
        ctk.CTkLabel(self._recent_frame, text="Recent Files",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     ).pack(anchor="w", padx=14, pady=(10, 4))

        for fp in self._recent_files:
            name = Path(fp).name
            parent_dir = str(Path(fp).parent.name)
            display = f"{parent_dir}/{name}" if parent_dir else name
            btn = ctk.CTkButton(
                self._recent_frame,
                text=f"  {display}",
                anchor="w",
                fg_color="transparent",
                hover_color=RECENT_HOVER,
                text_color=("gray20", "gray80"),
                font=ctk.CTkFont(size=12),
                height=30,
                command=lambda p=fp: self._open_recent(p),
            )
            btn.pack(fill="x", padx=8, pady=1)

        # Small bottom padding
        ctk.CTkFrame(self._recent_frame, height=6, fg_color="transparent").pack()

    def _open_recent(self, path: str):
        if Path(path).exists():
            self.file_path_var.set(path)
            self._add_recent_file(path)
            self._toast(f"Loaded: {Path(path).name}", "info")
        else:
            self._recent_files.remove(path)
            self._save_recent_files()
            self._rebuild_recent_files_ui()
            self._toast("File no longer exists", "warning")

    # ──────────────────────────────────────────────────────────────────────
    # Toast helper
    # ──────────────────────────────────────────────────────────────────────
    def _toast(self, message: str, kind: str = "info", duration: int = 3500):
        t = Toast(self._content, message, kind, duration)
        t.show()

    # ──────────────────────────────────────────────────────────────────────
    # Dialog openers
    # ──────────────────────────────────────────────────────────────────────
    def open_settings(self):
        dialog = AnalysisSettingsDialog(self.root, self.analysis_settings,
                                        self.csv_settings_manager)
        result = dialog.show()
        if result:
            self.analysis_settings.update(result)
            calc = self.csv_settings_manager.settings.get("calculation_settings", {})
            calc["hairpin_detection_method"] = result.get(
                "hairpin_detection_method", "terminal"
            )
            self.csv_settings_manager.save_settings()
            temps = result.get("folding_temperatures")
            if temps:
                self._toast(f"Analysis settings updated (temps: {temps})", "success")
            else:
                self._toast("Analysis settings updated", "success")

    def open_performance_settings(self):
        dialog = PerformanceSettingsDialog(self.root, self.csv_settings_manager)
        result = dialog.show()
        if result:
            self.analysis_settings.update(result)
            self._toast("Performance settings updated", "success")

    def open_csv_settings(self):
        dialog = SettingsDialogCSVModern(self.root, self.csv_settings_manager)
        dialog.show()

    def open_sequence_settings(self):
        try:
            dialog = SequenceSettingsDialogModern(self.root, self.csv_settings_manager)
            dialog.show()
        except Exception as e:
            self._toast(f"Error: {e}", "error")

    def open_quality_score_builder(self):
        dialog = QualityScoreBuilderDialog(self.root, self.csv_settings_manager, mode="hairpin")
        dialog.show()

    def open_full_length_quality_score_builder(self):
        dialog = QualityScoreBuilderDialog(self.root, self.csv_settings_manager, mode="full_length")
        dialog.show()

    def open_motif_finder(self):
        dialog = MotifFinderDialog(self.root, self.csv_settings_manager)
        result = dialog.show()
        if result:
            pat = result.get("motif_pattern", "")
            enabled = result.get("motif_search_enabled", False)
            if enabled and pat:
                self._toast(f"Motif finder enabled: {pat}", "success")
            elif not enabled:
                self._toast("Motif finder disabled", "info")

    def _open_upstream_extractor(self):
        dialog = SequenceExtractorDialog(self.root)
        dialog.show()

    def _open_pool_generator(self):
        dialog = SyntheticPoolDialog(self.root)
        dialog.show()

    # ──────────────────────────────────────────────────────────────────────
    # File browsing
    # ──────────────────────────────────────────────────────────────────────
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select sequence file",
            filetypes=[
                ("FASTA files", "*.fasta *.fa"),
                ("CSV files", "*.csv"),
                ("TSV files", "*.tsv"),
                ("Two-column text", "*.txt"),
                ("GenBank files", "*.gb *.gbk"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            self.file_path_var.set(filename)
            self._add_recent_file(filename)

    # ──────────────────────────────────────────────────────────────────────
    # Logging
    # ──────────────────────────────────────────────────────────────────────
    def log(self, message: str):
        """Thread-safe log to both Analyze-page log and Results full log."""
        def _append():
            for tb in (self.log_text, self._results_log_text):
                tb.insert(tk.END, message + "\n")
                tb.see(tk.END)
        try:
            self.root.after(0, _append)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────
    # Analysis
    # ──────────────────────────────────────────────────────────────────────
    def clear_output(self):
        for tb in (self.log_text, self._results_log_text,
                   self._results_table_text, self._structure_text):
            tb.delete("1.0", tk.END)
        self.results = []
        self.sequences = []
        self.status_var.set("Ready")
        self.progress.set(0)
        self._progress_label_var.set("")
        self._file_badge_var.set("")
        self.export_btn.configure(state=tk.DISABLED)

    def run_analysis(self):
        file_path = self.file_path_var.get()
        if not file_path:
            self._toast("Please select a file first", "warning")
            return
        if not Path(file_path).exists():
            self._toast("Selected file does not exist", "error")
            return

        self._add_recent_file(file_path)
        self.analyze_btn.configure(state=tk.DISABLED)
        self.clear_output()
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_var.set("Loading sequences...")
        self._progress_label_var.set("Loading sequences...")

        thread = threading.Thread(target=self._perform_analysis,
                                  args=(file_path,), daemon=True)
        thread.start()

    def _perform_analysis(self, file_path: str):
        try:
            self.root.after(0, lambda: self.status_var.set("Loading sequences..."))

            self.sequences = FastaParse.load_sequences(
                file_path,
                convert_to_rna=True,
                validate_fasta=True,
            )

            num_seqs = len(self.sequences)

            # Switch to determinate progress
            def _switch_determinate():
                self.progress.stop()
                self.progress.configure(mode="determinate")
                self.progress.set(0)
                self._file_badge_var.set(f"{num_seqs} sequences loaded")
                self._progress_label_var.set(f"Analyzing 0 / {num_seqs} ...")
                self.status_var.set(f"Analyzing {num_seqs} sequences...")
            self.root.after(0, _switch_determinate)

            self._analysis_count = 0

            original_log = self.log

            def progress_log(message: str):
                original_log(message)
                updated = False
                # Sequential: count completed sequences
                if message.lstrip().startswith("Done ") or message.lstrip().startswith("Skipped "):
                    self._analysis_count += 1
                    updated = True
                # Parallel: parse "Progress: X/Y sequences"
                elif "Progress:" in message and "/" in message:
                    try:
                        part = message.split("Progress:")[1].strip()
                        done_str = part.split("/")[0].strip()
                        self._analysis_count = int(done_str)
                        updated = True
                    except (IndexError, ValueError):
                        pass
                # Parallel: "Parallel processing complete: X/Y sequences"
                elif "Parallel processing complete:" in message:
                    try:
                        part = message.split("complete:")[1].strip()
                        done_str = part.split("/")[0].strip()
                        self._analysis_count = int(done_str)
                        updated = True
                    except (IndexError, ValueError):
                        pass

                if updated:
                    frac = min(self._analysis_count / max(num_seqs, 1), 1.0)
                    count = min(self._analysis_count, num_seqs)
                    self.root.after(0, lambda f=frac: self.progress.set(f))
                    self.root.after(
                        0,
                        lambda c=count: self._progress_label_var.set(
                            f"Analyzing {c} / {num_seqs} ..."
                        ),
                    )

            self.results = HairpinAnalysis.calculate_results_final(
                self.sequences,
                self.output_dir,
                self.analysis_settings,
                progress_log,
                self.csv_settings_manager,
            )

            # Populate results tabs
            self.root.after(0, lambda: self._populate_results_tabs())

            self.root.after(0, lambda: self.progress.set(1.0))
            self.root.after(
                0,
                lambda: self._progress_label_var.set(
                    f"Done \u2014 {num_seqs} sequences processed"
                ),
            )
            self.root.after(
                0,
                lambda: self.status_var.set(
                    f"Analysis complete \u2014 {num_seqs} sequences"
                ),
            )
            self.root.after(0, lambda: self.export_btn.configure(state=tk.NORMAL))
            self.root.after(
                0,
                lambda: self._toast(
                    f"Analysis complete: {num_seqs} sequences", "success"
                ),
            )
            # Auto-switch to results page
            self.root.after(200, lambda: self._show_page("results"))

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            err_msg = str(e)
            self.root.after(0, lambda: self.status_var.set("Error occurred"))
            self.log(f"\nERROR: {err_msg}")
            self.log(error_details)
            self.root.after(0, lambda: self._toast(f"Error: {err_msg}", "error", 6000))

        finally:
            def _cleanup():
                self.analyze_btn.configure(state=tk.NORMAL)
                try:
                    self.progress.stop()
                except Exception:
                    pass
            self.root.after(0, _cleanup)

    # ──────────────────────────────────────────────────────────────────────
    # Populate results tabs after analysis
    # ──────────────────────────────────────────────────────────────────────
    def _populate_results_tabs(self):
        # Results table
        self._results_table_text.delete("1.0", tk.END)
        if self.results:
            # Build a simple text table from results
            # Header
            header_keys = []
            if self.results:
                first = self.results[0]
                if isinstance(first, dict):
                    header_keys = list(first.keys())

            if header_keys:
                # Show key columns in a readable format
                for i, result in enumerate(self.results):
                    self._results_table_text.insert(
                        tk.END, f"{'='*60}\n"
                    )
                    self._results_table_text.insert(
                        tk.END, f"  Sequence {i+1}\n"
                    )
                    self._results_table_text.insert(
                        tk.END, f"{'='*60}\n"
                    )
                    if isinstance(result, dict):
                        for k, v in result.items():
                            val_str = str(v)
                            if len(val_str) > 100:
                                val_str = val_str[:97] + "..."
                            self._results_table_text.insert(
                                tk.END, f"  {k:.<40s} {val_str}\n"
                            )
                    else:
                        self._results_table_text.insert(tk.END, str(result) + "\n")
                    self._results_table_text.insert(tk.END, "\n")
            else:
                for r in self.results:
                    self._results_table_text.insert(tk.END, str(r) + "\n")
        else:
            self._results_table_text.insert(tk.END, "No results available.\n")

        # Structure preview
        self._structure_text.delete("1.0", tk.END)
        if self.results:
            for i, result in enumerate(self.results):
                if isinstance(result, dict):
                    name = result.get("Name", result.get("name", f"Seq {i+1}"))
                    seq = result.get("Hairpin_Sequence",
                                    result.get("hairpin_sequence", ""))
                    struct = result.get("Hairpin_Structure",
                                       result.get("hairpin_structure", ""))
                    full_struct = result.get("Structure",
                                            result.get("original_structure", ""))

                    self._structure_text.insert(tk.END, f"> {name}\n")
                    if seq:
                        self._structure_text.insert(tk.END, f"  Hairpin:   {seq}\n")
                    if struct:
                        self._structure_text.insert(tk.END, f"  Structure: {struct}\n")
                    if full_struct and full_struct != struct:
                        # Show first 120 chars of full structure
                        preview = full_struct[:120]
                        if len(full_struct) > 120:
                            preview += "..."
                        self._structure_text.insert(
                            tk.END, f"  Full:      {preview}\n"
                        )
                    self._structure_text.insert(tk.END, "\n")

    # ──────────────────────────────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────────────────────────────
    def export_results(self):
        if not self.results:
            self._toast("Run analysis first", "warning")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"rna_results_{timestamp}.xlsx"

            output_file = filedialog.asksaveasfilename(
                title="Save Results As",
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel workbook", "*.xlsx"),
                    ("CSV files", "*.csv"),
                    ("All files", "*.*"),
                ],
                initialfile=default_filename,
                initialdir=str(Path.home() / "Downloads"),
            )
            if not output_file:
                return

            import shutil

            if output_file.endswith(".xlsx"):
                source_xlsx = self.output_dir / "rna_results.xlsx"
                if source_xlsx.exists():
                    shutil.copy2(source_xlsx, output_file)
                else:
                    from RnaThermofinder.utils.analysis_helpers import (
                        write_excel_with_tabs,
                    )
                    write_excel_with_tabs(
                        self.results, output_file, self.csv_settings_manager
                    )
            else:
                source_csv = self.output_dir / "rna_results.csv"
                if source_csv.exists():
                    shutil.copy2(source_csv, output_file)
                else:
                    self._toast("Results file not found", "error")
                    return

            self.log(f"\nResults exported to: {output_file}")
            self._toast(f"Exported: {Path(output_file).name}", "success")

            if messagebox.askyesno("Open Folder?",
                                   "Open the folder containing the file?"):
                self._open_folder(Path(output_file).parent)

        except Exception as e:
            self.log(f"Export failed: {e}")
            self._toast(f"Export failed: {e}", "error")

    def _open_folder(self, folder_path: Path):
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", str(folder_path)])
            else:
                subprocess.call(["xdg-open", str(folder_path)])
        except Exception as e:
            self.log(f"Could not open folder: {e}")


# Backward compatibility alias
RNAThermoFinderGUI = RSASApp


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════
def main():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    RSASApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
