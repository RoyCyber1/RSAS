"""
Switch Finder Dialog — detect temperature-dependent structural switching.

Finds a user-defined motif in loaded sequences, truncates each sequence at the
motif boundary, folds at each configured temperature, and reports whether the
motif transitions from paired to unpaired (thermometer/riboswitch behaviour).
"""

import csv
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings_manager import SettingsManager, get_user_data_dir

from RnaThermofinder.utils.motif_finder import _iupac_to_regex

ACCENT = "#2980b9"
ACCENT_HOVER = "#3498db"
MUTED = "#8b95a5"
SUCCESS = "#27ae60"
ERROR = "#e74c3c"
WARN = "#f39c12"

# CSV injection prefixes — sanitize cell values that could be interpreted as
# formulas by Excel/LibreOffice when opening the exported CSV.
_CSV_DANGER_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv(value) -> str:
    """Prefix dangerous cell values with a single quote to prevent formula injection."""
    s = str(value) if value is not None else ""
    if s and s[0] in _CSV_DANGER_PREFIXES:
        return "'" + s
    return s

# IUPAC reference
_IUPAC_HELP = (
    "Standard: A, C, G, U\n"
    "Degenerate: R=A|G  Y=C|U  S=G|C  W=A|U\n"
    "  K=G|U  M=A|C  B=C|G|U  D=A|G|U\n"
    "  H=A|C|U  V=A|C|G  N=any"
)


