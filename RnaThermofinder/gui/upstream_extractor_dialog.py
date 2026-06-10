"""
Sequence Extractor Dialog — CustomTkinter edition.
Supports upstream, downstream, and bidirectional (both) extraction
from CDS features in a GenBank-annotated genome.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import threading
import customtkinter as ctk

try:
    from settings_manager import default_output_dir
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from settings_manager import default_output_dir


class SequenceExtractorDialog:
    """Dialog for sequence extraction (upstream / downstream / both) with NCBI fetch (CTk)."""

    ACCENT = "#2980b9"

    def __init__(self, parent):
        self.parent = parent
        self.genbank_file = None
        self.fasta_file = None
        self.output_file = None

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Sequence Extractor")
        self.dialog.geometry("880x820")
        self.dialog.resizable(True, True)
        self.dialog.minsize(780, 720)
        self.dialog.transient(parent)
        self.dialog.after(100, self._try_grab)

        self._create_widgets()

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _try_grab(self):
        """Safely grab focus — delayed for macOS compatibility."""
        try:
            if self.dialog.winfo_exists():
                self.dialog.grab_set()
        except tk.TclError:
            pass

    def _create_widgets(self):
        main = ctk.CTkFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(main, text="Sequence Extractor",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 2))
        ctk.CTkLabel(main,
                     text="Extract upstream, downstream, or flanking sequences from genes using local files or fetch from NCBI",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(0, 12))

        # Tabs: Local / NCBI
        self.tabview = ctk.CTkTabview(main, corner_radius=10)
        self.tabview.pack(fill=tk.X, pady=(0, 10))

        self._create_local_tab(self.tabview.add("Local Files"))
        self._create_ncbi_tab(self.tabview.add("Fetch from NCBI"))

        # Direction + Parameters card
        params_card = ctk.CTkFrame(main, corner_radius=10)
        params_card.pack(fill=tk.X, pady=(0, 10))
        ctk.CTkLabel(params_card, text="Extraction Parameters",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 6))
        self._create_direction_selector(params_card)
        self._create_params(params_card)

        # Output
        out_card = ctk.CTkFrame(main, corner_radius=10)
        out_card.pack(fill=tk.X, pady=(0, 10))
        ctk.CTkLabel(out_card, text="Output",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 6))
        self._create_file_row(out_card, "Output File (.fasta):", "output",
                              [("FASTA files", "*.fasta *.fa"), ("All files", "*.*")],
                              is_save=True)
        ctk.CTkFrame(out_card, height=8, fg_color="transparent").pack()

        # Progress
        prog_card = ctk.CTkFrame(main, corner_radius=10)
        prog_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        ctk.CTkLabel(prog_card, text="Progress",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        self.progress_text = ctk.CTkTextbox(prog_card, height=100,
                                            font=ctk.CTkFont(family="Consolas", size=11),
                                            state="disabled", corner_radius=6)
        self.progress_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        # Buttons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill=tk.X)

        self.run_btn = ctk.CTkButton(btn_frame, text="Run Extraction", width=160,
                                     fg_color=self.ACCENT,
                                     command=self._run_extraction)
        self.run_btn.pack(side=tk.LEFT)
        ctk.CTkButton(btn_frame, text="Close", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Source file tabs
    # ------------------------------------------------------------------
    def _create_local_tab(self, tab):
        ctk.CTkLabel(tab, text="Select GenBank and FASTA files from your computer:",
                     font=ctk.CTkFont(size=11), text_color="gray"
                     ).pack(anchor="w", pady=(4, 8))

        self._create_file_row(tab, "GenBank File:", "genbank",
                              [("GenBank files", "*.flat *.gb *.gbk"), ("All files", "*.*")])
        self._create_file_row(tab, "FASTA File:", "fasta",
                              [("FASTA files", "*.fasta *.fa *.fna"), ("All files", "*.*")])

    def _create_ncbi_tab(self, tab):
        ctk.CTkLabel(tab,
                     text="Fetch GenBank and FASTA files automatically from NCBI:",
                     font=ctk.CTkFont(size=11), text_color="gray"
                     ).pack(anchor="w", pady=(4, 8))

        # Accession
        row1 = ctk.CTkFrame(tab, fg_color="transparent")
        row1.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row1, text="Accession Number:", width=170).pack(side=tk.LEFT)
        self.accession_var = tk.StringVar()
        ctk.CTkEntry(row1, textvariable=self.accession_var, width=250).pack(side=tk.LEFT, padx=4)
        ctk.CTkLabel(row1, text="e.g. NZ_CP097882.1", text_color="gray",
                     font=ctk.CTkFont(size=10)).pack(side=tk.LEFT, padx=4)

        # Email
        row2 = ctk.CTkFrame(tab, fg_color="transparent")
        row2.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row2, text="Email (NCBI requires):", width=170).pack(side=tk.LEFT)
        self.email_var = tk.StringVar()
        ctk.CTkEntry(row2, textvariable=self.email_var, width=250).pack(side=tk.LEFT, padx=4)

        # Download dir
        row3 = ctk.CTkFrame(tab, fg_color="transparent")
        row3.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row3, text="Save Downloads To:", width=170).pack(side=tk.LEFT)
        self.download_dir_var = tk.StringVar(value=str(default_output_dir()))
        ctk.CTkEntry(row3, textvariable=self.download_dir_var, width=280).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(row3, text="Browse", width=80,
                      command=self._browse_download_dir).pack(side=tk.LEFT, padx=4)

        # Fetch button
        row4 = ctk.CTkFrame(tab, fg_color="transparent")
        row4.pack(fill=tk.X, pady=(8, 0))
        self.fetch_btn = ctk.CTkButton(row4, text="Fetch from NCBI", width=160,
                                       fg_color=self.ACCENT,
                                       command=self._fetch_from_ncbi)
        self.fetch_btn.pack(side=tk.LEFT)
        self.fetch_status_var = tk.StringVar()
        ctk.CTkLabel(row4, textvariable=self.fetch_status_var,
                     text_color="gray", font=ctk.CTkFont(size=10)
                     ).pack(side=tk.LEFT, padx=10)

    # ------------------------------------------------------------------
    # Direction selector
    # ------------------------------------------------------------------
    def _create_direction_selector(self, parent):
        """Segmented button for choosing extraction direction."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, padx=16, pady=(0, 6))

        ctk.CTkLabel(row, text="Direction:", width=120).pack(side=tk.LEFT)

        self.direction_var = tk.StringVar(value="Upstream")
        self.direction_seg = ctk.CTkSegmentedButton(
            row, values=["Upstream", "Downstream", "Both"],
            variable=self.direction_var,
            command=self._on_direction_changed,
            font=ctk.CTkFont(size=12),
        )
        self.direction_seg.set("Upstream")
        self.direction_seg.pack(side=tk.LEFT, padx=4)

        # Info label
        self.direction_info_var = tk.StringVar(
            value="Extract N bases before the CDS start (promoter / 5' UTR region)")
        ctk.CTkLabel(row, textvariable=self.direction_info_var,
                     text_color="gray", font=ctk.CTkFont(size=10),
                     wraplength=350).pack(side=tk.LEFT, padx=(12, 0))

    def _on_direction_changed(self, value):
        """Show/hide parameter fields based on direction.
        NOTE: CTkSegmentedButton already updates direction_var via its variable= binding.
        We must NOT override it with a lowercase value or the button loses its selection.
        """
        direction = value.lower()  # local only — used for logic below

        descs = {
            "upstream": "Extract N bases before the CDS start (promoter / 5' UTR region)",
            "downstream": "Extract N bases after the CDS end (terminator / 3' UTR region)",
            "both": "Extract upstream AND downstream as separate entries per gene",
        }
        self.direction_info_var.set(descs.get(direction, ""))

        # Show/hide parameter rows
        show_up = direction in ("upstream", "both")
        show_dn = direction in ("downstream", "both")

        if show_up:
            self._upstream_row.pack(fill=tk.X, padx=16, pady=3, before=self._window2_frame)
        else:
            self._upstream_row.pack_forget()

        if show_dn:
            self._downstream_row.pack(fill=tk.X, padx=16, pady=3, before=self._window2_frame)
        else:
            self._downstream_row.pack_forget()

        # Update Window 2 labels and visibility
        self._update_window2_visibility()

    # ------------------------------------------------------------------
    # Extraction parameters
    # ------------------------------------------------------------------
    def _create_params(self, parent):
        # ── Upstream length row ───────────────────────────────────────
        self._upstream_row = ctk.CTkFrame(parent, fg_color="transparent")
        self._upstream_row.pack(fill=tk.X, padx=16, pady=3)

        ctk.CTkLabel(self._upstream_row, text="Upstream Length (bp):", width=200).pack(side=tk.LEFT)
        self.upstream_var = tk.StringVar(value="300")
        ctk.CTkEntry(self._upstream_row, textvariable=self.upstream_var, width=80).pack(side=tk.LEFT, padx=4)
        ctk.CTkLabel(self._upstream_row, text="(required)", text_color="gray",
                     font=ctk.CTkFont(size=10)).pack(side=tk.LEFT, padx=4)

        # ── Downstream length row ─────────────────────────────────────
        self._downstream_row = ctk.CTkFrame(parent, fg_color="transparent")
        # Starts hidden (upstream is the default direction)

        ctk.CTkLabel(self._downstream_row, text="Downstream Length (bp):", width=200).pack(side=tk.LEFT)
        self.downstream_var = tk.StringVar(value="200")
        ctk.CTkEntry(self._downstream_row, textvariable=self.downstream_var, width=80).pack(side=tk.LEFT, padx=4)
        ctk.CTkLabel(self._downstream_row, text="(required)", text_color="gray",
                     font=ctk.CTkFont(size=10)).pack(side=tk.LEFT, padx=4)

        # ── Window 2 (optional second extraction) ─────────────────────
        self._window2_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._window2_frame.pack(fill=tk.X, padx=16, pady=(3, 12))

        self.use_window2_var = tk.BooleanVar(value=False)
        self._window2_cb = ctk.CTkCheckBox(
            self._window2_frame, text="Window 2 (optional):",
            variable=self.use_window2_var,
            command=self._toggle_window2)
        self._window2_cb.pack(side=tk.LEFT)

        # Upstream Window 2
        self._up2_label = ctk.CTkLabel(self._window2_frame, text="Up:", width=30)
        self.upstream2_var = tk.StringVar(value="150")
        self._up2_entry = ctk.CTkEntry(self._window2_frame, textvariable=self.upstream2_var,
                                       width=70, state="disabled")

        # Downstream Window 2
        self._dn2_label = ctk.CTkLabel(self._window2_frame, text="Down:", width=40)
        self.downstream2_var = tk.StringVar(value="100")
        self._dn2_entry = ctk.CTkEntry(self._window2_frame, textvariable=self.downstream2_var,
                                       width=70, state="disabled")

        self._dn2_hint = ctk.CTkLabel(self._window2_frame, text="(bp)", text_color="gray",
                                      font=ctk.CTkFont(size=10))

        # Initial layout for Window 2 sub-widgets
        self._update_window2_visibility()

    def _toggle_window2(self):
        """Enable/disable Window 2 entry fields."""
        enabled = self.use_window2_var.get()
        state = "normal" if enabled else "disabled"
        self._up2_entry.configure(state=state)
        self._dn2_entry.configure(state=state)

    def _update_window2_visibility(self):
        """Show the right Window 2 fields for the current direction."""
        direction = self.direction_var.get().lower()
        show_up = direction in ("upstream", "both")
        show_dn = direction in ("downstream", "both")

        # Forget all Window 2 sub-widgets first
        for w in (self._up2_label, self._up2_entry, self._dn2_label, self._dn2_entry, self._dn2_hint):
            w.pack_forget()

        # Re-pack the relevant ones
        if show_up:
            self._up2_label.pack(side=tk.LEFT, padx=(8, 2))
            self._up2_entry.pack(side=tk.LEFT, padx=(0, 4))
        if show_dn:
            self._dn2_label.pack(side=tk.LEFT, padx=(8, 2))
            self._dn2_entry.pack(side=tk.LEFT, padx=(0, 4))
        if show_up or show_dn:
            self._dn2_hint.pack(side=tk.LEFT, padx=2)

    # ------------------------------------------------------------------
    # File browser helpers
    # ------------------------------------------------------------------
    def _create_file_row(self, parent, label, file_type, filetypes, is_save=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, padx=16, pady=4)

        ctk.CTkLabel(row, text=label, width=180).pack(side=tk.LEFT)
        var = tk.StringVar()
        setattr(self, f"{file_type}_var", var)
        ctk.CTkEntry(row, textvariable=var, width=400).pack(side=tk.LEFT, padx=4)

        if is_save:
            cmd = lambda: self._browse_save_file(file_type, filetypes)
            text = "Save As"
        else:
            cmd = lambda: self._browse_file(file_type, filetypes)
            text = "Browse"
        ctk.CTkButton(row, text=text, width=80, command=cmd).pack(side=tk.LEFT, padx=4)

    def _browse_file(self, file_type, filetypes):
        fn = filedialog.askopenfilename(title=f"Select {file_type.upper()} file",
                                        filetypes=filetypes)
        if fn:
            getattr(self, f"{file_type}_var").set(fn)
            setattr(self, f"{file_type}_file", fn)

    def _browse_save_file(self, file_type, filetypes):
        fn = filedialog.asksaveasfilename(
            title="Save extracted sequences as...",
            initialdir=str(default_output_dir()),
            initialfile="extracted_sequences.fasta",
            filetypes=filetypes, defaultextension=".fasta")
        if fn:
            getattr(self, f"{file_type}_var").set(fn)
            setattr(self, f"{file_type}_file", fn)

    def _browse_download_dir(self):
        d = filedialog.askdirectory(title="Select download directory")
        if d:
            self.download_dir_var.set(d)

    # ------------------------------------------------------------------
    # Thread-safe helpers
    # ------------------------------------------------------------------
    def _safe_after(self, func):
        try:
            if self.dialog.winfo_exists():
                self.dialog.after(0, func)
        except Exception:
            pass

    def _log(self, message):
        def _append():
            self.progress_text.configure(state="normal")
            self.progress_text.insert(tk.END, message + "\n")
            self.progress_text.see(tk.END)
            self.progress_text.configure(state="disabled")
        self._safe_after(_append)

    # ------------------------------------------------------------------
    # NCBI fetch
    # ------------------------------------------------------------------
    def _fetch_from_ncbi(self):
        accession = self.accession_var.get().strip()
        email = self.email_var.get().strip()
        download_dir = self.download_dir_var.get().strip()

        if not accession:
            messagebox.showerror("Error", "Enter an accession number.", parent=self.dialog)
            return
        if not email:
            messagebox.showerror("Error", "Enter your email (NCBI requirement).", parent=self.dialog)
            return
        if not download_dir:
            messagebox.showerror("Error", "Select a download directory.", parent=self.dialog)
            return

        self.fetch_btn.configure(state="disabled")
        self.fetch_status_var.set("Fetching...")
        self.progress_text.configure(state="normal")
        self.progress_text.delete("1.0", tk.END)
        self.progress_text.configure(state="disabled")

        def fetch():
            try:
                from RnaThermofinder.utils.upstream_extractor import fetch_from_ncbi
                gb_path, fasta_path = fetch_from_ncbi(
                    accession, email, download_dir, progress_callback=self._log)
                self._safe_after(lambda: self._set_fetched(gb_path, fasta_path))
                self._safe_after(lambda: self.fetch_status_var.set("Fetch complete"))
                self._safe_after(lambda: messagebox.showinfo(
                    "Fetch Complete",
                    f"Downloaded:\n\nGenBank: {gb_path}\nFASTA: {fasta_path}",
                    parent=self.dialog))
            except Exception as e:
                self._log(f"Error: {e}")
                self._safe_after(lambda: self.fetch_status_var.set("Fetch failed"))
                self._safe_after(lambda: messagebox.showerror("Error", str(e), parent=self.dialog))
            finally:
                self._safe_after(lambda: self.fetch_btn.configure(state="normal"))

        threading.Thread(target=fetch, daemon=True).start()

    def _set_fetched(self, gb_path, fasta_path):
        self.genbank_var.set(gb_path)
        self.genbank_file = gb_path
        self.fasta_var.set(fasta_path)
        self.fasta_file = fasta_path
        self.tabview.set("Local Files")

    # ------------------------------------------------------------------
    # Run extraction
    # ------------------------------------------------------------------
    def _run_extraction(self):
        gb = self.genbank_var.get().strip()
        fa = self.fasta_var.get().strip()
        out = self.output_var.get().strip()

        if not gb:
            messagebox.showerror("Error", "Select a GenBank file (or fetch from NCBI).", parent=self.dialog)
            return
        if not fa:
            messagebox.showerror("Error", "Select a FASTA file (or fetch from NCBI).", parent=self.dialog)
            return
        if not out:
            messagebox.showerror("Error", "Specify an output file location.", parent=self.dialog)
            return

        # Verify files actually exist on disk before running
        if not Path(gb).exists():
            messagebox.showerror("Error", f"GenBank file not found:\n{gb}", parent=self.dialog)
            return
        if not Path(fa).exists():
            messagebox.showerror("Error", f"FASTA file not found:\n{fa}", parent=self.dialog)
            return

        self.genbank_file = gb
        self.fasta_file = fa
        self.output_file = out

        direction = self.direction_var.get().lower()

        # ── Validate lengths ──────────────────────────────────────────
        upstream_length = 0
        downstream_length = 0

        if direction in ("upstream", "both"):
            try:
                upstream_length = int(self.upstream_var.get())
                if upstream_length <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Error", "Upstream length must be a positive integer.", parent=self.dialog)
                return

        if direction in ("downstream", "both"):
            try:
                downstream_length = int(self.downstream_var.get())
                if downstream_length <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Error", "Downstream length must be a positive integer.", parent=self.dialog)
                return

        # ── Optional Window 2 ─────────────────────────────────────────
        upstream_length_2 = None
        downstream_length_2 = None

        if self.use_window2_var.get():
            if direction in ("upstream", "both"):
                try:
                    upstream_length_2 = int(self.upstream2_var.get())
                    if upstream_length_2 <= 0:
                        raise ValueError()
                except ValueError:
                    messagebox.showerror("Error", "Window 2 upstream length must be a positive integer.", parent=self.dialog)
                    return

            if direction in ("downstream", "both"):
                try:
                    downstream_length_2 = int(self.downstream2_var.get())
                    if downstream_length_2 <= 0:
                        raise ValueError()
                except ValueError:
                    messagebox.showerror("Error", "Window 2 downstream length must be a positive integer.", parent=self.dialog)
                    return

        # ── Launch extraction ─────────────────────────────────────────
        self.run_btn.configure(state="disabled")
        self.progress_text.configure(state="normal")
        self.progress_text.delete("1.0", tk.END)
        self.progress_text.configure(state="disabled")

        def run():
            try:
                from RnaThermofinder.utils.upstream_extractor import extract_sequences
                total, successful = extract_sequences(
                    genbank_file=self.genbank_file,
                    fasta_file=self.fasta_file,
                    output_file=self.output_file,
                    upstream_length=upstream_length,
                    downstream_length=downstream_length,
                    direction=direction,
                    upstream_length_2=upstream_length_2,
                    downstream_length_2=downstream_length_2,
                    progress_callback=self._log,
                )
                dir_label = {"upstream": "upstream", "downstream": "downstream",
                             "both": "upstream + downstream"}[direction]
                self._safe_after(lambda: messagebox.showinfo(
                    "Success",
                    f"Extracted {dir_label} sequences: {successful}/{total} genes\n"
                    f"Output: {self.output_file}",
                    parent=self.dialog))
            except Exception as e:
                self._log(f"Error: {e}")
                self._safe_after(lambda: messagebox.showerror("Error", str(e), parent=self.dialog))
            finally:
                self._safe_after(lambda: self.run_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def show(self):
        self.dialog.wait_window()


# ─────────────────────────────────────────────────────────────────────
# Backward-compatible alias for old import paths
# ─────────────────────────────────────────────────────────────────────
UpstreamExtractorDialogModern = SequenceExtractorDialog
