"""
Synthetic Pool Generator dialog.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import threading
import customtkinter as ctk

from RnaThermofinder.utils.synthetic_pool_generator import (
    PRESETS,
    validate_iupac,
    segments_preview,
    generate_pool,
)

ACCENT = "#2980b9"
ACCENT_HOVER = "#3498db"
MUTED = "#8b95a5"

MAX_SEGMENTS = 10


class SyntheticPoolDialog:
    """Dialog for generating synthetic RNA sequence pools."""

    def __init__(self, parent):
        self.parent = parent

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Synthetic Pool Generator")
        self.dialog.geometry("680x780")
        self.dialog.resizable(True, True)
        self.dialog.minsize(600, 600)
        self.dialog.transient(parent)
        self.dialog.after(100, self._try_grab)

        # Segment widget references
        self._segment_rows: list = []  # list of dicts with widget refs
        self._drag_idx = None          # index of segment row currently being dragged

        self._create_widgets()

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

    def _create_widgets(self):
        main = ctk.CTkScrollableFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        ctk.CTkLabel(main, text="Synthetic Pool Generator",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 2))
        ctk.CTkLabel(main,
                     text="Generate random RNA sequences with fixed motif inserts",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(0, 14))

        # Preset row
        preset_row = ctk.CTkFrame(main, fg_color="transparent")
        preset_row.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(preset_row, text="Preset:", width=60).pack(side=tk.LEFT)
        preset_names = ["Custom"] + list(PRESETS.keys())
        self.preset_var = tk.StringVar(value="Custom")
        self.preset_menu = ctk.CTkOptionMenu(
            preset_row, variable=self.preset_var,
            values=preset_names, width=180)
        self.preset_menu.pack(side=tk.LEFT, padx=(4, 8))
        ctk.CTkButton(preset_row, text="Load Preset", width=100,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._load_preset).pack(side=tk.LEFT)

        # Sequence template
        tmpl_card = ctk.CTkFrame(main, corner_radius=10)
        tmpl_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(tmpl_card, text="Sequence Template",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        # Container for dynamic segment rows
        self._segments_frame = ctk.CTkFrame(tmpl_card, fg_color="transparent")
        self._segments_frame.pack(fill=tk.X, padx=16, pady=(0, 4))

        # Add / Remove buttons
        btn_row = ctk.CTkFrame(tmpl_card, fg_color="transparent")
        btn_row.pack(fill=tk.X, padx=16, pady=(0, 4))
        ctk.CTkButton(btn_row, text="+ Add Segment", width=120,
                      fg_color="gray40", hover_color="gray50",
                      command=self._add_segment).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(btn_row, text="Remove Last", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self._remove_segment).pack(side=tk.LEFT)
        ctk.CTkLabel(btn_row, text="  ⠿ Drag to reorder",
                     font=ctk.CTkFont(size=10), text_color=MUTED
                     ).pack(side=tk.LEFT, padx=(10, 0))

        # Preview label
        self.preview_var = tk.StringVar(value="(no segments)")
        ctk.CTkLabel(tmpl_card, textvariable=self.preview_var,
                     font=ctk.CTkFont(family="Consolas", size=11),
                     text_color=ACCENT
                     ).pack(anchor="w", padx=16, pady=(4, 12))

        # Pool settings
        pool_card = ctk.CTkFrame(main, corner_radius=10)
        pool_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(pool_card, text="Pool Settings",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 6))

        # Pool size
        size_row = ctk.CTkFrame(pool_card, fg_color="transparent")
        size_row.pack(fill=tk.X, padx=16, pady=3)
        ctk.CTkLabel(size_row, text="Pool Size:", width=120).pack(side=tk.LEFT)
        self.pool_size_var = tk.StringVar(value="1000000")
        ctk.CTkEntry(size_row, textvariable=self.pool_size_var,
                     width=140).pack(side=tk.LEFT, padx=4)

        # Random seed
        seed_row = ctk.CTkFrame(pool_card, fg_color="transparent")
        seed_row.pack(fill=tk.X, padx=16, pady=(3, 12))
        ctk.CTkLabel(seed_row, text="Random Seed:", width=120).pack(side=tk.LEFT)
        self.seed_var = tk.StringVar(value="")
        ctk.CTkEntry(seed_row, textvariable=self.seed_var, width=140,
                     placeholder_text="blank = random").pack(side=tk.LEFT, padx=4)

        # Composition targets
        comp_card = ctk.CTkFrame(main, corner_radius=10)
        comp_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(comp_card, text="Composition Targets (optional)",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(comp_card,
                     text="⚠  Composition is calculated on the WHOLE sequence (random + fixed segments combined), not just random regions.",
                     font=ctk.CTkFont(size=10), text_color="#e67e22",
                     wraplength=560, justify="left"
                     ).pack(anchor="w", padx=16, pady=(0, 8))

        self._comp_widgets = {}
        for kind in ("GC", "AU", "GU"):
            self._create_comp_row(comp_card, kind)

        ctk.CTkFrame(comp_card, height=6, fg_color="transparent").pack()

        # Output
        out_card = ctk.CTkFrame(main, corner_radius=10)
        out_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(out_card, text="Output",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 6))

        out_row = ctk.CTkFrame(out_card, fg_color="transparent")
        out_row.pack(fill=tk.X, padx=16, pady=(0, 12))
        ctk.CTkLabel(out_row, text="Output File:", width=90).pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        ctk.CTkEntry(out_row, textvariable=self.output_var, width=360
                     ).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(out_row, text="Browse", width=80,
                      command=self._browse_output).pack(side=tk.LEFT, padx=4)

        # Progress
        prog_card = ctk.CTkFrame(main, corner_radius=10)
        prog_card.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(prog_card, text="Progress",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(12, 4))

        self.progress_text = ctk.CTkTextbox(
            prog_card, height=90,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled", corner_radius=6)
        self.progress_text.pack(fill=tk.X, padx=12, pady=(0, 12))

        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=(4, 0))

        self.generate_btn = ctk.CTkButton(
            btn_frame, text="Generate", width=140,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._generate)
        self.generate_btn.pack(side=tk.LEFT)

        ctk.CTkButton(btn_frame, text="Close", width=100,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _create_comp_row(self, parent, kind: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, padx=16, pady=2)

        enabled_var = tk.BooleanVar(value=False)
        target_var = tk.StringVar(value="")
        tolerance_var = tk.StringVar(value="5")

        cb = ctk.CTkCheckBox(row, text=f"{kind}%", variable=enabled_var,
                             width=70,
                             command=lambda: self._on_comp_toggle(kind))
        cb.pack(side=tk.LEFT)

        lbl_t = ctk.CTkLabel(row, text="Target:", width=55)
        lbl_t.pack(side=tk.LEFT, padx=(8, 2))
        target_entry = ctk.CTkEntry(row, textvariable=target_var, width=60,
                                    state="disabled",
                                    placeholder_text="%")
        target_entry.pack(side=tk.LEFT, padx=(0, 4))

        ctk.CTkLabel(row, text="\u00b1", width=15).pack(side=tk.LEFT)
        tolerance_entry = ctk.CTkEntry(row, textvariable=tolerance_var,
                                       width=50, state="disabled")
        tolerance_entry.pack(side=tk.LEFT, padx=(2, 2))
        ctk.CTkLabel(row, text="%", width=20).pack(side=tk.LEFT)

        self._comp_widgets[kind] = {
            "enabled": enabled_var,
            "target": target_var,
            "tolerance": tolerance_var,
            "target_entry": target_entry,
            "tolerance_entry": tolerance_entry,
        }

    def _on_comp_toggle(self, kind: str):
        w = self._comp_widgets[kind]
        state = "normal" if w["enabled"].get() else "disabled"
        w["target_entry"].configure(state=state)
        w["tolerance_entry"].configure(state=state)

    def _add_segment(self, seg_type: str = "random", value: str = ""):
        if len(self._segment_rows) >= MAX_SEGMENTS:
            messagebox.showwarning("Limit", f"Maximum {MAX_SEGMENTS} segments.",
                                   parent=self.dialog)
            return

        # Capture index BEFORE appending so drag callbacks reference correct position
        seg_idx = len(self._segment_rows)
        idx = seg_idx + 1

        row = ctk.CTkFrame(self._segments_frame, fg_color="transparent")
        row.pack(fill=tk.X, pady=2)

        # ── Drag handle ─────────────────────────────────────────────────
        # Grab and drag up/down to reorder segments without deleting them
        handle = ctk.CTkLabel(row, text="⠿", width=22,
                              font=ctk.CTkFont(size=14), text_color=MUTED)
        handle.pack(side=tk.LEFT, padx=(0, 2))
        handle.bind("<Button-1>",       lambda e, i=seg_idx: self._drag_start(e, i))
        handle.bind("<B1-Motion>",      self._drag_motion)
        handle.bind("<ButtonRelease-1>", self._drag_end)

        ctk.CTkLabel(row, text=f"Seg {idx}:", width=50,
                     font=ctk.CTkFont(size=12)).pack(side=tk.LEFT)

        type_var = tk.StringVar(value=seg_type.capitalize())
        type_menu = ctk.CTkOptionMenu(
            row, variable=type_var, values=["Random", "Fixed"],
            width=90)
        type_menu.pack(side=tk.LEFT, padx=(4, 4))

        # Label that changes between "Length:" and "Motif:"
        label_var = tk.StringVar(value="Length:" if seg_type == "random" else "Motif:")
        lbl = ctk.CTkLabel(row, textvariable=label_var, width=50)
        lbl.pack(side=tk.LEFT, padx=(4, 2))

        entry_var = tk.StringVar(value=value)
        entry = ctk.CTkEntry(row, textvariable=entry_var, width=140,
                             font=ctk.CTkFont(family="Consolas", size=12))
        entry.pack(side=tk.LEFT, padx=(0, 4))

        # Bind for live preview
        entry_var.trace_add("write", lambda *_: self._update_preview())

        info = {
            "row": row,
            "type_var": type_var,
            "label_var": label_var,
            "entry_var": entry_var,
        }
        self._segment_rows.append(info)

        # Wire type change callback
        type_menu.configure(
            command=lambda v, i=seg_idx: self._on_seg_type_change(i))

        self._update_preview()

    def _remove_segment(self):
        if not self._segment_rows:
            return
        info = self._segment_rows.pop()
        info["row"].destroy()
        self._update_preview()

    def _on_seg_type_change(self, idx: int):
        if idx >= len(self._segment_rows):
            return
        info = self._segment_rows[idx]
        new_type = info["type_var"].get().lower()
        info["label_var"].set("Length:" if new_type == "random" else "Motif:")
        info["entry_var"].set("")
        self._update_preview()

    def _clear_segments(self):
        for info in self._segment_rows:
            info["row"].destroy()
        self._segment_rows.clear()
        self._update_preview()

    # ------------------------------------------------------------------
    # Drag-to-reorder
    # ------------------------------------------------------------------

    def _drag_start(self, event, idx: int):
        """Record which segment row began being dragged."""
        self._drag_idx = idx

    def _drag_motion(self, event):
        """Highlight the drop target while the user is dragging."""
        if self._drag_idx is None:
            return
        y_abs = event.widget.winfo_rooty() + event.y
        target = self._get_drop_idx(y_abs)
        for i, info in enumerate(self._segment_rows):
            # Highlight the row we would land on (but not the row being dragged)
            if i == target and i != self._drag_idx:
                info["row"].configure(fg_color="gray30")
            else:
                info["row"].configure(fg_color="transparent")

    def _drag_end(self, event):
        """Complete the drag — reorder segments if the position changed."""
        if self._drag_idx is None:
            return
        from_idx = self._drag_idx
        self._drag_idx = None
        y_abs = event.widget.winfo_rooty() + event.y
        to_idx = self._get_drop_idx(y_abs)
        # Reset any row highlights
        for info in self._segment_rows:
            info["row"].configure(fg_color="transparent")
        if from_idx != to_idx:
            self._reorder_segments(from_idx, to_idx)

    def _get_drop_idx(self, y_abs: int) -> int:
        """Return the segment index whose row midpoint is closest to y_abs (screen coords)."""
        best_idx = 0
        best_dist = float("inf")
        for i, info in enumerate(self._segment_rows):
            try:
                row_y = info["row"].winfo_rooty()
                row_h = info["row"].winfo_height()
                mid = row_y + row_h // 2
                dist = abs(y_abs - mid)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
            except Exception:
                pass
        return best_idx

    def _reorder_segments(self, from_idx: int, to_idx: int):
        """Move the segment at from_idx to to_idx, then rebuild the entire segment UI.

        Rebuilding from scratch is simpler and safer than trying to re-pack
        CTk frames in place — it also renumbers the 'Seg N:' labels correctly.
        """
        # Snapshot current segment data
        snapshot = []
        for info in self._segment_rows:
            snapshot.append({
                "type": info["type_var"].get().lower(),
                "value": info["entry_var"].get(),
            })
        # Move the dragged item to its new position
        item = snapshot.pop(from_idx)
        snapshot.insert(to_idx, item)
        # Destroy existing rows and rebuild in new order
        for info in self._segment_rows:
            info["row"].destroy()
        self._segment_rows.clear()
        for snap in snapshot:
            self._add_segment(snap["type"], snap["value"])

    def _update_preview(self):
        segments = self._read_segments(validate=False)
        if not segments:
            self.preview_var.set("(no segments)")
            return
        try:
            self.preview_var.set(segments_preview(segments))
        except Exception:
            self.preview_var.set("(invalid segments)")

    def _load_preset(self):
        name = self.preset_var.get()
        if name == "Custom":
            self._clear_segments()
            return
        preset = PRESETS.get(name)
        if not preset:
            return
        self._clear_segments()
        for seg in preset:
            if seg["type"] == "random":
                self._add_segment("random", str(seg["length"]))
            else:
                self._add_segment("fixed", seg["motif"])

    def _read_segments(self, validate: bool = True):
        """Read segments from UI. Returns list of dicts or None on error."""
        segments = []
        for i, info in enumerate(self._segment_rows):
            seg_type = info["type_var"].get().lower()
            val = info["entry_var"].get().strip()

            if seg_type == "random":
                if validate:
                    try:
                        length = int(val)
                        if length <= 0:
                            raise ValueError()
                    except ValueError:
                        messagebox.showerror(
                            "Invalid Segment",
                            f"Segment {i + 1}: enter a positive integer for random region length.",
                            parent=self.dialog)
                        return None
                else:
                    try:
                        length = int(val)
                    except ValueError:
                        length = 0
                segments.append({"type": "random", "length": length})
            else:
                motif = val.upper()
                if validate:
                    if not motif:
                        messagebox.showerror(
                            "Invalid Segment",
                            f"Segment {i + 1}: enter a motif (IUPAC nucleotides).",
                            parent=self.dialog)
                        return None
                    err = validate_iupac(motif)
                    if err:
                        messagebox.showerror(
                            "Invalid Segment",
                            f"Segment {i + 1}: {err}",
                            parent=self.dialog)
                        return None
                segments.append({"type": "fixed", "motif": motif if motif else "?"})
        return segments

    def _browse_output(self):
        fn = filedialog.asksaveasfilename(
            title="Save pool as...",
            initialdir=str(Path.home() / "Downloads"),
            initialfile="synthetic_pool.fasta",
            filetypes=[("FASTA files", "*.fasta *.fa"), ("All files", "*.*")],
            defaultextension=".fasta",
        )
        if fn:
            self.output_var.set(fn)

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

    def _generate(self):
        # Segments
        segments = self._read_segments(validate=True)
        if segments is None:
            return
        if not segments:
            messagebox.showerror("No Segments",
                                 "Add at least one segment to the template.",
                                 parent=self.dialog)
            return

        # Pool size
        try:
            pool_size = int(self.pool_size_var.get().strip())
            if pool_size <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Invalid Pool Size",
                                 "Pool size must be a positive integer.",
                                 parent=self.dialog)
            return

        # Seed
        seed_str = self.seed_var.get().strip()
        seed = None
        if seed_str:
            try:
                seed = int(seed_str)
            except ValueError:
                messagebox.showerror("Invalid Seed",
                                     "Random seed must be an integer (or leave blank).",
                                     parent=self.dialog)
                return

        # Composition targets
        targets = []
        for kind in ("GC", "AU", "GU"):
            w = self._comp_widgets[kind]
            if not w["enabled"].get():
                continue
            try:
                target_pct = float(w["target"].get().strip())
                if not (0 <= target_pct <= 100):
                    raise ValueError()
            except ValueError:
                messagebox.showerror(
                    "Invalid Target",
                    f"{kind}% target must be a number between 0 and 100.",
                    parent=self.dialog)
                return
            try:
                tol_pct = float(w["tolerance"].get().strip())
                if tol_pct < 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror(
                    "Invalid Tolerance",
                    f"{kind}% tolerance must be a non-negative number.",
                    parent=self.dialog)
                return
            targets.append({
                "type": kind.lower(),
                "target": target_pct,
                "tolerance": tol_pct,
            })

        # Output file
        output_file = self.output_var.get().strip()
        if not output_file:
            messagebox.showerror("No Output File",
                                 "Select an output file location.",
                                 parent=self.dialog)
            return

        self.generate_btn.configure(state="disabled")
        self.progress_text.configure(state="normal")
        self.progress_text.delete("1.0", tk.END)
        self.progress_text.configure(state="disabled")
        self._log("Starting pool generation...")

        def run():
            try:
                def progress_cb(current, total, msg):
                    self._log(msg)

                result = generate_pool(
                    n=pool_size,
                    segments=segments,
                    output_file=output_file,
                    targets=targets if targets else None,
                    seed=seed,
                    progress_callback=progress_cb,
                )

                written = result["written"]
                failed = result["failed"]
                fpath = result["file"]

                if written == 0 and failed > 0:
                    # All sequences were rejected by composition filters
                    self._log(
                        f"⚠  All {failed:,} sequences were filtered out — "
                        f"composition constraints are too strict.\n"
                        f"   Try relaxing target % values or increasing tolerance."
                    )
                    self._safe_after(lambda: messagebox.showwarning(
                        "No Sequences Written",
                        f"All {failed:,} attempted sequences were filtered out.\n\n"
                        f"Composition targets may be impossible to satisfy "
                        f"given the current sequence length and fixed motifs.\n\n"
                        f"Try: relaxing target %, increasing tolerance, "
                        f"or shortening fixed segments.",
                        parent=self.dialog,
                    ))
                else:
                    summary = f"Done! {written:,} sequences written to {fpath}"
                    if failed:
                        summary += f" ({failed:,} filtered out)"
                    self._log(summary)
                    self._safe_after(lambda: messagebox.showinfo(
                        "Generation Complete",
                        f"Pool generated successfully!\n\n"
                        f"Sequences written: {written:,}\n"
                        + (f"Filtered out: {failed:,}\n" if failed else "")
                        + f"\nOutput: {fpath}",
                        parent=self.dialog,
                    ))
            except Exception as e:
                self._log(f"Error: {e}")
                self._safe_after(lambda: messagebox.showerror(
                    "Error", str(e), parent=self.dialog))
            finally:
                self._safe_after(lambda: self.generate_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def show(self):
        self.dialog.wait_window()