class SwitchFinderDialog:
    """Dialog for running switch finder analysis on loaded sequences."""

    def __init__(self, parent, sequences=None, settings_manager=None):
        """
        Parameters
        ----------
        parent : tk widget
            Parent window.
        sequences : list[dict] | None
            Pre-loaded sequences (each dict has 'name' and 'sequence').
            If None, the user can load a FASTA file from the dialog.
        settings_manager : SettingsManager | None
            Used to read configured folding temperatures.
        """
        self.parent = parent
        self._sequences = sequences or []
        self._sm = settings_manager or SettingsManager()
        self._running = False
        self._cancel_event = threading.Event()
        self._all_results = []
        self._cached_temps: list = []   # temps from the last analysis run

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Switch Finder")
        self.dialog.geometry("900x820")
        self.dialog.resizable(True, True)
        self.dialog.minsize(700, 600)
        self.dialog.transient(parent)
        # Delay grab_set for macOS — window must be fully mapped first
        self.dialog.after(100, self._try_grab)
        self.dialog.protocol("WM_DELETE_WINDOW", self._close)

        self._create_widgets()

        # Centre on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _create_widgets(self):
        main = ctk.CTkScrollableFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # ── Title ────────────────────────────────────────────────────
        ctk.CTkLabel(main, text="Switch Finder",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 2))
        ctk.CTkLabel(main,
                     text="Detect temperature-dependent structural switching around a motif",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(0, 14))

        # ── Input section ────────────────────────────────────────────
        input_card = ctk.CTkFrame(main, corner_radius=10)
        input_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(input_card, text="Input Sequences",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        seq_row = ctk.CTkFrame(input_card, fg_color="transparent")
        seq_row.pack(fill=tk.X, padx=16, pady=(0, 4))

        loaded_count = len(self._sequences)
        self._seq_label = ctk.CTkLabel(
            seq_row,
            text=f"{loaded_count} sequence(s) loaded from analysis"
            if loaded_count > 0 else "No sequences loaded — load a FASTA file below",
            font=ctk.CTkFont(size=12),
            text_color=SUCCESS if loaded_count > 0 else WARN,
        )
        self._seq_label.pack(side=tk.LEFT, padx=(0, 12))

        file_row = ctk.CTkFrame(input_card, fg_color="transparent")
        file_row.pack(fill=tk.X, padx=16, pady=(0, 10))

        self._file_var = tk.StringVar()
        ctk.CTkEntry(file_row, textvariable=self._file_var, width=400,
                     placeholder_text="Path to FASTA file (optional — overrides loaded sequences)"
                     ).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(file_row, text="Browse", width=80,
                      fg_color="gray40", hover_color="gray50",
                      command=self._browse_fasta).pack(side=tk.LEFT)

        # ── Motif pattern ────────────────────────────────────────────
        motif_card = ctk.CTkFrame(main, corner_radius=10)
        motif_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(motif_card, text="Motif Pattern",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        motif_row = ctk.CTkFrame(motif_card, fg_color="transparent")
        motif_row.pack(fill=tk.X, padx=16, pady=(0, 4))

        # Pre-fill from settings if motif search was enabled
        calc = self._sm.settings.get("calculation_settings", {})
        initial_motif = calc.get("motif_pattern", "")

        self._motif_var = tk.StringVar(value=initial_motif)
        self._motif_entry = ctk.CTkEntry(
            motif_row, textvariable=self._motif_var, width=260, height=36,
            placeholder_text="e.g. AGGAGG, UAUAAUGU, NNUANN",
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self._motif_entry.pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(motif_row, text="Validate", width=90,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._validate_motif).pack(side=tk.LEFT)

        self._valid_label = ctk.CTkLabel(motif_card, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color=MUTED)
        self._valid_label.pack(anchor="w", padx=16, pady=(0, 4))

        # IUPAC help (collapsed)
        ctk.CTkLabel(motif_card, text=_IUPAC_HELP,
                     font=ctk.CTkFont(family="Consolas", size=10),
                     text_color=MUTED, justify="left"
                     ).pack(anchor="w", padx=16, pady=(0, 10))

        # ── Parameters ───────────────────────────────────────────────
        param_card = ctk.CTkFrame(main, corner_radius=10)
        param_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(param_card, text="Analysis Parameters",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        param_grid = ctk.CTkFrame(param_card, fg_color="transparent")
        param_grid.pack(fill=tk.X, padx=16, pady=(0, 10))

        # Temperatures
        temps = self._sm.get_temperatures()
        ctk.CTkLabel(param_grid, text="Folding temperatures:",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w", pady=4)
        ctk.CTkLabel(param_grid, text=f"{', '.join(str(t) for t in temps)} °C  (from settings)",
                     font=ctk.CTkFont(size=12), text_color=MUTED
                     ).grid(row=0, column=1, sticky="w", padx=(8, 0), pady=4)

        # 3' flank
        ctk.CTkLabel(param_grid, text="3' flank (nt past motif):",
                     font=ctk.CTkFont(size=12)).grid(row=1, column=0, sticky="w", pady=4)
        self._flank3_var = tk.StringVar(value="0")
        ctk.CTkEntry(param_grid, textvariable=self._flank3_var, width=60
                     ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=4)

        # 5' flank (0 = keep all upstream)
        ctk.CTkLabel(param_grid, text="5' context (nt before motif, 0=all):",
                     font=ctk.CTkFont(size=12)).grid(row=2, column=0, sticky="w", pady=4)
        self._flank5_var = tk.StringVar(value="0")
        ctk.CTkEntry(param_grid, textvariable=self._flank5_var, width=60
                     ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        # Fold direction
        ctk.CTkLabel(param_grid, text="Fold direction:",
                     font=ctk.CTkFont(size=12)).grid(row=3, column=0, sticky="w", pady=4)
        self._direction_var = tk.StringVar(value="upstream")
        dir_menu = ctk.CTkOptionMenu(
            param_grid, variable=self._direction_var,
            values=["upstream", "downstream", "both"],
            width=140, font=ctk.CTkFont(size=12),
        )
        dir_menu.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=4)

        # PF toggle
        self._pf_var = tk.BooleanVar(value=True)
        ctk.CTkSwitch(param_grid, text="Include partition function accessibility",
                      variable=self._pf_var, font=ctk.CTkFont(size=12),
                      ).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)

        # ── How it works ─────────────────────────────────────────────
        how_card = ctk.CTkFrame(main, corner_radius=10)
        how_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(how_card, text="How It Works",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))
        how_text = (
            "1. Finds all occurrences of the motif in each sequence.\n"
            "2. Truncates the sequence based on fold direction:\n"
            "   \u2022 Upstream: cuts 3' of motif, folds against upstream only\n"
            "   \u2022 Downstream: cuts 5' of motif, folds against downstream only\n"
            "   \u2022 Both: tries both, picks the direction with highest switch score\n"
            "3. Folds the truncated sequence at each temperature (MFE + PF).\n"
            "4. Reports paired % of the motif region at each temperature.\n"
            "5. Extracts the partner sequence (bases pairing with motif at T_low).\n"
            "6. Switch Score = paired% at T_low \u2212 paired% at T_high.\n\n"
            "Classification:\n"
            "   Thermometer:  \u2265 50% Strong  |  \u2265 25% Moderate  |  \u2265 10% Weak\n"
            "   Riboswitch candidate:  \u2265 70% paired at all temps, < 10% switch\n"
            "     (stably sequestered \u2014 likely needs a ligand to open)\n"
            "   Accessible:  < 30% paired (motif not sequestered)"
        )
        ctk.CTkLabel(how_card, text=how_text,
                     font=ctk.CTkFont(size=11), text_color=MUTED,
                     justify="left").pack(anchor="w", padx=16, pady=(0, 12))

        # ── Action buttons ───────────────────────────────────────────
        btn_row = ctk.CTkFrame(main, fg_color="transparent")
        btn_row.pack(fill=tk.X, pady=(4, 8))

        self._run_btn = ctk.CTkButton(
            btn_row, text="Run Switch Analysis", width=200, height=40,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run_analysis,
        )
        self._run_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._cancel_btn = ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color=ERROR, hover_color="#c0392b",
            state="disabled",
            command=self._cancel_analysis,
        )
        self._cancel_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._export_btn = ctk.CTkButton(
            btn_row, text="Export CSV", width=120,
            fg_color="gray40", hover_color="gray50",
            state="disabled",
            command=self._export_results,
        )
        self._export_btn.pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="Close", width=80,
            fg_color="gray40", hover_color="gray50",
            command=self._close,
        ).pack(side=tk.RIGHT)

        # ── Progress / results ───────────────────────────────────────
        results_card = ctk.CTkFrame(main, corner_radius=10)
        results_card.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        ctk.CTkLabel(results_card, text="Results",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        self._results_text = ctk.CTkTextbox(
            results_card, height=250,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled", corner_radius=6,
        )
        self._results_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _try_grab(self):
        """Safely grab focus — delayed for macOS compatibility."""
        try:
            if self.dialog.winfo_exists():
                self.dialog.grab_set()
        except tk.TclError:
            pass

    def _close(self):
        if self._running:
            if not messagebox.askyesno(
                "Analysis Running",
                "An analysis is still running. Cancel and close?",
                parent=self.dialog,
            ):
                return
            self._cancel_event.set()
        self.dialog.grab_release()
        self.dialog.destroy()

    def _safe_after(self, func):
        """Schedule func on the main thread."""
        try:
            if self.dialog.winfo_exists():
                self.dialog.after(0, func)
        except tk.TclError:
            pass

    def _log(self, message: str):
        def _append():
            self._results_text.configure(state="normal")
            self._results_text.insert(tk.END, message + "\n")
            self._results_text.see(tk.END)
            self._results_text.configure(state="disabled")
        self._safe_after(_append)

    def _clear_log(self):
        def _clear():
            self._results_text.configure(state="normal")
            self._results_text.delete("1.0", tk.END)
            self._results_text.configure(state="disabled")
        self._safe_after(_clear)

    def _browse_fasta(self):
        path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Select FASTA file",
            filetypes=[("FASTA files", "*.fa *.fasta *.fna *.txt"),
                       ("All files", "*.*")],
        )
        if path:
            self._file_var.set(path)

    def _validate_motif(self) -> bool:
        pattern = self._motif_var.get().strip().upper()
        if not pattern:
            self._valid_label.configure(text="Enter a motif pattern", text_color=ERROR)
            return False

        valid_chars = set("ACGURYWSKMBDHVN")
        invalid = set(pattern) - valid_chars
        if invalid:
            self._valid_label.configure(
                text=f"Invalid characters: {', '.join(sorted(invalid))}",
                text_color=ERROR)
            return False

        if len(pattern) < 3:
            self._valid_label.configure(text="Motif should be at least 3 nt long",
                                        text_color=WARN)
            return True  # warning only

        if len(pattern) > 30:
            self._valid_label.configure(text="Motif should be 30 nt or shorter",
                                        text_color=ERROR)
            return False

        try:
            regex = _iupac_to_regex(pattern)
            info = f"Valid pattern ({len(pattern)} nt)"
            if regex != pattern:
                info += f" \u2192 {regex}"
            self._valid_label.configure(text=info, text_color=SUCCESS)
        except ValueError as e:
            self._valid_label.configure(text=str(e), text_color=ERROR)
            return False

        return True

    def _parse_sequences_from_fasta(self, path: str):
        """Minimal FASTA parser for standalone file loading."""
        seqs = []
        name = None
        buf = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue  # skip blank lines and FASTA comments
                if line.startswith(">"):
                    if name is not None:
                        seqs.append({"name": name, "sequence": "".join(buf)})
                    name = line[1:].split()[0]
                    buf = []
                elif name is not None:
                    buf.append(line.upper().replace("T", "U"))
            if name is not None:
                seqs.append({"name": name, "sequence": "".join(buf)})
        return seqs

    # ------------------------------------------------------------------
    # Run analysis
    # ------------------------------------------------------------------

    def _cancel_analysis(self):
        if self._running:
            self._cancel_event.set()
            self._log("\nCancelling...")

    def _run_analysis(self):
        if self._running:
            return

        motif = self._motif_var.get().strip().upper()
        if not motif:
            messagebox.showwarning("Missing Motif",
                                   "Please enter a motif pattern.",
                                   parent=self.dialog)
            return

        if not self._validate_motif():
            return

        # Get sequences — file overrides pre-loaded
        fasta_path = self._file_var.get().strip()
        if fasta_path:
            try:
                sequences = self._parse_sequences_from_fasta(fasta_path)
                if not sequences:
                    messagebox.showerror("Empty File",
                                         "No sequences found in the FASTA file.",
                                         parent=self.dialog)
                    return
            except Exception as e:
                messagebox.showerror("File Error", f"Could not read file:\n{e}",
                                     parent=self.dialog)
                return
        else:
            sequences = self._sequences

        if not sequences:
            messagebox.showwarning("No Sequences",
                                   "Load sequences via the main Analyze page or browse a FASTA file.",
                                   parent=self.dialog)
            return

        # Parse flank parameters
        try:
            flank3 = max(0, int(self._flank3_var.get().strip() or "0"))
        except ValueError:
            messagebox.showerror("Invalid Parameter",
                                 "3' flank must be a non-negative integer.",
                                 parent=self.dialog)
            return
        try:
            flank5 = max(0, int(self._flank5_var.get().strip() or "0"))
        except ValueError:
            messagebox.showerror("Invalid Parameter",
                                 "5' context must be a non-negative integer.",
                                 parent=self.dialog)
            return

        temps = self._sm.get_temperatures()
        use_pf = self._pf_var.get()
        direction = self._direction_var.get()

        # Cache temps for export (avoid re-reading settings later)
        self._cached_temps = list(temps)

        self._running = True
        self._cancel_event.clear()
        self._run_btn.configure(state="disabled", text="Running...")
        self._cancel_btn.configure(state="normal")
        self._export_btn.configure(state="disabled")
        self._all_results = []
        self._clear_log()
        self._log(f"Searching for motif '{motif}' in {len(sequences)} sequence(s)...")
        self._log(f"Temperatures: {temps} °C  |  PF: {'yes' if use_pf else 'no'}  |  Direction: {direction}")
        self._log(f"3' flank: {flank3} nt  |  5' context: {flank5 if flank5 > 0 else 'all'} nt")
        self._log("")

        cancel_event = self._cancel_event

        def _worker():
            try:
                from RnaThermofinder.utils.switch_finder import analyze_switch_batch

                def _progress(current, total):
                    if cancel_event.is_set():
                        raise InterruptedError("Analysis cancelled by user")
                    # Throttle: log every 10%, or every sequence if < 20 total
                    step = max(1, total // 10)
                    if current % step == 0 or current == total:
                        self._log(f"  [{current}/{total}] sequences processed")

                results = analyze_switch_batch(
                    sequences, motif, temps,
                    direction=direction,
                    flank_past_motif=flank3,
                    context_limit=flank5,
                    use_pf=use_pf,
                    progress_callback=_progress,
                )
                if not cancel_event.is_set():
                    self._all_results = results
                    self._safe_after(lambda: self._display_results(results, temps, use_pf))
            except InterruptedError:
                self._log("\nAnalysis cancelled.")
            except Exception as e:
                self._log(f"\nError: {e}")
                import traceback
                traceback.print_exc(file=sys.stderr)
            finally:
                def _done():
                    self._running = False
                    self._run_btn.configure(state="normal", text="Run Switch Analysis")
                    self._cancel_btn.configure(state="disabled")
                self._safe_after(_done)

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Display results
    # ------------------------------------------------------------------

    def _display_results(self, results, temps, use_pf):
        t_low = temps[0] if temps else 25
        t_high = temps[-1] if temps else 42

        total_hits = sum(len(r.get("hits", [])) for r in results)
        seqs_with_hits = sum(1 for r in results if r.get("hits"))

        self._log(f"\n{'=' * 80}")
        self._log(f"SWITCH FINDER RESULTS")
        self._log(f"{'=' * 80}")
        self._log(f"Sequences: {len(results)}  |  With motif: {seqs_with_hits}  |  Total hits: {total_hits}")
        self._log("")

        # Summary table header
        header_parts = [f"{'Sequence':<25}", f"{'Pos':>8}", f"{'Match':>10}", f"{'Dir':>6}"]
        for t in temps:
            header_parts.append(f"{'P%@' + str(t):>8}")
        if use_pf:
            for t in temps:
                header_parts.append(f"{'Acc@' + str(t):>8}")
        header_parts.append(f"{'Switch':>8}")
        header_parts.append(f"{'dMFE':>7}")
        header_parts.append(f"{'Class':>22}")
        header = " ".join(header_parts)

        self._log(header)
        self._log("-" * len(header))

        thermometers_found = 0
        riboswitch_candidates = 0
        fold_errors = 0

        for r in results:
            name = r.get("name", "?")
            hits = r.get("hits", [])
            if not hits:
                self._log(f"{name:<25}  (no motif found)")
                continue

            for hit in hits:
                s, e = hit["start"], hit["end"]
                matched = hit.get("matched_seq", "")
                direction = hit.get("direction", "?")
                dir_abbr = direction[:2] if direction else "?"

                parts = [f"{name:<25}", f"{s+1}-{e:>6}", f"{matched:>10}", f"{dir_abbr:>6}"]

                for t in temps:
                    pct = hit.get(f"paired_pct_{t}")
                    parts.append(f"{pct:>7.1f}%" if pct is not None else f"{'N/A':>8}")

                if use_pf:
                    for t in temps:
                        acc = hit.get(f"pf_access_{t}")
                        parts.append(f"{acc:>7.1f}%" if acc is not None else f"{'N/A':>8}")

                sw = hit.get("switch_score_mfe")
                parts.append(f"{sw:>+7.1f}%" if sw is not None else f"{'N/A':>8}")

                mfe_d = hit.get("mfe_delta")
                parts.append(f"{mfe_d:>+6.1f}" if mfe_d is not None else f"{'N/A':>7}")

                cls = hit.get("switch_class", "N/A")
                parts.append(f"{cls:>22}")

                if cls == "N/A":
                    fold_errors += 1
                elif "thermometer" in cls.lower() and "weak" not in cls.lower():
                    thermometers_found += 1
                elif cls == "Riboswitch candidate":
                    riboswitch_candidates += 1

                self._log(" ".join(parts))

                # Detail line: partner and structures
                partner = hit.get("partner_seq", "")
                if partner:
                    p_start = hit.get("partner_start", -1)
                    p_end = hit.get("partner_end", -1)
                    pos_str = f"{p_start+1}-{p_end}" if p_start >= 0 else "?"
                    self._log(f"{'':>25}  Partner: {partner} ({pos_str})")

        self._log("")
        self._log(f"Thermometer candidates (moderate+): {thermometers_found}")
        self._log(f"Riboswitch candidates (stably sequestered): {riboswitch_candidates}")
        if fold_errors > 0:
            self._log(f"Fold errors (N/A results): {fold_errors}  — check stderr for details")

        if total_hits > 0:
            self._export_btn.configure(state="normal")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_results(self):
        if not self._all_results:
            messagebox.showinfo("No Results", "Run the analysis first.",
                                parent=self.dialog)
            return

        initial_dir = get_user_data_dir() / "Data" / "Outputs"
        if not initial_dir.exists():
            initial_dir = Path.home() / "Downloads"
        output_file = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Save switch analysis results",
            initialdir=str(initial_dir),
            initialfile="switch_analysis.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            defaultextension=".csv",
        )
        if not output_file:
            return

        # Use cached temps from analysis run (avoids re-reading settings)
        temps = self._cached_temps if self._cached_temps else self._sm.get_temperatures()
        use_pf = self._pf_var.get()

        try:
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # Header
                header = ["Sequence", "Motif_Start", "Motif_End", "Matched_Seq",
                          "Direction", "Trunc_Start", "Trunc_End", "Trunc_Length",
                          "Trunc_Sequence"]
                for t in temps:
                    header.append(f"Paired_Pct_{t}C")
                if use_pf:
                    for t in temps:
                        header.append(f"PF_Access_{t}C")
                for t in temps:
                    header.append(f"MFE_{t}C")
                for t in temps:
                    header.append(f"Motif_Struct_{t}C")
                # Intermediate paired diffs for 3+ temps
                if len(temps) >= 3:
                    for idx in range(len(temps) - 1):
                        header.append(f"Paired_Diff_{temps[idx]}_{temps[idx+1]}C")
                header.extend(["Switch_Score_MFE", "MFE_Delta", "Switch_Class"])
                if use_pf:
                    header.append("Switch_Score_PF")
                header.extend(["Partner_Seq", "Partner_Start", "Partner_End"])
                writer.writerow(header)

                # Data rows — sanitize string values to prevent CSV injection
                for r in self._all_results:
                    name = _sanitize_csv(r.get("name", ""))
                    for hit in r.get("hits", []):
                        row = [
                            name,
                            hit["start"] + 1,  # 1-based for biologists
                            hit["end"],
                            _sanitize_csv(hit.get("matched_seq", "")),
                            hit.get("direction", ""),
                            hit.get("trunc_start", 0) + 1,
                            hit.get("trunc_end", 0),
                            hit.get("trunc_len", 0),
                            _sanitize_csv(hit.get("trunc_seq", "")),
                        ]
                        for t in temps:
                            row.append(hit.get(f"paired_pct_{t}", ""))
                        if use_pf:
                            for t in temps:
                                row.append(hit.get(f"pf_access_{t}", ""))
                        for t in temps:
                            row.append(hit.get(f"mfe_{t}", ""))
                        for t in temps:
                            row.append(_sanitize_csv(hit.get(f"mfe_struct_{t}", "")))
                        if len(temps) >= 3:
                            for idx in range(len(temps) - 1):
                                ta, tb = temps[idx], temps[idx + 1]
                                row.append(hit.get(f"paired_diff_{ta}_{tb}", ""))
                        row.append(hit.get("switch_score_mfe", ""))
                        row.append(hit.get("mfe_delta", ""))
                        row.append(_sanitize_csv(hit.get("switch_class", "")))
                        if use_pf:
                            row.append(hit.get("switch_score_pf", ""))
                        p_start = hit.get("partner_start", -1)
                        p_end = hit.get("partner_end", -1)
                        row.append(_sanitize_csv(hit.get("partner_seq", "")))
                        row.append(p_start + 1 if p_start >= 0 else "")
                        row.append(p_end if p_end >= 0 else "")
                        writer.writerow(row)

            self._log(f"\nExported to {output_file}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save file:\n{e}",
                                 parent=self.dialog)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show(self):
        self.dialog.wait_window()
