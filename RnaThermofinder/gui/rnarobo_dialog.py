"""
RNArobo Structural Motif Search dialog.

Descriptor format per the RNArobo 2.1.0 guide:
  h = helix (paired stem, default allows G-U wobble via TGYR transform)
  s = single-stranded
  r = relational (like helix but with custom pairing transform string)

Each element supports mismatches, mispairs (helix/relational), and
optional insertions with nucleotide constraints.
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

from RnaThermofinder.utils.rnarobo_wrapper import (
    RNAROBO_PRESETS,
    DescriptorSpec,
    HelixElement,
    SingleStrandedElement,
    RelationalElement,
    check_rnarobo_available,
    run_rnarobo,
    validate_descriptor,
)

ACCENT = "#2980b9"
ACCENT_HOVER = "#3498db"
MUTED = "#8b95a5"
SUCCESS = "#27ae60"

MAX_ELEMENTS = 50  # generous UI sanity cap; descriptor assembly is fully dynamic

# Element type labels shown in the dropdown
TYPE_HELIX = "Helix (h)"
TYPE_SINGLE = "Single-stranded (s)"
TYPE_RELATIONAL = "Relational (r)"


class RNAroboDialog:
    """Dialog for running RNArobo structural motif searches."""

    def __init__(self, parent):
        self.parent = parent
        self._results = None

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("RNArobo — Structural Motif Search")
        self.dialog.geometry("820x900")
        self.dialog.resizable(True, True)
        self.dialog.minsize(750, 650)
        self.dialog.transient(parent)
        self.dialog.after(100, self._try_grab)

        self._element_rows: list = []

        self._create_widgets()
        self._check_binary()

        # Centre on parent
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

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------

    def _create_widgets(self):
        main = ctk.CTkScrollableFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        ctk.CTkLabel(main, text="RNArobo Structural Motif Search",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 2))
        ctk.CTkLabel(main,
                     text="Search for structural RNA motifs (helices, loops, junctions, pseudoknots) in FASTA sequences",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(0, 2))
        ctk.CTkLabel(main,
                     text="Rampasek et al. (2016) RNA motif search with data-driven element ordering. BMC Bioinformatics 17:216. doi:10.1186/s12859-016-1074-x",
                     font=ctk.CTkFont(size=9), text_color=MUTED,
                     wraplength=720, justify="center").pack(pady=(0, 8))

        # Binary status
        self.status_label = ctk.CTkLabel(
            main, text="Checking rnarobo binary...",
            font=ctk.CTkFont(size=11), text_color=MUTED)
        self.status_label.pack(anchor="w", pady=(0, 10))

        # Preset row
        preset_row = ctk.CTkFrame(main, fg_color="transparent")
        preset_row.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(preset_row, text="Preset:", width=60).pack(side=tk.LEFT)
        preset_names = ["Custom"] + list(RNAROBO_PRESETS.keys())
        self.preset_var = tk.StringVar(value="Custom")
        self.preset_menu = ctk.CTkOptionMenu(
            preset_row, variable=self.preset_var,
            values=preset_names, width=240)
        self.preset_menu.pack(side=tk.LEFT, padx=(4, 8))
        ctk.CTkButton(preset_row, text="Load Preset", width=100,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._load_preset).pack(side=tk.LEFT)

        # Motif Map card
        map_card = ctk.CTkFrame(main, corner_radius=10)
        map_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(map_card, text="Motif Map",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(map_card,
                     text="Space-separated element names. Primed names (h1') mark complementary helix/relational strand.",
                     font=ctk.CTkFont(size=10), text_color=MUTED
                     ).pack(anchor="w", padx=16, pady=(0, 4))

        map_row = ctk.CTkFrame(map_card, fg_color="transparent")
        map_row.pack(fill=tk.X, padx=16, pady=(0, 4))

        self.motif_map_var = tk.StringVar(value="")
        ctk.CTkEntry(map_row, textvariable=self.motif_map_var, width=420,
                     font=ctk.CTkFont(family="Consolas", size=12),
                     placeholder_text="e.g. h1 s1 h2 s2 h2' h1'"
                     ).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(map_row, text="Auto-fill Elements", width=140,
                      fg_color="gray40", hover_color="gray50",
                      command=self._auto_fill_from_map).pack(side=tk.LEFT)

        ctk.CTkFrame(map_card, height=8, fg_color="transparent").pack()

        # Element Specifications card
        elem_card = ctk.CTkFrame(main, corner_radius=10)
        elem_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(elem_card, text="Element Specifications",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(elem_card,
                     text="h/r: mismatches:mispairs, pos_strand:neg_strand.  s: mismatches, sequence.  * = wildcard.  [10] = 10 wildcards.",
                     font=ctk.CTkFont(size=10), text_color=MUTED
                     ).pack(anchor="w", padx=16, pady=(0, 2))
        ctk.CTkLabel(elem_card,
                     text="r (relational): like h but with custom pairing transform (e.g. TGCA=canonical, TGYR=wobble).  Insertions are optional.",
                     font=ctk.CTkFont(size=10), text_color=MUTED
                     ).pack(anchor="w", padx=16, pady=(0, 6))

        self._elements_frame = ctk.CTkFrame(elem_card, fg_color="transparent")
        self._elements_frame.pack(fill=tk.X, padx=16, pady=(0, 4))

        btn_row = ctk.CTkFrame(elem_card, fg_color="transparent")
        btn_row.pack(fill=tk.X, padx=16, pady=(0, 10))
        ctk.CTkButton(btn_row, text="+ Add Element", width=120,
                      fg_color="gray40", hover_color="gray50",
                      command=lambda: self._add_element(TYPE_HELIX, "")
                      ).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(btn_row, text="Remove Last", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self._remove_element).pack(side=tk.LEFT)

        # Descriptor Preview
        prev_card = ctk.CTkFrame(main, corner_radius=10)
        prev_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(prev_card, text="Descriptor Preview",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        self.preview_text = ctk.CTkTextbox(
            prev_card, height=80,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled", corner_radius=6)
        self.preview_text.pack(fill=tk.X, padx=12, pady=(0, 12))

        # Input / Options
        io_card = ctk.CTkFrame(main, corner_radius=10)
        io_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(io_card, text="Input & Options",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 6))

        # Sequence file
        file_row = ctk.CTkFrame(io_card, fg_color="transparent")
        file_row.pack(fill=tk.X, padx=16, pady=3)
        ctk.CTkLabel(file_row, text="Sequence File:", width=110).pack(side=tk.LEFT)
        self.input_var = tk.StringVar()
        ctk.CTkEntry(file_row, textvariable=self.input_var, width=380
                     ).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(file_row, text="Browse", width=80,
                      command=self._browse_input).pack(side=tk.LEFT, padx=4)

        # Options row
        opt_row = ctk.CTkFrame(io_card, fg_color="transparent")
        opt_row.pack(fill=tk.X, padx=16, pady=(6, 4))

        self.both_strands_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_row, text="Both strands (-c)",
                        variable=self.both_strands_var, width=160
                        ).pack(side=tk.LEFT)

        self.non_overlap_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt_row, text="Non-overlapping (-u)",
                        variable=self.non_overlap_var, width=170
                        ).pack(side=tk.LEFT)

        # Note: FASTA output (-f) is intentionally not exposed because
        # the output parser only handles rnarobo's default tabular format.
        self.fasta_out_var = tk.BooleanVar(value=False)

        # N-ratio row
        nratio_row = ctk.CTkFrame(io_card, fg_color="transparent")
        nratio_row.pack(fill=tk.X, padx=16, pady=(2, 12))
        ctk.CTkLabel(nratio_row, text="N-ratio threshold:", width=130).pack(side=tk.LEFT)
        self.nratio_var = tk.StringVar(value="")
        ctk.CTkEntry(nratio_row, textvariable=self.nratio_var, width=80,
                     placeholder_text="0.0-1.0").pack(side=tk.LEFT, padx=4)
        ctk.CTkLabel(nratio_row, text="(max allowed N content, leave blank to skip)",
                     font=ctk.CTkFont(size=10), text_color=MUTED).pack(side=tk.LEFT, padx=4)

        # Progress / Results
        prog_card = ctk.CTkFrame(main, corner_radius=10)
        prog_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(prog_card, text="Results",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        self.progress_text = ctk.CTkTextbox(
            prog_card, height=160,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled", corner_radius=6)
        self.progress_text.pack(fill=tk.X, padx=12, pady=(0, 12))

        # Buttons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=(4, 0))

        self.run_btn = ctk.CTkButton(
            btn_frame, text="Run Search", width=140,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run_search)
        self.run_btn.pack(side=tk.LEFT)

        self.export_btn = ctk.CTkButton(
            btn_frame, text="Export Results", width=130,
            fg_color=SUCCESS, hover_color="#2ecc71",
            state="disabled", command=self._export_results)
        self.export_btn.pack(side=tk.LEFT, padx=(10, 0))

        ctk.CTkButton(btn_frame, text="Close", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Binary check
    # ------------------------------------------------------------------

    def _check_binary(self):
        available, message = check_rnarobo_available()
        if available:
            self.status_label.configure(
                text=f"\u2713 RNArobo binary found: {message}", text_color=SUCCESS)
            self.run_btn.configure(state="normal")
        else:
            self.status_label.configure(
                text=f"\u2717 RNArobo not found — place binary in bin/<platform>/",
                text_color="#e74c3c")
            self.run_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    def _load_preset(self):
        name = self.preset_var.get()
        if name == "Custom":
            self._clear_elements()
            self.motif_map_var.set("")
            self._update_preview()
            return
        preset = RNAROBO_PRESETS.get(name)
        if not preset:
            return
        self._clear_elements()
        self.motif_map_var.set(preset.motif_map)
        for elem in preset.elements:
            self._add_element_from_dataclass(elem)
        self._update_preview()

    def _add_element_from_dataclass(self, elem):
        """Add a UI row pre-filled from a dataclass element."""
        if isinstance(elem, HelixElement):
            self._add_element(TYPE_HELIX, elem.name,
                              mm=str(elem.mismatches), mispairs=str(elem.mispairs),
                              pos_strand=elem.pos_strand, neg_strand=elem.neg_strand,
                              insertions=str(elem.insertions) if elem.insertions else "",
                              insert_nuc=elem.insertion_nuc)
        elif isinstance(elem, RelationalElement):
            self._add_element(TYPE_RELATIONAL, elem.name,
                              mm=str(elem.mismatches), mispairs=str(elem.mispairs),
                              pos_strand=elem.pos_strand, neg_strand=elem.neg_strand,
                              insertions=str(elem.insertions) if elem.insertions else "",
                              insert_nuc=elem.insertion_nuc,
                              transform=elem.transform)
        elif isinstance(elem, SingleStrandedElement):
            self._add_element(TYPE_SINGLE, elem.name,
                              mm=str(elem.mismatches),
                              pos_strand=elem.sequence,
                              insertions=str(elem.insertions) if elem.insertions else "",
                              insert_nuc=elem.insertion_nuc)

    # ------------------------------------------------------------------
    # Element rows
    # ------------------------------------------------------------------

    def _add_element(self, elem_type: str = TYPE_HELIX, name: str = "",
                     mm: str = "0", mispairs: str = "0",
                     pos_strand: str = "", neg_strand: str = "",
                     insertions: str = "", insert_nuc: str = "",
                     transform: str = ""):
        if len(self._element_rows) >= MAX_ELEMENTS:
            messagebox.showwarning("Limit", f"Maximum {MAX_ELEMENTS} elements.",
                                   parent=self.dialog)
            return

        # Row 1: name, type, mismatches, mispairs
        row1 = ctk.CTkFrame(self._elements_frame, fg_color="transparent")
        row1.pack(fill=tk.X, pady=(4, 0))

        name_var = tk.StringVar(value=name)
        ctk.CTkEntry(row1, textvariable=name_var, width=45,
                     font=ctk.CTkFont(family="Consolas", size=11),
                     placeholder_text="h1").pack(side=tk.LEFT, padx=(0, 4))

        type_var = tk.StringVar(value=elem_type)
        type_menu = ctk.CTkOptionMenu(
            row1, variable=type_var,
            values=[TYPE_HELIX, TYPE_SINGLE, TYPE_RELATIONAL],
            width=155)
        type_menu.pack(side=tk.LEFT, padx=(0, 6))

        ctk.CTkLabel(row1, text="Mm:", width=28, font=ctk.CTkFont(size=11)).pack(side=tk.LEFT)
        mm_var = tk.StringVar(value=mm)
        ctk.CTkEntry(row1, textvariable=mm_var, width=30,
                     font=ctk.CTkFont(size=11)).pack(side=tk.LEFT, padx=(2, 6))

        ctk.CTkLabel(row1, text="Mispairs:", width=55, font=ctk.CTkFont(size=11)).pack(side=tk.LEFT)
        mispairs_var = tk.StringVar(value=mispairs)
        mp_entry = ctk.CTkEntry(row1, textvariable=mispairs_var, width=30,
                                font=ctk.CTkFont(size=11))
        mp_entry.pack(side=tk.LEFT, padx=(2, 6))

        ctk.CTkLabel(row1, text="Ins:", width=25, font=ctk.CTkFont(size=11)).pack(side=tk.LEFT)
        ins_var = tk.StringVar(value=insertions)
        ctk.CTkEntry(row1, textvariable=ins_var, width=30,
                     font=ctk.CTkFont(size=11),
                     placeholder_text="0").pack(side=tk.LEFT, padx=(2, 4))

        ctk.CTkLabel(row1, text="InsNuc:", width=45, font=ctk.CTkFont(size=11)).pack(side=tk.LEFT)
        ins_nuc_var = tk.StringVar(value=insert_nuc)
        ctk.CTkEntry(row1, textvariable=ins_nuc_var, width=35,
                     font=ctk.CTkFont(family="Consolas", size=11),
                     placeholder_text="N").pack(side=tk.LEFT, padx=(2, 0))

        # Row 2: sequences (pos_strand, neg_strand for helix/relational, or sequence for ss)
        row2 = ctk.CTkFrame(self._elements_frame, fg_color="transparent")
        row2.pack(fill=tk.X, pady=(0, 2))

        # Spacer to align with row1 content
        ctk.CTkFrame(row2, width=49, fg_color="transparent").pack(side=tk.LEFT)

        pos_label = ctk.CTkLabel(row2, text="5' strand:", width=65, font=ctk.CTkFont(size=11))
        pos_label.pack(side=tk.LEFT)
        pos_var = tk.StringVar(value=pos_strand)
        pos_entry = ctk.CTkEntry(row2, textvariable=pos_var, width=140,
                                 font=ctk.CTkFont(family="Consolas", size=11),
                                 placeholder_text="NNN**CC")
        pos_entry.pack(side=tk.LEFT, padx=(2, 6))

        neg_label = ctk.CTkLabel(row2, text="3' strand:", width=65, font=ctk.CTkFont(size=11))
        neg_label.pack(side=tk.LEFT)
        neg_var = tk.StringVar(value=neg_strand)
        neg_entry = ctk.CTkEntry(row2, textvariable=neg_var, width=140,
                                 font=ctk.CTkFont(family="Consolas", size=11),
                                 placeholder_text="GG**NNN")
        neg_entry.pack(side=tk.LEFT, padx=(2, 6))

        ctk.CTkLabel(row2, text="Transform:", width=68, font=ctk.CTkFont(size=11)).pack(side=tk.LEFT)
        transform_var = tk.StringVar(value=transform)
        transform_entry = ctk.CTkEntry(row2, textvariable=transform_var, width=55,
                                       font=ctk.CTkFont(family="Consolas", size=11),
                                       placeholder_text="TGCA")
        transform_entry.pack(side=tk.LEFT, padx=(2, 0))

        # Separator line
        sep = ctk.CTkFrame(self._elements_frame, height=1, fg_color="gray60")
        sep.pack(fill=tk.X, pady=(2, 2))

        info = {
            "row1": row1, "row2": row2, "sep": sep,
            "name_var": name_var, "type_var": type_var,
            "mm_var": mm_var, "mispairs_var": mispairs_var,
            "mispairs_entry": mp_entry,
            "ins_var": ins_var, "ins_nuc_var": ins_nuc_var,
            "pos_var": pos_var, "neg_var": neg_var,
            "pos_label": pos_label, "neg_label": neg_label,
            "neg_entry": neg_entry,
            "transform_var": transform_var, "transform_entry": transform_entry,
        }
        self._element_rows.append(info)

        # Wire type change
        idx = len(self._element_rows) - 1
        type_menu.configure(command=lambda v, i=idx: self._on_type_change(i))
        self._apply_type_visibility(info)

        # Live preview on any change
        for var in (name_var, mm_var, mispairs_var, ins_var, ins_nuc_var,
                    pos_var, neg_var, transform_var):
            var.trace_add("write", lambda *_: self._update_preview())

        self._update_preview()

    def _apply_type_visibility(self, info):
        """Show/hide fields based on element type."""
        t = info["type_var"].get()
        is_paired = (t == TYPE_HELIX or t == TYPE_RELATIONAL)
        is_relational = (t == TYPE_RELATIONAL)

        # Mispairs: only for helix/relational
        state = "normal" if is_paired else "disabled"
        info["mispairs_entry"].configure(state=state)

        # Neg strand: only for helix/relational
        info["neg_entry"].configure(state="normal" if is_paired else "disabled")
        neg_color = None if is_paired else MUTED
        if neg_color:
            info["neg_label"].configure(text_color=MUTED)
        else:
            info["neg_label"].configure(text_color=("gray90", "gray14"))

        # Transform: only for relational
        info["transform_entry"].configure(state="normal" if is_relational else "disabled")

        # Relabel for single-stranded
        if is_paired:
            info["pos_label"].configure(text="5' strand:")
        else:
            info["pos_label"].configure(text="Sequence:")

    def _on_type_change(self, idx: int):
        if idx >= len(self._element_rows):
            return
        info = self._element_rows[idx]
        self._apply_type_visibility(info)
        self._update_preview()

    def _remove_element(self):
        if not self._element_rows:
            return
        info = self._element_rows.pop()
        info["row1"].destroy()
        info["row2"].destroy()
        info["sep"].destroy()
        self._update_preview()

    def _clear_elements(self):
        for info in self._element_rows:
            info["row1"].destroy()
            info["row2"].destroy()
            info["sep"].destroy()
        self._element_rows.clear()

    def _auto_fill_from_map(self):
        map_text = self.motif_map_var.get().strip()
        if not map_text:
            messagebox.showwarning("Empty Map", "Enter a motif map first.",
                                   parent=self.dialog)
            return
        self._clear_elements()
        tokens = map_text.split()
        seen = set()
        for token in tokens:
            base = token.rstrip("'")
            if base in seen:
                continue
            seen.add(base)
            if base.startswith("r"):
                self._add_element(TYPE_RELATIONAL, base)
            elif base.startswith("h"):
                self._add_element(TYPE_HELIX, base)
            else:
                self._add_element(TYPE_SINGLE, base)
        self._update_preview()

    # ------------------------------------------------------------------
    # Descriptor preview
    # ------------------------------------------------------------------

    def _update_preview(self):
        spec = self._read_descriptor(validate=False)
        if spec is None:
            text = "(define elements above)"
        else:
            text = spec.to_descriptor_text()

        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Build descriptor from UI
    # ------------------------------------------------------------------

    def _read_descriptor(self, validate: bool = True):
        motif_map = self.motif_map_var.get().strip()
        if validate and not motif_map:
            messagebox.showerror("Missing Motif Map", "Enter a motif map.",
                                 parent=self.dialog)
            return None

        elements = []
        for i, info in enumerate(self._element_rows):
            name = info["name_var"].get().strip()
            t = info["type_var"].get()
            mm_str = info["mm_var"].get().strip()
            mispairs_str = info["mispairs_var"].get().strip()
            ins_str = info["ins_var"].get().strip()
            ins_nuc = info["ins_nuc_var"].get().strip()
            pos = info["pos_var"].get().strip()
            neg = info["neg_var"].get().strip()
            transform = info["transform_var"].get().strip()

            if validate and not name:
                messagebox.showerror("Invalid Element",
                                     f"Element {i+1}: name cannot be empty.",
                                     parent=self.dialog)
                return None

            def _int(s, default=0):
                try:
                    return int(s) if s else default
                except ValueError:
                    return default

            mm = _int(mm_str)
            mp = _int(mispairs_str)
            ins = _int(ins_str)

            if t == TYPE_HELIX:
                elements.append(HelixElement(
                    name=name, mismatches=mm, mispairs=mp,
                    pos_strand=pos, neg_strand=neg,
                    insertions=ins, insertion_nuc=ins_nuc))
            elif t == TYPE_RELATIONAL:
                elements.append(RelationalElement(
                    name=name, mismatches=mm, mispairs=mp,
                    pos_strand=pos, neg_strand=neg,
                    insertions=ins, insertion_nuc=ins_nuc,
                    transform=transform if transform else "TGCA"))
            else:
                elements.append(SingleStrandedElement(
                    name=name, mismatches=mm,
                    sequence=pos,
                    insertions=ins, insertion_nuc=ins_nuc))

        spec = DescriptorSpec(motif_map=motif_map, elements=elements)

        if validate:
            err = validate_descriptor(spec)
            if err:
                messagebox.showerror("Invalid Descriptor", err, parent=self.dialog)
                return None

        return spec

    # ------------------------------------------------------------------
    # File browsing
    # ------------------------------------------------------------------

    def _browse_input(self):
        fn = filedialog.askopenfilename(
            title="Select FASTA sequence file",
            filetypes=[("FASTA files", "*.fasta *.fa"), ("All files", "*.*")],
        )
        if fn:
            self.input_var.set(fn)

    # ------------------------------------------------------------------
    # Run search
    # ------------------------------------------------------------------

    def _run_search(self):
        descriptor = self._read_descriptor(validate=True)
        if descriptor is None:
            return

        seq_file = self.input_var.get().strip()
        if not seq_file or not Path(seq_file).exists():
            messagebox.showerror("Missing Input",
                                 "Select a valid FASTA sequence file.",
                                 parent=self.dialog)
            return

        # Parse optional nratio
        nratio = None
        nratio_str = self.nratio_var.get().strip()
        if nratio_str:
            try:
                nratio = float(nratio_str)
                if not (0.0 <= nratio <= 1.0):
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Invalid N-ratio",
                                     "N-ratio must be a number between 0.0 and 1.0.",
                                     parent=self.dialog)
                return

        self.run_btn.configure(state="disabled")
        self.export_btn.configure(state="disabled")
        self._clear_log()
        self._log("Starting RNArobo search...\n")
        self._results = None

        # Capture all tkinter variable values here in the main thread.
        # BooleanVar.get() is not thread-safe — reading it inside the
        # worker thread risks stale or corrupted values.
        both_strands = self.both_strands_var.get()
        non_overlapping = self.non_overlap_var.get()
        fasta_output = self.fasta_out_var.get()

        def run():
            try:
                result = run_rnarobo(
                    descriptor,
                    seq_file,
                    both_strands=both_strands,
                    non_overlapping=non_overlapping,
                    fasta_output=fasta_output,
                    nratio=nratio,
                    progress_callback=self._log,
                )

                self._results = result

                # Always report a non-zero exit code so the user knows
                # the search may have failed (e.g. bad descriptor syntax),
                # even when rnarobo produced no stderr output.
                if result.return_code != 0:
                    if result.raw_stderr.strip():
                        self._log(
                            f"\nrnarobo error (exit {result.return_code}):\n"
                            f"{result.raw_stderr.strip()}"
                        )
                    else:
                        self._log(
                            f"\nrnarobo exited with non-zero status "
                            f"({result.return_code}) — check descriptor syntax."
                        )

                self._display_results(result)

                if result.matches:
                    self._safe_after(lambda: self.export_btn.configure(state="normal"))

            except FileNotFoundError as e:
                self._log(f"\nError: {e}")
            except Exception as e:
                self._log(f"\nError: {e}")
            finally:
                self._safe_after(lambda: self.run_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _display_results(self, result):
        if not result.matches:
            self._log("\nNo matches found.")
            if result.total_bases:
                self._log(f"Total bases scanned: {result.total_bases:,}")
            return

        self._log(f"\n{'='*72}")
        self._log(f"{'Seq Name':<25} {'From':>7} {'To':>7} {'Strand':>7}")
        self._log(f"{'-'*72}")

        for m in result.matches:
            strand = "-" if m.is_reverse else "+"
            self._log(f"{m.seq_name:<25} {m.seq_from:>7} {m.seq_to:>7} {strand:>7}")
            if m.elements:
                self._log(f"  {m.elements}")

        self._log(f"{'='*72}")
        self._log(f"Total matches: {result.total_matches}")
        if result.total_bases:
            self._log(f"Total bases scanned: {result.total_bases:,}")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_results(self):
        if not self._results or not self._results.matches:
            messagebox.showinfo("No Results", "Run a search first.",
                                parent=self.dialog)
            return

        output_file = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Save results as...",
            initialdir=str(default_output_dir()),
            initialfile="rnarobo_results.tsv",
            filetypes=[("TSV files", "*.tsv"), ("Text files", "*.txt"),
                       ("All files", "*.*")],
            defaultextension=".tsv",
        )
        if not output_file:
            return

        def _tsv(val: str) -> str:
            """Sanitize a string for TSV output — remove embedded tabs/newlines."""
            return str(val).replace("\t", " ").replace("\r", " ").replace("\n", " ")

        with open(output_file, "w") as fh:
            fh.write("Seq_Name\tFrom\tTo\tStrand\tDescription\tMatched_Elements\n")
            for m in self._results.matches:
                strand = "-" if m.is_reverse else "+"
                fh.write(f"{_tsv(m.seq_name)}\t{m.seq_from}\t{m.seq_to}\t"
                         f"{strand}\t{_tsv(m.description)}\t{_tsv(m.elements)}\n")

        self._log(f"\nResults exported to: {output_file}")
        messagebox.showinfo("Export Complete",
                            f"Results saved to:\n{output_file}",
                            parent=self.dialog)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _safe_after(self, func):
        try:
            if self.dialog.winfo_exists():
                self.dialog.after(0, func)
        except Exception:
            pass

    def _log(self, message: str):
        def _append():
            self.progress_text.configure(state="normal")
            self.progress_text.insert(tk.END, message + "\n")
            self.progress_text.see(tk.END)
            self.progress_text.configure(state="disabled")
        self._safe_after(_append)

    def _clear_log(self):
        def _clear():
            self.progress_text.configure(state="normal")
            self.progress_text.delete("1.0", tk.END)
            self.progress_text.configure(state="disabled")
        self._safe_after(_clear)

    def show(self):
        self.dialog.wait_window()
