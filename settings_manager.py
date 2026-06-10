"""
Settings Manager for RSAS: RNA Structure Analysis Suite
Handles configuration persistence using JSON
"""

import copy
import json
import sys
import threading
from pathlib import Path
from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# User data directory — writable location for settings, recent files, outputs
# ---------------------------------------------------------------------------

def get_user_data_dir() -> Path:
    """Return the writable user data directory for RSAS.

    In a PyInstaller .app bundle the application directory is read-only.
    We always use ``~/.rsas/`` as the data root so settings, recent-files
    and default outputs survive across launches and updates.
    """
    data_dir = Path.home() / ".rsas"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def default_output_dir() -> Path:
    """Writable, user-visible default directory for saved outputs (``~/RSAS``).

    Avoids ~/Downloads, ~/Desktop and ~/Documents, which a packaged macOS app
    may be blocked from writing to without a permission prompt.
    """
    try:
        out = Path.home() / "RSAS"
        out.mkdir(parents=True, exist_ok=True)
        return out
    except OSError:
        return get_user_data_dir()


# ---------------------------------------------------------------------------
# Default temperatures — single source of truth
# ---------------------------------------------------------------------------
DEFAULT_TEMPERATURES = [25, 37, 42]


def _generate_temp_columns(temps: List[int]) -> Dict[str, bool]:
    """Generate the temperature-dependent csv_output_columns with defaults.

    Non-temperature columns have fixed defaults.  Temperature columns are
    generated dynamically from the given temperature list.
    """
    base = temps[0] if temps else 25
    cols: Dict[str, bool] = {}

    # ── Basic sequence info (always present) ──
    cols["name"] = True
    cols["original_sequence"] = True
    cols["original_structure"] = True

    # ── Full-length structures (all temps except base) ──
    for t in temps:
        if t != base:
            cols[f"full_structure_{t}"] = False

    # ── Original sequence MFE at each temp ──
    for t in temps:
        cols[f"original_mfe_{t}"] = False

    # ── Original sequence composition (not temp-dependent) ──
    cols["original_au_percent"] = False
    cols["original_gc_percent"] = False
    cols["original_gu_percent"] = False

    # ── Original Sequence Range Checks ──
    for t in temps:
        cols[f"original_mfe_{t}_in_range"] = False
    cols["original_au_in_range"] = False
    cols["original_gc_in_range"] = False
    cols["original_gu_in_range"] = False

    # ── Full-length RBS sequestering per temp ──
    for t in temps:
        cols[f"full_rbs_{t}_seq"] = False
        cols[f"full_rbs_{t}_struct"] = False
        cols[f"full_rbs_{t}_paired"] = False

    # ── RBS sequestering differences ──
    t_first = temps[0]
    if len(temps) >= 2:
        cols[f"rbs_seq_diff_{temps[-1]}_{t_first}"] = False
    if len(temps) >= 3:
        cols[f"rbs_seq_diff_{temps[-2]}_{t_first}"] = False

    # ── Hairpin detection info ──
    cols["hairpin_detection_method"] = False
    cols["rbs_detection_params"] = False
    cols["hairpin_sequence"] = True
    cols["hairpin_structure"] = True

    # ── Hairpin composition (not temp-dependent) ──
    cols["hairpin_au_percent"] = True
    cols["hairpin_gc_percent"] = True
    cols["hairpin_gu_percent"] = True

    # ── Hairpin MFE at each temp ──
    for t in temps:
        cols[f"mfe_{t}c_hairpin"] = True

    # ── Hairpin MFE range checks ──
    for t in temps:
        cols[f"mfe_{t}_in_range_hairpin"] = True

    # ── Hairpin composition range checks (not temp-dependent) ──
    cols["au_in_range_hairpin"] = True
    cols["gc_in_range_hairpin"] = True
    cols["gu_in_range_hairpin"] = True

    # ── RBS info (not temp-dependent) ──
    cols["rbs_sequence"] = True
    cols["rbs_structure"] = True
    cols["rbs_paired_percent"] = True

    # ── Hairpin Quality scores ──
    cols["hp_quality_score"] = True
    cols["hp_quality_score_weighted"] = True
    cols["hp_quality_score_class"] = True
    cols["hp_quality_score_breakdown"] = False

    # ── Full-Length Quality scores ──
    cols["fl_quality_score"] = False
    cols["fl_quality_score_weighted"] = False
    cols["fl_quality_score_class"] = False
    cols["fl_quality_score_breakdown"] = False

    # ── PF Ensemble range checks (hairpin) ──
    for t in temps:
        cols[f"pf_hp_ensemble_{t}_in_range"] = False

    # ── RBS Paired range check ──
    cols["rbs_paired_in_range"] = False

    # ── Partition Function features (full sequence) ──
    for t in temps:
        cols[f"pf_full_ensemble_{t}"] = False
        cols[f"pf_full_mean_paired_{t}"] = False

    # ── Partition Function features (hairpin) ──
    for t in temps:
        cols[f"pf_hp_ensemble_{t}"] = False
        cols[f"pf_hp_mean_paired_{t}"] = False

    # ── Partition Function RBS accessibility ──
    for t in temps:
        cols[f"pf_rbs_access_{t}"] = False
    if len(temps) >= 2:
        cols[f"pf_rbs_diff_{temps[-1]}_{t_first}"] = False
    if len(temps) >= 3:
        cols[f"pf_rbs_diff_{temps[-2]}_{t_first}"] = False

    # ── Motif / Sequence Finder ──
    cols["motif_pattern"] = False
    cols["motif_count"] = False
    cols["motif_match_seq"] = False
    cols["motif_match_pos"] = False
    for t in temps:
        cols[f"motif_paired_pct_{t}"] = False
        cols[f"motif_struct_{t}"] = False
        cols[f"motif_pf_access_{t}"] = False
    if len(temps) >= 2:
        cols[f"motif_paired_diff_{temps[-1]}_{t_first}"] = False
        cols[f"motif_pf_diff_{temps[-1]}_{t_first}"] = False
    if len(temps) >= 3:
        cols[f"motif_paired_diff_{temps[-2]}_{t_first}"] = False
        cols[f"motif_pf_diff_{temps[-2]}_{t_first}"] = False

    return cols


