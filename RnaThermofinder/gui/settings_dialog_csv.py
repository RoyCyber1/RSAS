"""
Settings Dialog for RNA Thermometer Finder
Provides GUI for configuring CSV output columns
"""

import tkinter as tk
from tkinter import ttk, messagebox
from settings_manager import SettingsManager


class SettingsDialog_CSV:
    """
Settings Dialog for RNA Thermometer Finder
Provides GUI for configuring CSV output columns
UPDATED for RoyCyber1's complete data structure
"""
    def __init__(self, parent, settings_manager):
        self.parent = parent
        self.settings_manager = settings_manager
        self.checkboxes = {}

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("CSV Output Settings")
        self.dialog.geometry("650x800")
        self.dialog.resizable(False, False)

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

        # Center the dialog
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create all dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="CSV Output Configuration",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Preset Profiles Section
        self._create_preset_section(main_frame)

        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        # Custom Settings Section
        self._create_custom_section(main_frame)

        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        # Buttons
        self._create_button_section(main_frame)

    def _create_preset_section(self, parent):
        """Create preset profile buttons"""
        preset_frame = ttk.LabelFrame(parent, text="Quick Presets", padding="10")
        preset_frame.pack(fill=tk.X, pady=(0, 10))

        desc_label = ttk.Label(
            preset_frame,
            text="Choose a preset configuration or customize below:",
            font=("Arial", 9)
        )
        desc_label.pack(anchor=tk.W, pady=(0, 10))

        button_frame = ttk.Frame(preset_frame)
        button_frame.pack(fill=tk.X)

        # Standard Profile Button
        standard_btn = ttk.Button(
            button_frame,
            text="Hairpin Preset",
            command=self._apply_standard_preset,
            width=25
        )
        standard_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Cancer Research Profile Button
        cancer_btn = ttk.Button(
            button_frame,
            text="Preset 2",
            command=self._apply_cancer_research_preset,
            width=25
        )
        cancer_btn.pack(side=tk.LEFT, padx=5)

        cold_btn = ttk.Button(
            button_frame,
            text="Riboswitch",
            command=self._apply_cold_riboswitch_preset,
            width=20
        )
        cold_btn.pack(side=tk.LEFT, padx=5)

        # Add tooltips/descriptions
        tooltip_frame = ttk.Frame(preset_frame)
        tooltip_frame.pack(fill=tk.X, pady=(10, 0))

        standard_desc = ttk.Label(
            tooltip_frame,
            text="Standard: Hairpin-focused analysis with quality scoring",
            font=("Arial", 8),
            foreground="gray"
        )
        standard_desc.pack(anchor=tk.W)

        cancer_desc = ttk.Label(
            tooltip_frame,
            text="Cancer Research: Adds complete sequence MFE & composition at all temps",
            font=("Arial", 8),
            foreground="gray"
        )
        cancer_desc.pack(anchor=tk.W)

        # ✨ NEW: Cold riboswitch description
        cold_desc = ttk.Label(
            tooltip_frame,
            text="Riboswitch Preset: Focus on RBS sequestering differences (Δ temp)",
            font=("Arial", 8),
            foreground="gray"
        )
        cold_desc.pack(anchor=tk.W)

    def _create_custom_section(self, parent):
        """Create custom checkbox section"""
        custom_frame = ttk.LabelFrame(parent, text="Custom Column Selection", padding="10")
        custom_frame.pack(fill=tk.BOTH, expand=True)

        # Create scrollable frame
        canvas = tk.Canvas(custom_frame, height=350)
        scrollbar = ttk.Scrollbar(custom_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Define column groups
        column_groups = [
            ("Basic Information", [
                ("name", "Name (Sequence ID)"),
                ("original_sequence", "Complete Sequence"),
                ("original_structure", "Complete Structure (dot-bracket)")
            ]),
            ("Full-Length Structures", [
                ("full_structure_37", "Full Structure at 37°C"),
                ("full_structure_42", "Full Structure at 42°C")
            ]),

            ("Complete Sequence MFE at Temperatures", [
                ("original_mfe_25", "Original MFE at 25°C"),
                ("original_mfe_37", "Original MFE at 37°C"),
                ("original_mfe_42", "Original MFE at 42°C")
            ]),
            ("Complete Sequence Composition", [
                ("original_au_percent", "Original AU Percentage"),
                ("original_gc_percent", "Original GC Percentage"),
                ("original_gu_percent", "Original GU Percentage")
            ]),

            # ✨ NEW: Original Sequence Range Checks
            ("Complete Sequence Range Checks", [
                ("original_mfe_25_in_range", "Original MFE 25°C In Range"),
                ("original_mfe_37_in_range", "Original MFE 37°C In Range"),
                ("original_mfe_42_in_range", "Original MFE 42°C In Range"),
                ("original_au_in_range", "Original AU% In Range"),
                ("original_gc_in_range", "Original GC% In Range"),
                ("original_gu_in_range", "Original GU% In Range")
            ]),

            ("RBS Full Length Settings", [
                ("full_rbs_25_seq", "Full RBS 25°C Sequence"),
                ("full_rbs_25_struct", "Full RBS 25°C Structure"),
                ("full_rbs_25_paired", "Full RBS 25°C Paired%"),
                ("full_rbs_37_seq", "Full RBS 37°C Sequence"),
                ("full_rbs_37_struct", "Full RBS 37°C Structure"),
                ("full_rbs_37_paired", "Full RBS 37°C Paired%"),
                ("full_rbs_42_seq", "Full RBS 42°C Sequence"),
                ("full_rbs_42_struct", "Full RBS 42°C Structure"),
                ("full_rbs_42_paired", "Full RBS 42°C Paired%"),
                ("rbs_seq_diff_42_25", "RBS Sequestering Δ(42-25)"),
                ("rbs_seq_diff_37_25", "RBS Sequestering Δ(37-25)")
            ]),

            ("Terminal Hairpin Information", [
                ("hairpin_sequence", "Hairpin Sequence"),
                ("hairpin_structure", "Hairpin Structure")
            ]),
            ("Hairpin Composition", [
                ("hairpin_au_percent", "Hairpin AU Percentage"),
                ("hairpin_gc_percent", "Hairpin GC Percentage"),
                ("hairpin_gu_percent", "Hairpin GU Percentage")
            ]),
            ("Hairpin MFE at Temperatures", [
                ("mfe_25c_hairpin", "Hairpin MFE at 25°C"),
                ("mfe_37c_hairpin", "Hairpin MFE at 37°C"),
                ("mfe_42c_hairpin", "Hairpin MFE at 42°C")
            ]),
            ("Hairpin MFE Range Checks", [
                ("mfe_25_in_range_hairpin", "Hairpin MFE 25°C In Range"),
                ("mfe_37_in_range_hairpin", "Hairpin MFE 37°C In Range"),
                ("mfe_42_in_range_hairpin", "Hairpin MFE 42°C In Range")
            ]),
            ("Hairpin Composition Range Checks", [
                ("au_in_range_hairpin", "Hairpin AU% In Range"),
                ("gc_in_range_hairpin", "Hairpin GC% In Range"),
                ("gu_in_range_hairpin", "Hairpin GU% In Range")
            ]),
            ("RBS Analysis", [
                ("rbs_sequence", "RBS Sequence"),
                ("rbs_structure", "RBS Structure"),
                ("rbs_paired_percent", "RBS Paired Percentage")
            ]),
            ("Quality Metrics", [
                ("quality_score_hairpin", "Terminal Hairpin Quality Score (0-6)"),
                ("quality_score_original", "Original Sequence Quality Score (0-6)")
            ])
        ]

        # Create checkboxes grouped by category
        current_settings = self.settings_manager.settings["csv_output_columns"]

        for group_name, columns in column_groups:
            # Group header
            group_label = ttk.Label(
                scrollable_frame,
                text=group_name,
                font=("Arial", 10, "bold")
            )
            group_label.pack(anchor=tk.W, pady=(10, 5))

            # Checkboxes for this group
            for key, label in columns:
                var = tk.BooleanVar(value=current_settings.get(key, False))
                cb = ttk.Checkbutton(
                    scrollable_frame,
                    text=label,
                    variable=var
                )
                cb.pack(anchor=tk.W, padx=(20, 0), pady=2)
                self.checkboxes[key] = var

    def _create_button_section(self, parent):
        """Create action buttons"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(5, 0))

        # Reset to defaults
        reset_btn = ttk.Button(
            button_frame,
            text="Reset to Defaults",
            command=self._reset_to_defaults
        )
        reset_btn.pack(side=tk.LEFT)

        # Spacer
        ttk.Frame(button_frame).pack(side=tk.LEFT, expand=True)

        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        )
        cancel_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Save button
        save_btn = ttk.Button(
            button_frame,
            text="Save Settings",
            command=self._save_settings
        )
        save_btn.pack(side=tk.LEFT)

    def _apply_standard_preset(self):
        """Apply standard preset configuration"""
        standard_config = {
            "name": True,
            "original_sequence": True,
            "original_structure": True,

            # Full-length structures
            "full_structure_37": False,
            "full_structure_42": False,

            "original_mfe_25": False,
            "original_mfe_37": False,
            "original_mfe_42": False,
            "original_au_percent": False,
            "original_gc_percent": False,
            "original_gu_percent": False,

            "original_mfe_25_in_range": False,
            "original_mfe_37_in_range": False,
            "original_mfe_42_in_range": False,
            "original_au_in_range": False,
            "original_gc_in_range": False,
            "original_gu_in_range": False,

            # ✨ NEW: Full-length RBS (all disabled for standard)
            "full_rbs_25_seq": False,
            "full_rbs_25_struct": False,
            "full_rbs_25_paired": False,
            "full_rbs_37_seq": False,
            "full_rbs_37_struct": False,
            "full_rbs_37_paired": False,
            "full_rbs_42_seq": False,
            "full_rbs_42_struct": False,
            "full_rbs_42_paired": False,
            "rbs_seq_diff_42_25": False,
            "rbs_seq_diff_37_25": False,

            "hairpin_sequence": True,
            "hairpin_structure": True,
            "hairpin_au_percent": True,
            "hairpin_gc_percent": True,
            "hairpin_gu_percent": True,
            "mfe_25c_hairpin": True,
            "mfe_37c_hairpin": True,
            "mfe_42c_hairpin": True,
            "mfe_25_in_range_hairpin": True,
            "mfe_37_in_range_hairpin": True,
            "mfe_42_in_range_hairpin": True,
            "au_in_range_hairpin": True,
            "gc_in_range_hairpin": True,
            "gu_in_range_hairpin": True,
            "rbs_sequence": True,
            "rbs_structure": True,
            "rbs_paired_percent": True,
            "quality_score_hairpin": True,
            "quality_score_original": False
        }
        self._apply_preset(standard_config)

    def _apply_cancer_research_preset(self):
        """Apply cancer research preset configuration"""
        cancer_config = {
            "name": True,
            "original_sequence": True,
            "original_structure": True,
            "original_mfe_25": True,  # KEY: All original MFE temps
            "original_mfe_37": True,  # KEY
            "original_mfe_42": True,  # KEY
            "original_au_percent": True,  # KEY: Original composition
            "original_gc_percent": True,  # KEY
            "original_gu_percent": True,  # KEY

            "original_mfe_25_in_range": True,
            "original_mfe_37_in_range": True,
            "original_mfe_42_in_range": True,
            "original_au_in_range": True,
            "original_gc_in_range": True,
            "original_gu_in_range": True,

            "hairpin_sequence": True,
            "hairpin_structure": True,
            "hairpin_mfe": True,
            "hairpin_au_percent": True,
            "hairpin_gc_percent": True,
            "hairpin_gu_percent": True,
            "mfe_25c_hairpin": True,
            "mfe_37c_hairpin": True,
            "mfe_42c_hairpin": True,
            "mfe_25_in_range_hairpin": False,  # Less focus on range checks
            "mfe_37_in_range_hairpin": False,
            "mfe_42_in_range_hairpin": False,
            "au_in_range_hairpin": False,
            "gc_in_range_hairpin": False,
            "gu_in_range_hairpin": False,
            "rbs_sequence": True,
            "rbs_structure": True,
            "rbs_paired_percent": True,
            "quality_score_hairpin": True,
            "quality_score_original": True
        }
        self._apply_preset(cancer_config)

    def _apply_cold_riboswitch_preset(self):
        """Apply cold riboswitch detection preset configuration"""
        cold_config = {
            "name": True,
            "original_sequence": True,
            "original_structure": True,

            # Full-length structures (IMPORTANT for cold detection)
            "full_structure_37": True,
            "full_structure_42": True,

            # Original MFE (needed for structures at different temps)
            "original_mfe_25": True,
            "original_mfe_37": True,
            "original_mfe_42": True,

            # Original composition (optional, but useful)
            "original_au_percent": True,
            "original_gc_percent": True,
            "original_gu_percent": True,

            # Original range checks (not critical for cold detection)
            "original_mfe_25_in_range": True,
            "original_mfe_37_in_range": True,
            "original_mfe_42_in_range": True,
            "original_au_in_range": True,
            "original_gc_in_range": True,
            "original_gu_in_range": True,

            # ✨ CRITICAL: Full-length RBS sequestering (THE MAIN FOCUS)
            "full_rbs_25_seq": True,
            "full_rbs_25_struct": True,
            "full_rbs_25_paired": True,  # ← KEY: RBS at cold temp
            "full_rbs_37_seq": True,
            "full_rbs_37_struct": True,
            "full_rbs_37_paired": True,  # ← KEY: RBS at body temp
            "full_rbs_42_seq": True,
            "full_rbs_42_struct": True,
            "full_rbs_42_paired": True,  # ← KEY: RBS at high temp
            "rbs_seq_diff_42_25": True,  # ← 🔥 MOST IMPORTANT: Shows cold vs hot
            "rbs_seq_diff_37_25": True,  # ← 🔥 IMPORTANT: Shows cold vs normal

            # Hairpin info (basic, not the focus)
            "hairpin_sequence": True,
            "hairpin_structure": True,
            "hairpin_au_percent": True,
            "hairpin_gc_percent": True,
            "hairpin_gu_percent": True,

            # Hairpin MFE (optional)
            "mfe_25c_hairpin": True,
            "mfe_37c_hairpin": True,
            "mfe_42c_hairpin": True,

            # Hairpin range checks (not needed for cold detection)
            "mfe_25_in_range_hairpin": True,
            "mfe_37_in_range_hairpin": True,
            "mfe_42_in_range_hairpin": True,
            "au_in_range_hairpin": True,
            "gc_in_range_hairpin": True,
            "gu_in_range_hairpin": True,

            # Hairpin RBS (less important than full-length RBS)
            "rbs_sequence": True,
            "rbs_structure": True,
            "rbs_paired_percent": True,

            # Quality scores (optional)
            "quality_score_hairpin": True,
            "quality_score_original": False
        }
        self._apply_preset(cold_config)

    def _apply_preset(self, config: dict):
        """Apply a preset configuration to checkboxes"""
        for key, value in config.items():
            if key in self.checkboxes:
                self.checkboxes[key].set(value)

    def _reset_to_defaults(self):
        """Reset to default settings"""
        if messagebox.askyesno("Reset Settings", "Reset all settings to defaults?"):
            self.settings_manager.reset_to_defaults()
            self._apply_preset(self.settings_manager.settings["csv_output_columns"])
            messagebox.showinfo("Settings Reset", "Settings have been reset to defaults")

    def _save_settings(self):
        """Save current checkbox states to settings"""
        # Update settings from checkboxes
        for key, var in self.checkboxes.items():
            self.settings_manager.settings["csv_output_columns"][key] = var.get()

        # ✨ AUTO-ENABLE calculations based on selected columns
        calc_settings = self.settings_manager.settings.get("calculation_settings", {})

        # If any original MFE column is enabled, enable the calculation
        if (self.settings_manager.settings["csv_output_columns"].get("original_mfe_25", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_mfe_37", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_mfe_42", False)):
            calc_settings["calculate_original_mfe_temps"] = True
        else:
            calc_settings["calculate_original_mfe_temps"] = False

        # If any original composition column is enabled, enable the calculation
        if (self.settings_manager.settings["csv_output_columns"].get("original_au_percent", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_gc_percent", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_gu_percent", False)):
            calc_settings["calculate_original_composition"] = True
        else:
            calc_settings["calculate_original_composition"] = False

        # If any original range check column is enabled, enable the calculation
        if (self.settings_manager.settings["csv_output_columns"].get("original_mfe_25_in_range", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_mfe_37_in_range", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_mfe_42_in_range", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_au_in_range", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_gc_in_range", False) or
                self.settings_manager.settings["csv_output_columns"].get("original_gu_in_range", False) or
                self.settings_manager.settings["csv_output_columns"].get("quality_score_original", False)):
            calc_settings["calculate_original_range_checks"] = True
        else:
            calc_settings["calculate_original_range_checks"] = False

        # ✨ NEW: If any full-length RBS column is enabled, enable the calculation
        if (self.settings_manager.settings["csv_output_columns"].get("full_rbs_25_seq", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_25_struct", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_25_paired", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_37_seq", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_37_struct", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_37_paired", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_42_seq", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_42_struct", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_42_paired", False) or
                self.settings_manager.settings["csv_output_columns"].get("rbs_seq_diff_42_25", False) or
                self.settings_manager.settings["csv_output_columns"].get("rbs_seq_diff_37_25", False)):
            calc_settings["calculate_rbs_full_length"] = True
        else:
            calc_settings["calculate_rbs_full_length"] = False

        # ✨ NEW: If any 37°C or 42°C full structures/RBS columns are enabled, enable original MFE temps
        if (self.settings_manager.settings["csv_output_columns"].get("full_structure_37", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_structure_42", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_37_seq", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_37_struct", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_37_paired", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_42_seq", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_42_struct", False) or
                self.settings_manager.settings["csv_output_columns"].get("full_rbs_42_paired", False) or
                self.settings_manager.settings["csv_output_columns"].get("rbs_seq_diff_42_25", False) or
                self.settings_manager.settings["csv_output_columns"].get("rbs_seq_diff_37_25", False)):
            calc_settings["calculate_original_mfe_temps"] = True

        # Update calculation settings
        self.settings_manager.settings["calculation_settings"] = calc_settings

        # Save to file
        if self.settings_manager.save_settings():
            messagebox.showinfo("Settings Saved",
                                "CSV output settings saved successfully!\n\nCalculations optimized based on selected columns.")
            self.dialog.destroy()
        else:
            messagebox.showerror("Error", "Failed to save settings")

    def show(self):
        """Show the dialog and wait for it to close"""
        self.dialog.wait_window()