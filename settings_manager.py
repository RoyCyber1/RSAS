"""
Settings Manager for RNA Thermometer Finder
Handles configuration persistence using JSON
"""

import json
from pathlib import Path
from typing import Dict, Any

"""
Settings Manager for RNA Thermometer Finder
Handles configuration persistence using JSON
UPDATED for RoyCyber1's specific data structure
"""

import json
from pathlib import Path
from typing import Dict, Any


class SettingsManager:
    """Manages application settings with JSON persistence"""

    def __init__(self, settings_file: str = "csv_output_settings.json"):
        self.settings_file = Path(settings_file)
        self.default_settings = self._get_default_settings()
        self.settings = self.load_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        """Define default settings structure - matched to your data"""
        return {
            "csv_output_columns": {
                # Basic sequence info
                "name": True,
                "original_sequence": True,
                "original_structure": True,

                # ✨ NEW: Full-length structures at all temperatures
                "full_structure_37": False,
                "full_structure_42": False,

                # Original sequence MFE at different temps
                "original_mfe_25": False,  # NEW for cancer research
                "original_mfe_37": False,  # NEW for cancer research
                "original_mfe_42": False,  # NEW for cancer research

                # Original sequence composition
                "original_au_percent": False,  # NEW for cancer research
                "original_gc_percent": False,  # NEW for cancer research
                "original_gu_percent": False,  # NEW for cancer research

                #Original Sequence Range Checks
                "original_mfe_25_in_range": False,
                "original_mfe_37_in_range": False,
                "original_mfe_42_in_range": False,
                "original_au_in_range": False,
                "original_gc_in_range": False,
                "original_gu_in_range": False,

                # ✨ NEW: Full-length RBS sequestering at 25°C
                "full_rbs_25_seq": False,
                "full_rbs_25_struct": False,
                "full_rbs_25_paired": False,

                # ✨ NEW: Full-length RBS sequestering at 37°C
                "full_rbs_37_seq": False,
                "full_rbs_37_struct": False,
                "full_rbs_37_paired": False,

                # ✨ NEW: Full-length RBS sequestering at 42°C
                "full_rbs_42_seq": False,
                "full_rbs_42_struct": False,
                "full_rbs_42_paired": False,

                # ✨ NEW: RBS sequestering differences
                "rbs_seq_diff_42_25": False,
                "rbs_seq_diff_37_25": False,


                # Hairpin info
                "hairpin_sequence": True,
                "hairpin_structure": True,

                # Hairpin composition
                "hairpin_au_percent": True,
                "hairpin_gc_percent": True,
                "hairpin_gu_percent": True,

                # Hairpin MFE at temperatures
                "mfe_25c_hairpin": True,
                "mfe_37c_hairpin": True,
                "mfe_42c_hairpin": True,

                # Hairpin MFE range checks
                "mfe_25_in_range_hairpin": True,
                "mfe_37_in_range_hairpin": True,
                "mfe_42_in_range_hairpin": True,

                # Hairpin composition range checks
                "au_in_range_hairpin": True,
                "gc_in_range_hairpin": True,
                "gu_in_range_hairpin": True,

                # RBS info
                "rbs_sequence": True,
                "rbs_structure": True,
                "rbs_paired_percent": True,

                # Quality score
                "quality_score_hairpin": True,
                "quality_score_original": False  # ✨ NEW
            },

            "calculation_settings": {
                # Control which expensive calculations to perform
                "calculate_original_mfe_temps": False,  # MFE at 25/37/42°C for original sequence
                "calculate_original_composition": False,  # AU/GC/GU% for original sequence
                "calculate_original_range_checks": False,
                "calculate_hairpin_composition": True,  # Always calculate (needed for quality)
                "calculate_hairpin_mfe_temps": True,  # Always calculate (needed for quality)
                "calculate_rbs": True,  # RBS detection
                "calculate_rbs_full_length": False,  # NEW: RBS sequestering in full-length structures
            },
            "sequence_processing": {
                "append_sequence_enabled": False,
                "append_sequence": "AUG",
                "append_position": "end"  # "start" or "end"
            },

            "output_preferences": {
                "default_output_dir": "Data/Outputs",
                "create_structures_subdir": True,
                "auto_open_csv": False
            }
        }

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON file or create with defaults"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure new settings are added
                    return self._merge_settings(self.default_settings, loaded)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading settings: {e}. Using defaults.")
                return self.default_settings.copy()
        else:
            # Create settings file with defaults
            self.save_settings(self.default_settings)
            return self.default_settings.copy()

    def _merge_settings(self, defaults: Dict, loaded: Dict) -> Dict:
        """Merge loaded settings with defaults to add new options"""
        merged = defaults.copy()
        for key in merged:
            if key in loaded:
                if isinstance(merged[key], dict) and isinstance(loaded[key], dict):
                    merged[key] = self._merge_settings(merged[key], loaded[key])
                else:
                    merged[key] = loaded[key]
        return merged

    def save_settings(self, settings: Dict[str, Any] = None):
        """Save settings to JSON file"""
        if settings is None:
            settings = self.settings

        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            return True
        except IOError as e:
            print(f"Error saving settings: {e}")
            return False

    def get_enabled_columns(self) -> list:
        """Get list of enabled column names in order"""
        columns = []
        col_map = self.settings["csv_output_columns"]

        # Define the order of columns - MATCHED TO YOUR DATA STRUCTURE
        column_order = [
            ("name", "Name"),
            ("original_sequence", "Sequence"),
            ("original_structure", "Structure"),

            # ✨ NEW: Full-length structures
            ("full_structure_37", "Full_Structure_37C"),
            ("full_structure_42", "Full_Structure_42C"),


            ("original_mfe_25", "Original_MFE_25C"),
            ("original_mfe_37", "Original_MFE_37C"),
            ("original_mfe_42", "Original_MFE_42C"),
            ("original_au_percent", "Original_AU%"),
            ("original_gc_percent", "Original_GC%"),
            ("original_gu_percent", "Original_GU%"),

            ("original_mfe_25_in_range", "Original_MFE_25C_InRange"),
            ("original_mfe_37_in_range", "Original_MFE_37C_InRange"),
            ("original_mfe_42_in_range", "Original_MFE_42C_InRange"),
            ("original_au_in_range", "Original_AU%_InRange"),
            ("original_gc_in_range", "Original_GC%_InRange"),
            ("original_gu_in_range", "Original_GU%_InRange"),

            # ✨ NEW: Full-length RBS sequestering
            ("full_rbs_25_seq", "Full_RBS_25C_Seq"),
            ("full_rbs_25_struct", "Full_RBS_25C_Struct"),
            ("full_rbs_25_paired", "Full_RBS_25C_Paired%"),
            ("full_rbs_37_seq", "Full_RBS_37C_Seq"),
            ("full_rbs_37_struct", "Full_RBS_37C_Struct"),
            ("full_rbs_37_paired", "Full_RBS_37C_Paired%"),
            ("full_rbs_42_seq", "Full_RBS_42C_Seq"),
            ("full_rbs_42_struct", "Full_RBS_42C_Struct"),
            ("full_rbs_42_paired", "Full_RBS_42C_Paired%"),
            ("rbs_seq_diff_42_25", "RBS_Seq_Diff_42-25"),
            ("rbs_seq_diff_37_25", "RBS_Seq_Diff_37-25"),

            ("hairpin_sequence", "Hairpin_Sequence"),
            ("hairpin_structure", "Hairpin_Structure"),
            ("hairpin_au_percent", "Hairpin_AU%"),
            ("hairpin_gc_percent", "Hairpin_GC%"),
            ("hairpin_gu_percent", "Hairpin_GU%"),
            ("mfe_25c_hairpin", "Hairpin_MFE_25C"),
            ("mfe_37c_hairpin", "Hairpin_MFE_37C"),
            ("mfe_42c_hairpin", "Hairpin_MFE_42C"),
            ("mfe_25_in_range_hairpin", "Hairpin_MFE_25C_InRange"),
            ("mfe_37_in_range_hairpin", "Hairpin_MFE_37C_InRange"),
            ("mfe_42_in_range_hairpin", "Hairpin_MFE_42C_InRange"),
            ("au_in_range_hairpin", "Hairpin_AU%_InRange"),
            ("gc_in_range_hairpin", "Hairpin_GC%_InRange"),
            ("gu_in_range_hairpin", "Hairpin_GU%_InRange"),
            ("rbs_sequence", "RBS_Sequence"),
            ("rbs_structure", "RBS_Structure"),
            ("rbs_paired_percent", "RBS_Paired%"),
            ("quality_score_hairpin", "Quality_Score_Hairpin"),
            ("quality_score_original", "Quality_Score_Original")

        ]

        for key, display_name in column_order:
            if col_map.get(key, False):
                columns.append(display_name)

        return columns

    def update_column_setting(self, column_key: str, enabled: bool):
        """Update a specific column setting"""
        if column_key in self.settings["csv_output_columns"]:
            self.settings["csv_output_columns"][column_key] = enabled
            self.save_settings()

    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.settings = self.default_settings.copy()
        self.save_settings()
        return True