def _generate_column_order(temps: List[int]) -> list:
    """Generate the ordered list of (setting_key, display_name) tuples.

    This replaces the formerly hardcoded 71-entry column_order list.
    """
    base = temps[0] if temps else 25
    order = [
        ("name", "Name"),
        ("original_sequence", "Sequence"),
        ("original_structure", "Structure"),
    ]

    # Full-length structures
    for t in temps:
        if t != base:
            order.append((f"full_structure_{t}", f"Full_Structure_{t}C"))

    # Original MFE
    for t in temps:
        order.append((f"original_mfe_{t}", f"Original_MFE_{t}C"))
    order += [
        ("original_au_percent", "Original_AU%"),
        ("original_gc_percent", "Original_GC%"),
        ("original_gu_percent", "Original_GU%"),
    ]

    # Original range checks
    for t in temps:
        order.append((f"original_mfe_{t}_in_range", f"Original_MFE_{t}C_InRange"))
    order += [
        ("original_au_in_range", "Original_AU%_InRange"),
        ("original_gc_in_range", "Original_GC%_InRange"),
        ("original_gu_in_range", "Original_GU%_InRange"),
    ]

    # Full-length RBS sequestering
    for t in temps:
        order.append((f"full_rbs_{t}_seq", f"Full_RBS_{t}C_Seq"))
        order.append((f"full_rbs_{t}_struct", f"Full_RBS_{t}C_Struct"))
        order.append((f"full_rbs_{t}_paired", f"Full_RBS_{t}C_Paired%"))
    t_first = temps[0]
    if len(temps) >= 2:
        order.append((f"rbs_seq_diff_{temps[-1]}_{t_first}",
                       f"RBS_Seq_Diff_{temps[-1]}-{t_first}"))
    if len(temps) >= 3:
        order.append((f"rbs_seq_diff_{temps[-2]}_{t_first}",
                       f"RBS_Seq_Diff_{temps[-2]}-{t_first}"))

    # Hairpin info
    order += [
        ("hairpin_detection_method", "Hairpin_Detection_Method"),
        ("rbs_detection_params", "RBS_Detection_Params"),
        ("hairpin_sequence", "Hairpin_Sequence"),
        ("hairpin_structure", "Hairpin_Structure"),
        ("hairpin_au_percent", "Hairpin_AU%"),
        ("hairpin_gc_percent", "Hairpin_GC%"),
        ("hairpin_gu_percent", "Hairpin_GU%"),
    ]
    for t in temps:
        order.append((f"mfe_{t}c_hairpin", f"Hairpin_MFE_{t}C"))
    for t in temps:
        order.append((f"mfe_{t}_in_range_hairpin", f"Hairpin_MFE_{t}C_InRange"))
    order += [
        ("au_in_range_hairpin", "Hairpin_AU%_InRange"),
        ("gc_in_range_hairpin", "Hairpin_GC%_InRange"),
        ("gu_in_range_hairpin", "Hairpin_GU%_InRange"),
        ("rbs_sequence", "RBS_Sequence"),
        ("rbs_structure", "RBS_Structure"),
        ("rbs_paired_percent", "RBS_Paired%"),
    ]

    # PF full sequence
    for t in temps:
        order.append((f"pf_full_ensemble_{t}", f"PF_Full_Ensemble_{t}C"))
    for t in temps:
        order.append((f"pf_full_mean_paired_{t}", f"PF_Full_MeanPaired_{t}C"))
    # PF hairpin
    for t in temps:
        order.append((f"pf_hp_ensemble_{t}", f"PF_HP_Ensemble_{t}C"))
    for t in temps:
        order.append((f"pf_hp_mean_paired_{t}", f"PF_HP_MeanPaired_{t}C"))
    # PF RBS accessibility
    for t in temps:
        order.append((f"pf_rbs_access_{t}", f"PF_RBS_Access_{t}C"))
    if len(temps) >= 2:
        order.append((f"pf_rbs_diff_{temps[-1]}_{t_first}",
                       f"PF_RBS_Diff_{temps[-1]}-{t_first}"))
    if len(temps) >= 3:
        order.append((f"pf_rbs_diff_{temps[-2]}_{t_first}",
                       f"PF_RBS_Diff_{temps[-2]}-{t_first}"))

    # PF ensemble range checks (hairpin)
    for t in temps:
        order.append((f"pf_hp_ensemble_{t}_in_range", f"PF_HP_Ensemble_{t}C_InRange"))

    # RBS Paired range check
    order.append(("rbs_paired_in_range", "RBS_Paired%_InRange"))

    # Motif / Sequence Finder
    order.append(("motif_pattern", "Motif_Pattern"))
    order.append(("motif_count", "Motif_Count"))
    order.append(("motif_match_seq", "Motif_Match_Seq"))
    order.append(("motif_match_pos", "Motif_Match_Pos"))
    for t in temps:
        order.append((f"motif_paired_pct_{t}", f"Motif_Paired%_{t}C"))
        order.append((f"motif_struct_{t}", f"Motif_Struct_{t}C"))
        order.append((f"motif_pf_access_{t}", f"Motif_PF_Access_{t}C"))
    if len(temps) >= 2:
        order.append((f"motif_paired_diff_{temps[-1]}_{t_first}",
                       f"Motif_Paired_Diff_{temps[-1]}-{t_first}"))
        order.append((f"motif_pf_diff_{temps[-1]}_{t_first}",
                       f"Motif_PF_Diff_{temps[-1]}-{t_first}"))
    if len(temps) >= 3:
        order.append((f"motif_paired_diff_{temps[-2]}_{t_first}",
                       f"Motif_Paired_Diff_{temps[-2]}-{t_first}"))
        order.append((f"motif_pf_diff_{temps[-2]}_{t_first}",
                       f"Motif_PF_Diff_{temps[-2]}-{t_first}"))

    # Quality scores
    order += [
        ("hp_quality_score", "HP_Quality_Score"),
        ("hp_quality_score_weighted", "HP_Quality_Score_Weighted"),
        ("hp_quality_score_class", "HP_Quality_Score_Class"),
        ("hp_quality_score_breakdown", "HP_Quality_Score_Breakdown"),
        ("fl_quality_score", "FL_Quality_Score"),
        ("fl_quality_score_weighted", "FL_Quality_Score_Weighted"),
        ("fl_quality_score_class", "FL_Quality_Score_Class"),
        ("fl_quality_score_breakdown", "FL_Quality_Score_Breakdown"),
    ]

    return order


