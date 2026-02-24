"""
Quality Score Builder Dialog — CustomTkinter edition.

Allows scientists to create, edit, and manage scoring profiles with:
  - Selectable metrics (MFE, composition, PF Ensemble, RBS Sequestered)
  - Per-criterion min/max ranges, weights (1-5), and tolerance zones
  - Customizable classification tiers
  - Saveable/loadable profiles

Parameterized for both Hairpin and Full-Length scoring contexts.
"""

import copy
import tkinter as tk
from tkinter import messagebox, simpledialog
import customtkinter as ctk

from RnaThermofinder.utils.quality_scoring import (
    AVAILABLE_METRICS_HAIRPIN,
    AVAILABLE_METRICS_FULL,
    build_hairpin_metrics,
    build_full_metrics,
    get_default_hairpin_profile,
    get_default_full_length_profile,
    get_default_tiers,
    validate_profile,
)


class _CriterionRow:
    """One row in the criteria list — metric + min + max + weight + tolerance + remove."""

    def __init__(self, parent_frame, row_index, on_remove, on_change,
                 metrics_registry=None,
                 metric="mfe_25c_hairpin", min_val=0.0, max_val=100.0,
                 weight=1, tolerance=0.0):
        self.parent_frame = parent_frame
        self.on_remove = on_remove
        self.on_change = on_change
        self._metrics_registry = metrics_registry or AVAILABLE_METRICS_HAIRPIN
        self.frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        self.frame.pack(fill=tk.X, pady=3, padx=4)

        # Metric dropdown
        self._metric_labels = {v["label"]: k for k, v in self._metrics_registry.items()}
        labels = list(self._metric_labels.keys())
        current_label = self._metrics_registry.get(metric, {}).get("label", labels[0])

        self.metric_var = tk.StringVar(value=current_label)
        self.metric_menu = ctk.CTkOptionMenu(
            self.frame, variable=self.metric_var, values=labels,
            width=200, command=lambda _: self._notify_change())
        self.metric_menu.pack(side=tk.LEFT, padx=(0, 6))

        # Min
        ctk.CTkLabel(self.frame, text="Min:", font=ctk.CTkFont(size=11)
                     ).pack(side=tk.LEFT, padx=(4, 2))
        self.min_var = tk.DoubleVar(value=min_val)
        self.min_var.trace_add("write", lambda *a: self._notify_change())
        ctk.CTkEntry(self.frame, textvariable=self.min_var, width=65
                     ).pack(side=tk.LEFT, padx=(0, 6))

        # Max
        ctk.CTkLabel(self.frame, text="Max:", font=ctk.CTkFont(size=11)
                     ).pack(side=tk.LEFT, padx=(4, 2))
        self.max_var = tk.DoubleVar(value=max_val)
        self.max_var.trace_add("write", lambda *a: self._notify_change())
        ctk.CTkEntry(self.frame, textvariable=self.max_var, width=65
                     ).pack(side=tk.LEFT, padx=(0, 6))

        # Weight
        ctk.CTkLabel(self.frame, text="Wt:", font=ctk.CTkFont(size=11)
                     ).pack(side=tk.LEFT, padx=(4, 2))
        self.weight_var = tk.IntVar(value=weight)
        self.weight_label = ctk.CTkLabel(self.frame, text=str(weight),
                                         font=ctk.CTkFont(size=12, weight="bold"), width=20)
        self.weight_label.pack(side=tk.LEFT, padx=(0, 2))
        self.weight_slider = ctk.CTkSlider(
            self.frame, from_=1, to=5, number_of_steps=4, width=80,
            command=self._on_weight_change)
        self.weight_slider.set(weight)
        self.weight_slider.pack(side=tk.LEFT, padx=(0, 6))

        # Tolerance (grace zone)
        tol_label = ctk.CTkLabel(self.frame, text="Grace:", font=ctk.CTkFont(size=11))
        tol_label.pack(side=tk.LEFT, padx=(4, 2))
        self.tol_var = tk.DoubleVar(value=tolerance)
        self.tol_var.trace_add("write", lambda *a: self._notify_change())
        self.tol_entry = ctk.CTkEntry(self.frame, textvariable=self.tol_var, width=55)
        self.tol_entry.pack(side=tk.LEFT, padx=(0, 2))
        # Tooltip-style hint
        self.tol_hint = ctk.CTkLabel(self.frame, text="\u00b1",
                                      font=ctk.CTkFont(size=10), text_color="gray")
        self.tol_hint.pack(side=tk.LEFT, padx=(0, 6))

        # PF warning indicator
        metric_meta = self._metrics_registry.get(metric, {})
        self.pf_label = None
        if metric_meta.get("requires_pf"):
            self.pf_label = ctk.CTkLabel(self.frame, text="PF",
                                         font=ctk.CTkFont(size=9),
                                         text_color="orange")
            self.pf_label.pack(side=tk.LEFT, padx=(0, 4))

        # Remove button
        ctk.CTkButton(self.frame, text="\u2715", width=30, height=28,
                      fg_color="gray40", hover_color="#c0392b",
                      command=lambda: self.on_remove(self)
                      ).pack(side=tk.RIGHT)

    def _on_weight_change(self, val):
        w = int(round(val))
        self.weight_var.set(w)
        self.weight_label.configure(text=str(w))
        self._notify_change()

    def _notify_change(self):
        # Update PF indicator
        metric_id = self._metric_labels.get(self.metric_var.get(), "")
        meta = self._metrics_registry.get(metric_id, {})
        if self.pf_label:
            self.pf_label.destroy()
            self.pf_label = None
        if meta.get("requires_pf"):
            self.pf_label = ctk.CTkLabel(self.frame, text="PF",
                                         font=ctk.CTkFont(size=9),
                                         text_color="orange")
            self.pf_label.pack(side=tk.LEFT, padx=(0, 4))
        if self.on_change:
            self.on_change()

    def get_metric_id(self):
        return self._metric_labels.get(self.metric_var.get(), "")

    def to_dict(self):
        return {
            "metric": self.get_metric_id(),
            "min": self.min_var.get(),
            "max": self.max_var.get(),
            "weight": self.weight_var.get(),
            "tolerance": self.tol_var.get(),
        }

    def destroy(self):
        self.frame.destroy()


