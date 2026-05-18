"""
Pseudoknot Finder Dialog — predict RNA pseudoknots using Knotty.

Knotty uses the DP09 energy model to predict secondary structures
including pseudoknots. Results show which sequences contain pseudoknots,
their predicted structures, and minimum free energies.

Reference: Jabbari et al. (2018), Bioinformatics 34(22):3849-3856.
"""

import csv
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from RnaThermofinder.utils.knotty_wrapper import (
    check_knotty_available,
    run_knotty_batch,
    KnottyResult,
)

ACCENT = "#2980b9"
ACCENT_HOVER = "#3498db"
MUTED = "#8b95a5"
SUCCESS = "#27ae60"
ERROR = "#e74c3c"
WARN = "#f39c12"

_CSV_DANGER_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv(value) -> str:
    """Prefix dangerous cell values with a single quote to prevent formula injection."""
    s = str(value) if value is not None else ""
    if s and s[0] in _CSV_DANGER_PREFIXES:
        return "'" + s
    return s


class KnottyDialog:
    """Dialog for running Knotty pseudoknot predictions."""

    def __init__(self, parent, *, sequences=None):
        """
        Args:
            parent: Parent Tk widget.
            sequences: Optional list of dicts with 'name' and 'sequence' keys
                       (pre-loaded from the main app).
        """
        self.parent = parent
        self._sequences = sequences or []
        self._results: list[KnottyResult] = []
        self._running = False
        self._cancel_event = threading.Event()

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Pseudoknot Finder — Knotty")
        self.dialog.geometry("880x750")
        self.dialog.resizable(True, True)
        self.dialog.minsize(700, 550)
        self.dialog.transient(parent)
        self.dialog.after(100, self._try_grab)

        self._create_widgets()

    def _try_grab(self):
        """Safely grab focus — delayed for macOS compatibility."""
        try:
            if self.dialog.winfo_exists():
                self.dialog.grab_set()
        except tk.TclError:
            pass

    def show(self):
        self.dialog.wait_window()

    def _safe_after(self, fn, *args):
        """Schedule fn on the main thread if dialog still exists."""
        try:
            if self.dialog.winfo_exists():
                self.dialog.after(0, fn, *args)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _create_widgets(self):
        self.dialog.grid_columnconfigure(0, weight=1)
        self.dialog.grid_rowconfigure(4, weight=1)  # log area expands

        row = 0

        # ── Status banner ─────────────────────────────────────────────
        available, msg = check_knotty_available()
        status_color = SUCCESS if available else ERROR
        status_text = "Knotty available" if available else "Knotty not found"
        status_frame = ctk.CTkFrame(self.dialog, fg_color=status_color, corner_radius=6, height=32)
        status_frame.grid(row=row, column=0, sticky="ew", padx=12, pady=(12, 4))
        status_frame.grid_propagate(False)
        ctk.CTkLabel(status_frame, text=f"  {status_text}: {msg}",
                     text_color="white", font=ctk.CTkFont(size=11),
                     ).pack(side=tk.LEFT, padx=8, pady=4)
        row += 1

        # ── Input section ─────────────────────────────────────────────
        input_frame = ctk.CTkFrame(self.dialog)
        input_frame.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="Input", font=ctk.CTkFont(size=14, weight="bold"),
                     ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4), columnspan=3)

        # Loaded sequences count
        n_loaded = len(self._sequences)
        loaded_text = f"{n_loaded} sequences loaded from main app" if n_loaded else "No sequences loaded — provide a FASTA file below"
        loaded_color = MUTED if n_loaded else WARN
        ctk.CTkLabel(input_frame, text=loaded_text, text_color=loaded_color,
                     font=ctk.CTkFont(size=11),
                     ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4), columnspan=3)

        # FASTA file override
        ctk.CTkLabel(input_frame, text="FASTA file:", font=ctk.CTkFont(size=12),
                     ).grid(row=2, column=0, sticky="w", padx=12, pady=4)
        self.fasta_var = ctk.StringVar()
        ctk.CTkEntry(input_frame, textvariable=self.fasta_var, width=400,
                     placeholder_text="Path to FASTA file (optional — overrides loaded sequences)"
                     ).grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(input_frame, text="Browse", width=80,
                      command=self._browse_fasta,
                      ).grid(row=2, column=2, padx=(4, 12), pady=4)

        row += 1

        # ── Parameters section ────────────────────────────────────────
        param_frame = ctk.CTkFrame(self.dialog)
        param_frame.grid(row=row, column=0, sticky="ew", padx=12, pady=4)

        ctk.CTkLabel(param_frame, text="Parameters", font=ctk.CTkFont(size=14, weight="bold"),
                     ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4), columnspan=4)

        ctk.CTkLabel(param_frame, text="Timeout (sec):", font=ctk.CTkFont(size=12),
                     ).grid(row=1, column=0, sticky="w", padx=12, pady=4)
        self.timeout_var = ctk.StringVar(value="120")
        ctk.CTkEntry(param_frame, textvariable=self.timeout_var, width=80,
                     ).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(param_frame, text="Max length (nt):", font=ctk.CTkFont(size=12),
                     ).grid(row=1, column=2, sticky="w", padx=(20, 4), pady=4)
        self.maxlen_var = ctk.StringVar(value="500")
        ctk.CTkEntry(param_frame, textvariable=self.maxlen_var, width=80,
                     ).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(param_frame, text="Sequences longer than max length will be skipped (pseudoknot prediction is O(n⁴))",
                     text_color=MUTED, font=ctk.CTkFont(size=10),
                     ).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8), columnspan=4)

        row += 1

        # ── Buttons ──────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        btn_frame.grid(row=row, column=0, sticky="ew", padx=12, pady=4)

        self.run_btn = ctk.CTkButton(
            btn_frame, text="Run Pseudoknot Prediction", width=220, height=38,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run,
        )
        self.run_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel", width=80, height=38,
            fg_color=ERROR, hover_color="#c0392b",
            state="disabled",
            command=self._cancel,
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="Export CSV", width=100, height=38,
            command=self._export_csv,
        ).pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(
            btn_frame, text="How It Works", width=100, height=38,
            fg_color="transparent", border_width=1, border_color=MUTED,
            text_color=MUTED,
            command=self._show_help,
        ).pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(
            btn_frame, text="Close", width=80, height=38,
            fg_color="transparent", border_width=1, border_color=MUTED,
            text_color=MUTED,
            command=self._close,
        ).pack(side=tk.RIGHT)

        row += 1

        # ── Log / results area ────────────────────────────────────────
        self.log_box = ctk.CTkTextbox(self.dialog, font=ctk.CTkFont(family="Courier", size=11),
                                      state="disabled", wrap="none")
        self.log_box.grid(row=row, column=0, sticky="nsew", padx=12, pady=(4, 12))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, text: str):
        """Append text to the log area."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _browse_fasta(self):
        path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Select FASTA file",
            filetypes=[("FASTA files", "*.fasta *.fa *.fna"), ("All files", "*.*")],
        )
        if path:
            self.fasta_var.set(path)

    def _cancel(self):
        """Signal the batch worker to stop after the current sequence."""
        if self._running:
            self._cancel_event.set()
            self._log("Cancelling — will stop after current sequence finishes...")
            self.cancel_btn.configure(state="disabled")

    def _close(self):
        if self._running:
            self._cancel_event.set()
            if not messagebox.askyesno("Analysis Running",
                                       "An analysis is still running. Close anyway?",
                                       parent=self.dialog):
                return
        self.dialog.destroy()

    # ------------------------------------------------------------------
    # Load sequences
    # ------------------------------------------------------------------

    def _load_sequences(self) -> list[tuple[str, str]]:
        """Get sequences from FASTA file or loaded sequences.

        Returns list of (name, sequence) tuples.
        """
        fasta_path = self.fasta_var.get().strip()
        if fasta_path:
            return self._parse_fasta(fasta_path)

        if self._sequences:
            return [(s["name"], s["sequence"]) for s in self._sequences]

        return []

    _MAX_FASTA_MB = 100  # warn if FASTA file exceeds this size

    def _parse_fasta(self, path: str) -> list[tuple[str, str]]:
        """Simple FASTA parser."""
        import os as _os
        file_mb = _os.path.getsize(path) / (1024 * 1024)
        if file_mb > self._MAX_FASTA_MB:
            self._log(f"Warning: FASTA file is {file_mb:.0f} MB — this may be slow")

        sequences = []
        name = ""
        seq_lines: list[str] = []

        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(";"):
                        continue
                    if line.startswith(">"):
                        if name and seq_lines:
                            sequences.append((name, "".join(seq_lines)))
                        name = line[1:].strip().split()[0] if line[1:].strip() else f"seq_{len(sequences) + 1}"
                        seq_lines = []
                    else:
                        seq_lines.append(line.upper())
            if name and seq_lines:
                sequences.append((name, "".join(seq_lines)))
        except Exception as e:
            self._log(f"Error reading FASTA: {e}")

        return sequences

    # ------------------------------------------------------------------
    # Run prediction
    # ------------------------------------------------------------------

    def _run(self):
        if self._running:
            self._log("Already running — please wait.")
            return

        available, msg = check_knotty_available()
        if not available:
            messagebox.showerror("Knotty Not Found", msg, parent=self.dialog)
            return

        sequences = self._load_sequences()
        if not sequences:
            messagebox.showwarning("No Sequences",
                                   "Load sequences in the main app or provide a FASTA file.",
                                   parent=self.dialog)
            return

        try:
            timeout = int(self.timeout_var.get())
        except ValueError:
            timeout = 120

        try:
            max_len = int(self.maxlen_var.get())
        except ValueError:
            max_len = 500

        # Filter by length
        filtered = [(n, s) for n, s in sequences if len(s) <= max_len]
        skipped = len(sequences) - len(filtered)

        if not filtered:
            messagebox.showwarning("All Skipped",
                                   f"All {len(sequences)} sequences exceed the max length ({max_len} nt).",
                                   parent=self.dialog)
            return

        # Clear log
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        self._log(f"Starting pseudoknot prediction on {len(filtered)} sequences...")
        if skipped:
            self._log(f"  Skipped {skipped} sequences exceeding {max_len} nt")

        self._running = True
        self._cancel_event.clear()
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")

        def worker():
            total = len(filtered)

            def progress(current, t):
                step = max(1, t // 10)
                if current % step == 0 or current == t:
                    self._safe_after(self._log, f"  [{current}/{t}] sequences processed")

            def log_cb(msg):
                self._safe_after(self._log, f"  {msg}")

            results = run_knotty_batch(
                filtered,
                timeout=timeout,
                progress_callback=progress,
                log_callback=log_cb,
                cancel_event=self._cancel_event,
            )
            self._safe_after(self._on_results, results)

        threading.Thread(target=worker, daemon=True).start()

    def _on_results(self, results: list[KnottyResult]):
        self._results = results
        self._running = False
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

        # Count stats
        successful = [r for r in results if not r.error]
        errors = [r for r in results if r.error]
        pk_count = sum(1 for r in successful if r.has_pseudoknot)
        no_pk_count = len(successful) - pk_count

        self._log(f"\n{'=' * 70}")
        self._log(f"RESULTS: {len(successful)} predicted, {pk_count} pseudoknots found, "
                  f"{no_pk_count} without pseudoknots")
        if errors:
            self._log(f"  {len(errors)} errors (timeout or failure)")
        self._log(f"{'=' * 70}\n")

        # Header
        self._log(f"{'Name':<20} {'Len':>5} {'Energy':>8} {'PK?':>4}  Structure")
        self._log(f"{'-' * 20} {'-' * 5} {'-' * 8} {'-' * 4}  {'-' * 30}")

        # Sort: pseudoknots first, then by energy
        sorted_results = sorted(successful,
                                key=lambda r: (not r.has_pseudoknot, r.energy))

        for r in sorted_results:
            name = r.seq_name[:20] if r.seq_name else "unnamed"
            pk_flag = "YES" if r.has_pseudoknot else "no"
            struct_display = r.structure[:50] + "..." if len(r.structure) > 50 else r.structure
            self._log(f"{name:<20} {len(r.sequence):>5} {r.energy:>8.2f} {pk_flag:>4}  {struct_display}")

        if errors:
            self._log(f"\n--- Errors ---")
            for r in errors:
                name = r.seq_name[:20] if r.seq_name else "unnamed"
                self._log(f"{name:<20}  {r.error}")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_csv(self):
        if not self._results:
            messagebox.showinfo("No Results", "Run the prediction first.", parent=self.dialog)
            return

        path = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Results",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Length", "Sequence", "Structure",
                                 "Energy_kcal", "Has_Pseudoknot", "Error"])
                for r in self._results:
                    writer.writerow([
                        _sanitize_csv(r.seq_name),
                        len(r.sequence),
                        _sanitize_csv(r.sequence),
                        _sanitize_csv(r.structure),
                        f"{r.energy:.2f}" if not r.error else "",
                        "Yes" if r.has_pseudoknot else "No",
                        _sanitize_csv(r.error),
                    ])
            self._log(f"\nExported to {path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self.dialog)

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def _show_help(self):
        help_text = (
            "PSEUDOKNOT FINDER — How It Works\n"
            "━" * 40 + "\n\n"
            "Standard RNA folding (ViennaRNA) assumes nested base pairs only.\n"
            "Pseudoknots are crossing pairs that break this assumption:\n\n"
            "  Nested:      (((...)))          — pairs do NOT cross\n"
            "  Pseudoknot:  (((...[[...)))...]]  — () and [] CROSS\n\n"
            "In the pseudoknot above, the [ opens inside the () stem but\n"
            "the ] closes outside it. This is an H-type pseudoknot.\n\n"
            "Knotty uses the DP09 energy model to predict structures that\n"
            "include pseudoknots. It outputs extended dot-bracket notation:\n"
            "  ( ) — standard nested base pairs\n"
            "  [ ] — pairs that cross with ( ) pairs\n"
            "  { } — pairs that cross with ( ) or [ ] pairs\n\n"
            "IMPORTANT NOTES:\n"
            "- Energies reflect RNA-only folding. Ligand-RNA interactions\n"
            "  (relevant to riboswitches) are NOT modeled.\n"
            "- Prediction accuracy for pseudoknotted pairs is lower than\n"
            "  for nested pairs (~50-60% vs ~70-80% sensitivity).\n"
            "- Input sequences with T (thymine) are auto-converted to U.\n\n"
            "PERFORMANCE:\n"
            "Pseudoknot prediction is computationally expensive\n"
            "(O(n⁴) to O(n⁶) depending on pseudoknot complexity).\n"
            "Sequences >500 nt may take minutes. Use the max length\n"
            "filter to skip very long sequences.\n\n"
            "REFERENCE:\n"
            "Jabbari et al. (2018), Bioinformatics 34(22):3849-3856\n"
            "\"Knotty: efficient and accurate prediction of complex RNA\n"
            " pseudoknotted secondary structures\""
        )

        help_win = ctk.CTkToplevel(self.dialog)
        help_win.title("Pseudoknot Finder — Help")
        help_win.geometry("520x440")
        help_win.transient(self.dialog)

        tb = ctk.CTkTextbox(help_win, font=ctk.CTkFont(family="Courier", size=11),
                            wrap="word")
        tb.pack(fill="both", expand=True, padx=10, pady=10)
        tb.insert("1.0", help_text)
        tb.configure(state="disabled")