def _generate_default_scoring_profiles(temps: List[int]) -> dict:
    """Generate default scoring profiles using the configured temperatures."""
    hp_criteria = []
    for t in temps:
        hp_criteria.append({"metric": f"mfe_{t}c_hairpin", "min": -17, "max": -2, "weight": 1, "tolerance": 0})
    hp_criteria += [
        {"metric": "hairpin_au_percent", "min": 50, "max": 60, "weight": 1, "tolerance": 0},
        {"metric": "hairpin_gc_percent", "min": 0, "max": 30, "weight": 1, "tolerance": 0},
        {"metric": "hairpin_gu_percent", "min": 15, "max": 25, "weight": 1, "tolerance": 0},
    ]

    fl_criteria = []
    for t in temps:
        fl_criteria.append({"metric": f"original_mfe_{t}", "min": -17, "max": -2, "weight": 1, "tolerance": 0})
    fl_criteria += [
        {"metric": "original_au_percent", "min": 50, "max": 60, "weight": 1, "tolerance": 0},
        {"metric": "original_gc_percent", "min": 0, "max": 30, "weight": 1, "tolerance": 0},
        {"metric": "original_gu_percent", "min": 15, "max": 25, "weight": 1, "tolerance": 0},
    ]

    tiers = [
        {"label": "Tier 1", "min_pct": 83, "description": "Best candidates"},
        {"label": "Tier 2", "min_pct": 67, "description": "Good candidates"},
        {"label": "Tier 3", "min_pct": 50, "description": "Moderate"},
        {"label": "Tier 4", "min_pct": 33, "description": "Weak"},
        {"label": "Tier 5", "min_pct": 0, "description": "Poor"},
    ]

    return {
        "scoring_profiles": {
            "active_profile": "default_hairpin",
            "profiles": {
                "default_hairpin": {
                    "name": "Default Hairpin (Classic 0-6)",
                    "criteria": hp_criteria,
                    "tiers": copy.deepcopy(tiers),
                }
            }
        },
        "scoring_profiles_full": {
            "active_profile": "default_full_length",
            "profiles": {
                "default_full_length": {
                    "name": "Default Full-Length (Classic 0-6)",
                    "criteria": fl_criteria,
                    "tiers": copy.deepcopy(tiers),
                }
            }
        }
    }