class _TierRow:
    """One row in the tier configuration — label + min_pct + description + remove."""

    def __init__(self, parent_frame, on_remove, on_change,
                 label="Tier", min_pct=0, description=""):
        self.on_remove = on_remove
        self.on_change = on_change
        self.frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        self.frame.pack(fill=tk.X, pady=2, padx=4)

        # Label
        ctk.CTkLabel(self.frame, text="Label:", font=ctk.CTkFont(size=11)
                     ).pack(side=tk.LEFT, padx=(0, 2))
        self.label_var = tk.StringVar(value=label)
        self.label_var.trace_add("write", lambda *a: self._notify_change())
        ctk.CTkEntry(self.frame, textvariable=self.label_var, width=80
                     ).pack(side=tk.LEFT, padx=(0, 6))

        # Min percentage
        ctk.CTkLabel(self.frame, text="Min %:", font=ctk.CTkFont(size=11)
                     ).pack(side=tk.LEFT, padx=(4, 2))
        self.min_pct_var = tk.IntVar(value=min_pct)
        self.min_pct_var.trace_add("write", lambda *a: self._notify_change())
        ctk.CTkEntry(self.frame, textvariable=self.min_pct_var, width=55
                     ).pack(side=tk.LEFT, padx=(0, 6))

        # Description
        ctk.CTkLabel(self.frame, text="Desc:", font=ctk.CTkFont(size=11)
                     ).pack(side=tk.LEFT, padx=(4, 2))
        self.desc_var = tk.StringVar(value=description)
        self.desc_var.trace_add("write", lambda *a: self._notify_change())
        ctk.CTkEntry(self.frame, textvariable=self.desc_var, width=150
                     ).pack(side=tk.LEFT, padx=(0, 6))

        # Remove button
        ctk.CTkButton(self.frame, text="\u2715", width=30, height=24,
                      fg_color="gray40", hover_color="#c0392b",
                      command=lambda: self.on_remove(self)
                      ).pack(side=tk.RIGHT)

    def _notify_change(self):
        if self.on_change:
            self.on_change()

    def to_dict(self):
        return {
            "label": self.label_var.get(),
            "min_pct": self.min_pct_var.get(),
            "description": self.desc_var.get(),
        }

    def destroy(self):
        self.frame.destroy()