class SettingsManager:
    """Manages application settings with JSON persistence"""

    def __init__(self, settings_file: str = "csv_output_settings.json"):
        self._lock = threading.Lock()
        sf = Path(settings_file)
        if sf.is_absolute():
            self.settings_file = sf
        else:
            # Store settings in the user data dir so they persist outside
            # the (possibly read-only) application bundle.
            self.settings_file = get_user_data_dir() / sf.name
        self.default_settings = self._get_default_settings()
        self.settings = self.load_settings()

    # ------------------------------------------------------------------
    # Temperature accessors
    # ------------------------------------------------------------------

    def get_temperatures(self) -> List[int]:
        """Return the configured folding temperatures list."""
        with self._lock:
            return list(self.settings.get("folding_temperatures", DEFAULT_TEMPERATURES))

    def set_temperatures(self, temps: List[int]):
        """Set custom folding temperatures (1-5 values).

        Sorts and deduplicates the list, regenerates temperature-dependent
        column keys, and saves to disk.
        """
        temps = sorted(set(int(t) for t in temps))
        if not (1 <= len(temps) <= 5):
            raise ValueError("Must provide 1-5 unique temperatures")
        with self._lock:
            self.settings["folding_temperatures"] = temps
            # Ensure csv_output_columns has all keys for the new temperatures
            new_cols = _generate_temp_columns(temps)
            existing = self.settings.get("csv_output_columns", {})
            for k, default_val in new_cols.items():
                if k not in existing:
                    existing[k] = default_val
            self.settings["csv_output_columns"] = existing
        self.save_settings()

    # ------------------------------------------------------------------

    def _get_default_settings(self) -> Dict[str, Any]:
        """Define default settings structure - matched to your data"""
        temps = DEFAULT_TEMPERATURES
        profiles = _generate_default_scoring_profiles(temps)

        return {
            "folding_temperatures": list(temps),

            "csv_output_columns": _generate_temp_columns(temps),

            "calculation_settings": {
                # Control which expensive calculations to perform
                "calculate_original_mfe_temps": False,  # MFE at configured temps for original sequence
                "calculate_original_composition": False,  # AU/GC/GU% for original sequence
                "calculate_original_range_checks": False,
                "calculate_hairpin_composition": True,  # Always calculate (needed for quality)
                "calculate_hairpin_mfe_temps": True,  # Always calculate (needed for quality)
                "calculate_rbs": True,  # RBS detection
                "calculate_rbs_full_length": False,  # RBS sequestering in full-length structures

                # Motif / Sequence Finder
                "motif_search_enabled": False,  # Enable custom motif search
                "motif_pattern": "",            # IUPAC pattern (e.g. "AGGAGG", "NNUANN")

                # Hairpin detection method:
                #   "terminal"    = old method (rightmost stem-loop + trailing tail)
                #   "rbs_based"   = new method (find RBS-containing hairpin, AUG fallback, window-cut)
                "hairpin_detection_method": "terminal",
            },
            "sequence_processing": {
                "append_sequence_enabled": False,
                "append_sequence": "AUG",
                "append_position": "end"  # "start" or "end"
            },

            "rbs_detection": {
                "anchor_pattern": "AUG",
                "anchor_match_side": "last",
                "min_spacing": 5,
                "max_spacing": 13,
            },

            "output_preferences": {
                "default_output_dir": "Data/Outputs",
                "create_structures_subdir": True,
                "auto_open_csv": False
            },

            "custom_presets": {},

            "performance_settings": {
                "num_cpu_cores": 1,  # default 1 (sequential); user can increase for parallel
            },

            **profiles,
        }

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON file or create with defaults"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure new settings are added
                    return self._merge_settings(self.default_settings, loaded)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading settings: {e}. Using defaults.")
                return copy.deepcopy(self.default_settings)
        else:
            # Create settings file with defaults
            self.save_settings(self.default_settings)
            return copy.deepcopy(self.default_settings)

    def _merge_settings(self, defaults: Dict, loaded: Dict) -> Dict:
        """Merge loaded settings with defaults to add new options.

        Also reconciles temperature-dependent column keys: if the loaded
        settings have a ``folding_temperatures`` list, ensure all
        required column keys exist (with ``False`` defaults for new ones).
        """
        merged = copy.deepcopy(defaults)
        for key in merged:
            if key in loaded:
                if isinstance(merged[key], dict) and isinstance(loaded[key], dict):
                    merged[key] = self._merge_settings(merged[key], loaded[key])
                else:
                    merged[key] = loaded[key]

        # Also preserve any loaded keys that aren't in defaults (e.g. old temp columns)
        for key in loaded:
            if key not in merged:
                merged[key] = copy.deepcopy(loaded[key])

        # Reconcile temperature columns after merge
        if "folding_temperatures" in merged:
            temps = merged["folding_temperatures"]
            expected = _generate_temp_columns(temps)
            cols = merged.get("csv_output_columns", {})
            for k, default_val in expected.items():
                if k not in cols:
                    cols[k] = default_val
            merged["csv_output_columns"] = cols

        return merged

    def save_settings(self, settings: Dict[str, Any] = None):
        """Save settings to JSON file"""
        with self._lock:
            if settings is None:
                settings = copy.deepcopy(self.settings)
            else:
                settings = copy.deepcopy(settings)

        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            return True
        except (IOError, TypeError, ValueError) as e:
            print(f"Error saving settings: {e}")
            return False

    def get_enabled_columns(self) -> list:
        """Get list of enabled column display names in order."""
        with self._lock:
            columns = []
            col_map = self.settings["csv_output_columns"]
            temps = list(self.settings.get("folding_temperatures", DEFAULT_TEMPERATURES))
            column_order = _generate_column_order(temps)

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
        self.settings = copy.deepcopy(self.default_settings)
        self.save_settings()
        return True

    def save_custom_preset(self, name: str, column_config: dict) -> bool:
        """Save a named custom preset. Returns True on success."""
        self.settings.setdefault("custom_presets", {})
        self.settings["custom_presets"][name] = column_config.copy()
        return self.save_settings()

    def delete_custom_preset(self, name: str) -> bool:
        """Delete a named custom preset. Returns True on success."""
        presets = self.settings.get("custom_presets", {})
        if name in presets:
            del presets[name]
            return self.save_settings()
        return False

    def get_custom_presets(self) -> dict:
        """Return dict of all custom presets: { name: {col: bool, ...}, ... }"""
        return self.settings.get("custom_presets", {})

    # ------------------------------------------------------------------
    # Scoring Profile Management
    # ------------------------------------------------------------------

    def get_active_scoring_profile(self) -> dict:
        """Return the currently active scoring profile dict."""
        profiles_section = self.settings.get("scoring_profiles", {})
        active_name = profiles_section.get("active_profile", "default_hairpin")
        return profiles_section.get("profiles", {}).get(active_name, {})

    def get_active_profile_name(self) -> str:
        """Return the name key of the currently active scoring profile."""
        return self.settings.get("scoring_profiles", {}).get(
            "active_profile", "default_hairpin"
        )

    def set_active_scoring_profile(self, profile_key: str):
        """Set which scoring profile is active."""
        self.settings.setdefault("scoring_profiles", {})["active_profile"] = profile_key
        self.save_settings()

    def save_scoring_profile(self, key: str, profile_data: dict) -> bool:
        """Save a scoring profile under the given key."""
        profiles = (
            self.settings
            .setdefault("scoring_profiles", {})
            .setdefault("profiles", {})
        )
        profiles[key] = profile_data
        return self.save_settings()

    def delete_scoring_profile(self, key: str) -> bool:
        """Delete a scoring profile. Cannot delete default_hairpin."""
        if key == "default_hairpin":
            return False
        profiles = self.settings.get("scoring_profiles", {}).get("profiles", {})
        if key in profiles:
            del profiles[key]
            # If we just deleted the active profile, fall back to default
            if self.settings["scoring_profiles"].get("active_profile") == key:
                self.settings["scoring_profiles"]["active_profile"] = "default_hairpin"
            return self.save_settings()
        return False

    def get_all_scoring_profiles(self) -> dict:
        """Return all scoring profiles: {key: profile_dict, ...}."""
        return self.settings.get("scoring_profiles", {}).get("profiles", {})

    # ------------------------------------------------------------------
    # Full-Length Scoring Profile Management
    # ------------------------------------------------------------------

    def get_active_full_scoring_profile(self) -> dict:
        """Return the currently active full-length scoring profile dict."""
        section = self.settings.get("scoring_profiles_full", {})
        active_name = section.get("active_profile", "default_full_length")
        return section.get("profiles", {}).get(active_name, {})

    def get_active_full_profile_name(self) -> str:
        """Return the name key of the currently active full-length scoring profile."""
        return self.settings.get("scoring_profiles_full", {}).get(
            "active_profile", "default_full_length"
        )

    def set_active_full_scoring_profile(self, profile_key: str):
        """Set which full-length scoring profile is active."""
        self.settings.setdefault("scoring_profiles_full", {})["active_profile"] = profile_key
        self.save_settings()

    def save_full_scoring_profile(self, key: str, profile_data: dict) -> bool:
        """Save a full-length scoring profile under the given key."""
        profiles = (
            self.settings
            .setdefault("scoring_profiles_full", {})
            .setdefault("profiles", {})
        )
        profiles[key] = profile_data
        return self.save_settings()

    def delete_full_scoring_profile(self, key: str) -> bool:
        """Delete a full-length scoring profile. Cannot delete default."""
        if key == "default_full_length":
            return False
        profiles = self.settings.get("scoring_profiles_full", {}).get("profiles", {})
        if key in profiles:
            del profiles[key]
            if self.settings["scoring_profiles_full"].get("active_profile") == key:
                self.settings["scoring_profiles_full"]["active_profile"] = "default_full_length"
            return self.save_settings()
        return False

    def get_all_full_scoring_profiles(self) -> dict:
        """Return all full-length scoring profiles: {key: profile_dict, ...}."""
        return self.settings.get("scoring_profiles_full", {}).get("profiles", {})