class QualityScoreBuilderDialog:
    """Modal dialog for building and managing scoring profiles.

    Parameterized for hairpin or full-length context via `mode`.
    """

    ACCENT = "#2980b9"

    def __init__(self, parent, settings_manager, mode="hairpin"):
        """
        Args:
            parent: Parent window.
            settings_manager: SettingsManager instance.
            mode: "hairpin" or "full_length" -- determines which metrics/profiles to use.
        """
        self.settings_manager = settings_manager
        self.mode = mode
        self.criteria_rows = []
        self.tier_rows = []
        self._unsaved_changes = False

        # Build temperature-aware metric registries
        temps = None
        if hasattr(settings_manager, 'get_temperatures'):
            temps = settings_manager.get_temperatures()

        # Select mode-specific configuration
        if mode == "full_length":
            self._metrics_registry = build_full_metrics(temps)
            self._title = "Full-Length Quality Score Builder"
            self._default_profile_key = "default_full_length"
            self._default_profile_fn = lambda: get_default_full_length_profile(temps)
            self._get_profiles = settings_manager.get_all_full_scoring_profiles
            self._get_active_name = settings_manager.get_active_full_profile_name
            self._set_active = settings_manager.set_active_full_scoring_profile
            self._save_profile = settings_manager.save_full_scoring_profile
            self._delete_profile_fn = settings_manager.delete_full_scoring_profile
            self._get_active_profile = settings_manager.get_active_full_scoring_profile
        else:
            self._metrics_registry = build_hairpin_metrics(temps)
            self._title = "Terminal Hairpin Quality Score Builder"
            self._default_profile_key = "default_hairpin"
            self._default_profile_fn = lambda: get_default_hairpin_profile(temps)
            self._get_profiles = settings_manager.get_all_scoring_profiles
            self._get_active_name = settings_manager.get_active_profile_name
            self._set_active = settings_manager.set_active_scoring_profile
            self._save_profile = settings_manager.save_scoring_profile
            self._delete_profile_fn = settings_manager.delete_scoring_profile
            self._get_active_profile = settings_manager.get_active_scoring_profile

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(self._title)
        self.dialog.geometry("900x900")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()
        self._load_active_profile()

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _create_widgets(self):
        main = ctk.CTkFrame(self.dialog, fg_color="transparent")
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Title
        ctk.CTkLabel(main, text=self._title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 10))

        # --- Profile selector bar ---
        profile_bar = ctk.CTkFrame(main, fg_color="transparent")
        profile_bar.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(profile_bar, text="Profile:",
                     font=ctk.CTkFont(size=12)).pack(side=tk.LEFT, padx=(0, 8))

        self.profile_var = tk.StringVar()
        self.profile_menu = ctk.CTkOptionMenu(
            profile_bar, variable=self.profile_var, values=[""],
            width=220, command=self._on_profile_switch)
        self.profile_menu.pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(profile_bar, text="New", width=60,
                      command=self._new_profile).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(profile_bar, text="Duplicate", width=75,
                      command=self._duplicate_profile).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(profile_bar, text="Delete", width=60,
                      fg_color="gray40", hover_color="#c0392b",
                      command=self._delete_profile).pack(side=tk.LEFT, padx=2)

        self._refresh_profile_menu()

        # --- Criteria scrollable area ---
        ctk.CTkLabel(main, text="Scoring Criteria",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(6, 2))
        ctk.CTkLabel(main,
                     text="Each criterion: set Min/Max for full score (100%). "
                          "Wt = importance weight (1\u20135). "
                          "Grace = how far outside the range still gets partial credit "
                          "(e.g., Grace=2 means values up to 2 units outside the range "
                          "score linearly from 100% \u2192 0%). Set Grace=0 for strict pass/fail.",
                     font=ctk.CTkFont(size=10), text_color="gray",
                     wraplength=860, justify="left"
                     ).pack(anchor="w", pady=(0, 4))

        self.criteria_frame = ctk.CTkScrollableFrame(main, height=240)
        self.criteria_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        # --- Add criterion button ---
        add_bar = ctk.CTkFrame(main, fg_color="transparent")
        add_bar.pack(fill=tk.X, pady=(0, 6))

        ctk.CTkButton(add_bar, text="+ Add Criterion", width=140,
                      fg_color="#27ae60", hover_color="#2ecc71",
                      command=self._add_criterion_default).pack(side=tk.LEFT)

        self.pf_warn_label = ctk.CTkLabel(
            add_bar,
            text="PF = Requires PF output columns enabled for scoring",
            font=ctk.CTkFont(size=10), text_color="orange")
        self.pf_warn_label.pack(side=tk.RIGHT, padx=(10, 0))

        # --- Formula preview ---
        self.formula_label = ctk.CTkLabel(
            main, text="Score = ...",
            font=ctk.CTkFont(size=11), text_color="gray",
            wraplength=860, justify="left")
        self.formula_label.pack(anchor="w", pady=(0, 8))

        # --- Classification Tiers ---
        ctk.CTkLabel(main, text="Classification Tiers",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(main,
                     text="Define quality tiers based on the weighted score percentage. "
                          "Sequences are classified into the highest tier they meet. "
                          "Defaults are based on the legacy 0-6 scoring system.",
                     font=ctk.CTkFont(size=10), text_color="gray",
                     wraplength=860, justify="left"
                     ).pack(anchor="w", pady=(0, 4))

        self.tiers_frame = ctk.CTkScrollableFrame(main, height=120)
        self.tiers_frame.pack(fill=tk.X, pady=(0, 4))

        tier_btn_bar = ctk.CTkFrame(main, fg_color="transparent")
        tier_btn_bar.pack(fill=tk.X, pady=(0, 6))
        ctk.CTkButton(tier_btn_bar, text="+ Add Tier", width=100,
                      fg_color="#27ae60", hover_color="#2ecc71",
                      command=self._add_tier_default).pack(side=tk.LEFT)
        ctk.CTkButton(tier_btn_bar, text="Reset to Defaults", width=130,
                      fg_color="gray40", hover_color="gray50",
                      command=self._reset_tiers).pack(side=tk.LEFT, padx=(8, 0))

        # --- Action buttons ---
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill=tk.X)

        ctk.CTkButton(btn_frame, text="Cancel", width=90,
                      fg_color="gray40", hover_color="gray50",
                      command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ctk.CTkButton(btn_frame, text="Save Profile", width=120,
                      fg_color=self.ACCENT,
                      command=self._save_current_profile).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Profile Management
    # ------------------------------------------------------------------
    def _refresh_profile_menu(self):
        profiles = self._get_profiles()
        keys = list(profiles.keys())
        if not keys:
            keys = [self._default_profile_key]
        display_names = []
        self._profile_key_map = {}
        for k in keys:
            p = profiles.get(k, {})
            display = p.get("name", k)
            display_names.append(display)
            self._profile_key_map[display] = k

        self.profile_menu.configure(values=display_names)
        active_key = self._get_active_name()
        active_display = profiles.get(active_key, {}).get("name", active_key)
        self.profile_var.set(active_display)

    def _get_current_profile_key(self):
        display = self.profile_var.get()
        return self._profile_key_map.get(display, self._default_profile_key)

    def _on_profile_switch(self, _=None):
        if self._unsaved_changes:
            if messagebox.askyesno("Unsaved Changes",
                                   "You have unsaved changes. Save before switching?"):
                self._save_current_profile()
        key = self._get_current_profile_key()
        self._set_active(key)
        self._load_active_profile()

    def _load_active_profile(self):
        profile = self._get_active_profile()
        if not profile:
            profile = self._default_profile_fn()

        # Load criteria
        self._clear_criteria()
        first_metric = list(self._metrics_registry.keys())[0] if self._metrics_registry else ""
        for crit in profile.get("criteria", []):
            self._add_criterion(
                metric=crit.get("metric", first_metric),
                min_val=crit.get("min", 0),
                max_val=crit.get("max", 100),
                weight=crit.get("weight", 1),
                tolerance=crit.get("tolerance", 0),
            )

        # Load tiers
        self._clear_tiers()
        tiers = profile.get("tiers", get_default_tiers())
        for tier in tiers:
            self._add_tier(
                label=tier.get("label", "Tier"),
                min_pct=tier.get("min_pct", 0),
                description=tier.get("description", ""),
            )

        self._unsaved_changes = False
        self._update_formula()

    def _new_profile(self):
        name = simpledialog.askstring("New Profile", "Profile name:",
                                      parent=self.dialog)
        if not name or not name.strip():
            return
        name = name.strip()
        key = name.lower().replace(" ", "_")
        profiles = self._get_profiles()
        if key in profiles:
            messagebox.showerror("Error", f"Profile '{name}' already exists.")
            return
        self._save_profile(key, {
            "name": name,
            "criteria": [],
            "tiers": get_default_tiers(),
        })
        self._set_active(key)
        self._refresh_profile_menu()
        self.profile_var.set(name)
        self._load_active_profile()

    def _duplicate_profile(self):
        current_key = self._get_current_profile_key()
        current = self._get_profiles().get(current_key, {})
        name = simpledialog.askstring("Duplicate Profile",
                                      "Name for the copy:",
                                      parent=self.dialog)
        if not name or not name.strip():
            return
        name = name.strip()
        key = name.lower().replace(" ", "_")
        profiles = self._get_profiles()
        if key in profiles:
            messagebox.showerror("Error", f"Profile '{name}' already exists.")
            return
        dup = copy.deepcopy(current)
        dup["name"] = name
        self._save_profile(key, dup)
        self._set_active(key)
        self._refresh_profile_menu()
        self.profile_var.set(name)
        self._load_active_profile()

    def _delete_profile(self):
        key = self._get_current_profile_key()
        if key == self._default_profile_key:
            messagebox.showinfo("Cannot Delete",
                                "The default profile cannot be deleted.")
            return
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete profile '{self.profile_var.get()}'?"):
            return
        self._delete_profile_fn(key)
        self._refresh_profile_menu()
        active_key = self._get_active_name()
        profiles = self._get_profiles()
        active_display = profiles.get(active_key, {}).get("name", active_key)
        self.profile_var.set(active_display)
        self._load_active_profile()

    # ------------------------------------------------------------------
    # Criteria Management
    # ------------------------------------------------------------------
    def _clear_criteria(self):
        for row in self.criteria_rows:
            row.destroy()
        self.criteria_rows.clear()

    def _add_criterion(self, metric=None, min_val=0.0,
                       max_val=100.0, weight=1, tolerance=0.0):
        if metric is None:
            metric = list(self._metrics_registry.keys())[0] if self._metrics_registry else ""
        row = _CriterionRow(
            self.criteria_frame, len(self.criteria_rows),
            on_remove=self._remove_criterion,
            on_change=self._on_criterion_changed,
            metrics_registry=self._metrics_registry,
            metric=metric, min_val=min_val, max_val=max_val,
            weight=weight, tolerance=tolerance)
        self.criteria_rows.append(row)
        self._unsaved_changes = True
        self._update_formula()

    def _add_criterion_default(self):
        used = {r.get_metric_id() for r in self.criteria_rows}
        available = [k for k in self._metrics_registry if k not in used]
        if not available:
            messagebox.showinfo("All Metrics Added",
                                "All available metrics are already in this profile.")
            return
        self._add_criterion(metric=available[0])

    def _remove_criterion(self, row):
        row.destroy()
        self.criteria_rows.remove(row)
        self._unsaved_changes = True
        self._update_formula()

    def _on_criterion_changed(self):
        self._unsaved_changes = True
        self._update_formula()

    # ------------------------------------------------------------------
    # Tier Management
    # ------------------------------------------------------------------
    def _clear_tiers(self):
        for row in self.tier_rows:
            row.destroy()
        self.tier_rows.clear()

    def _add_tier(self, label="Tier", min_pct=0, description=""):
        row = _TierRow(
            self.tiers_frame,
            on_remove=self._remove_tier,
            on_change=self._on_tier_changed,
            label=label, min_pct=min_pct, description=description)
        self.tier_rows.append(row)
        self._unsaved_changes = True

    def _add_tier_default(self):
        next_num = len(self.tier_rows) + 1
        self._add_tier(label=f"Tier {next_num}", min_pct=0, description="Custom tier")

    def _remove_tier(self, row):
        row.destroy()
        self.tier_rows.remove(row)
        self._unsaved_changes = True

    def _on_tier_changed(self):
        self._unsaved_changes = True

    def _reset_tiers(self):
        self._clear_tiers()
        for tier in get_default_tiers():
            self._add_tier(
                label=tier["label"],
                min_pct=tier["min_pct"],
                description=tier["description"],
            )
        self._unsaved_changes = True

    # ------------------------------------------------------------------
    # Formula Preview
    # ------------------------------------------------------------------
    def _update_formula(self):
        if not self.criteria_rows:
            self.formula_label.configure(text="No criteria defined \u2014 add at least one criterion.")
            return

        parts = []
        total_weight = 0
        grace_notes = []
        for row in self.criteria_rows:
            d = row.to_dict()
            meta = self._metrics_registry.get(d["metric"], {})
            short = meta.get("label", d["metric"])
            w = d["weight"]
            tol = d["tolerance"]
            total_weight += w
            if w == 1:
                parts.append(short)
            else:
                parts.append(f"{w}\u00d7{short}")
            if tol > 0:
                grace_notes.append(f"{short} \u00b1{tol}")

        numerator = " + ".join(parts)
        formula_text = f"Score = ({numerator}) / {total_weight} \u00d7 100%"
        if grace_notes:
            formula_text += f"   |   Grace zones: {', '.join(grace_notes)}"
        self.formula_label.configure(text=formula_text)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def _save_current_profile(self):
        key = self._get_current_profile_key()
        criteria = [row.to_dict() for row in self.criteria_rows]
        tiers = [row.to_dict() for row in self.tier_rows]

        profile = {
            "name": self.profile_var.get(),
            "criteria": criteria,
            "tiers": tiers,
        }

        ok, err = validate_profile(profile, metrics_registry=self._metrics_registry)
        if not ok:
            messagebox.showerror("Validation Error", err)
            return

        self._save_profile(key, profile)
        self._set_active(key)
        self._unsaved_changes = False
        messagebox.showinfo("Saved", f"Profile '{profile['name']}' saved successfully.")

    # ------------------------------------------------------------------
    def show(self):
        self.dialog.wait_window()
