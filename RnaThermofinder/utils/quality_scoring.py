"""
RSAS Quality Scoring Engine

Customizable quality score system where scientists define scoring criteria,
assign weights, set tolerance zones for partial credit, and save/load profiles.

Supports dynamic folding temperatures (1-5 configurable values).
"""

import copy
from typing import List, Optional


# Default temperatures (imported from settings_manager for consistency)

_DEFAULT_TEMPS = [25, 37, 42]


# Metric Registry Factories

def build_hairpin_metrics(temps: Optional[List[int]] = None) -> dict:
    """Build the hairpin-level metric registry for the given temperatures."""
    if temps is None:
        temps = _DEFAULT_TEMPS
    metrics = {}

    # Temperature-dependent MFE metrics
    for t in temps:
        metrics[f"mfe_{t}c_hairpin"] = {
            "label": f"Hairpin MFE at {t}\u00b0C",
            "short": f"HP_MFE{t}",
            "unit": "kcal/mol",
            "data_key": f"mfe_{t}c_hairpin",
            "requires_pf": False,
        }

    # Non-temperature composition metrics
    metrics["hairpin_au_percent"] = {
        "label": "Hairpin AU%",
        "short": "HP_AU",
        "unit": "%",
        "data_key": "hairpin_au_percent",
        "requires_pf": False,
    }
    metrics["hairpin_gc_percent"] = {
        "label": "Hairpin GC%",
        "short": "HP_GC",
        "unit": "%",
        "data_key": "hairpin_gc_percent",
        "requires_pf": False,
    }
    metrics["hairpin_gu_percent"] = {
        "label": "Hairpin GU%",
        "short": "HP_GU",
        "unit": "%",
        "data_key": "hairpin_gu_percent",
        "requires_pf": False,
    }

    # Temperature-dependent PF ensemble metrics
    for t in temps:
        metrics[f"pf_hp_ensemble_{t}"] = {
            "label": f"PF Ensemble (HP) {t}\u00b0C",
            "short": f"HP_PF{t}",
            "unit": "kcal/mol",
            "data_key": f"pf_hp_ensemble_{t}",
            "requires_pf": True,
        }

    # RBS (not temperature-dependent)
    metrics["rbs_paired_percent"] = {
        "label": "RBS Sequestered %",
        "short": "RBS_Seq",
        "unit": "%",
        "data_key": "rbs_paired_percent",
        "requires_pf": False,
    }

    return metrics


def build_full_metrics(temps: Optional[List[int]] = None) -> dict:
    """Build the full-length metric registry for the given temperatures."""
    if temps is None:
        temps = _DEFAULT_TEMPS
    metrics = {}

    # Temperature-dependent MFE metrics
    for t in temps:
        metrics[f"original_mfe_{t}"] = {
            "label": f"Full-Length MFE at {t}\u00b0C",
            "short": f"FL_MFE{t}",
            "unit": "kcal/mol",
            "data_key": f"original_mfe_{t}",
            "requires_pf": False,
        }

    # Non-temperature composition metrics
    metrics["original_au_percent"] = {
        "label": "Full-Length AU%",
        "short": "FL_AU",
        "unit": "%",
        "data_key": "original_au_percent",
        "requires_pf": False,
    }
    metrics["original_gc_percent"] = {
        "label": "Full-Length GC%",
        "short": "FL_GC",
        "unit": "%",
        "data_key": "original_gc_percent",
        "requires_pf": False,
    }
    metrics["original_gu_percent"] = {
        "label": "Full-Length GU%",
        "short": "FL_GU",
        "unit": "%",
        "data_key": "original_gu_percent",
        "requires_pf": False,
    }

    # Temperature-dependent PF ensemble metrics
    for t in temps:
        metrics[f"pf_full_ensemble_{t}"] = {
            "label": f"PF Ensemble (Full) {t}\u00b0C",
            "short": f"FL_PF{t}",
            "unit": "kcal/mol",
            "data_key": f"pf_full_ensemble_{t}",
            "requires_pf": True,
        }

    return metrics


def build_metric_range_keys(temps: Optional[List[int]] = None) -> dict:
    """Build the metric-to-range-key mapping for the given temperatures.

    Returns a dict mapping metric_id -> (min_key, max_key) for use by
    extract_ranges_from_profile().
    """
    if temps is None:
        temps = _DEFAULT_TEMPS
    mapping = {}

    # Hairpin MFE
    for t in temps:
        mapping[f"mfe_{t}c_hairpin"] = (f"mfe_{t}_min", f"mfe_{t}_max")

    # Hairpin composition (not temperature-dependent)
    mapping["hairpin_au_percent"] = ("au_min", "au_max")
    mapping["hairpin_gc_percent"] = ("gc_min", "gc_max")
    mapping["hairpin_gu_percent"] = ("gu_min", "gu_max")

    # Hairpin PF ensemble
    for t in temps:
        mapping[f"pf_hp_ensemble_{t}"] = (f"pf_ensemble_{t}_min", f"pf_ensemble_{t}_max")

    # RBS
    mapping["rbs_paired_percent"] = ("rbs_paired_min", "rbs_paired_max")

    # Full-length MFE
    for t in temps:
        mapping[f"original_mfe_{t}"] = (f"orig_mfe_{t}_min", f"orig_mfe_{t}_max")

    # Full-length composition (not temperature-dependent)
    mapping["original_au_percent"] = ("orig_au_min", "orig_au_max")
    mapping["original_gc_percent"] = ("orig_gc_min", "orig_gc_max")
    mapping["original_gu_percent"] = ("orig_gu_min", "orig_gu_max")

    # Full-length PF ensemble
    for t in temps:
        mapping[f"pf_full_ensemble_{t}"] = (f"pf_full_{t}_min", f"pf_full_{t}_max")

    return mapping



# Module-level registries — initialized with default temps for backward compat

AVAILABLE_METRICS_HAIRPIN = build_hairpin_metrics(_DEFAULT_TEMPS)
AVAILABLE_METRICS_FULL = build_full_metrics(_DEFAULT_TEMPS)

# Backward compatibility: combined registry (hairpin metrics)
AVAILABLE_METRICS = AVAILABLE_METRICS_HAIRPIN

# Default range key mapping
_METRIC_TO_RANGE_KEYS = build_metric_range_keys(_DEFAULT_TEMPS)



# Default Tier Thresholds (percentage-based classification)
# Grounded in legacy 0-6 system: 6/6=100%, 5/6≈83%, 4/6≈67%, 3/6=50%, 2/6≈33%


_DEFAULT_TIERS = [
    {"label": "Tier 1", "min_pct": 83, "description": "Best candidates"},
    {"label": "Tier 2", "min_pct": 67, "description": "Good candidates"},
    {"label": "Tier 3", "min_pct": 50, "description": "Moderate"},
    {"label": "Tier 4", "min_pct": 33, "description": "Weak"},
    {"label": "Tier 5", "min_pct": 0,  "description": "Poor"},
]

def get_default_tiers():
    """Return a deep copy of the default tier thresholds."""
    return copy.deepcopy(_DEFAULT_TIERS)


# ---------------------------------------------------------------------------
# Default Profile
# ---------------------------------------------------------------------------

def get_default_hairpin_profile(temps: Optional[List[int]] = None):
    """Return a deep copy of the built-in default hairpin scoring profile.

    If *temps* is given, generates criteria for those temperatures.
    Otherwise uses the default [25, 37, 42].
    """
    if temps is None:
        temps = _DEFAULT_TEMPS
    criteria = []
    for t in temps:
        criteria.append({"metric": f"mfe_{t}c_hairpin", "min": -17, "max": -2, "weight": 1, "tolerance": 0})
    criteria += [
        {"metric": "hairpin_au_percent", "min": 50, "max": 60, "weight": 1, "tolerance": 0},
        {"metric": "hairpin_gc_percent", "min": 0,  "max": 30, "weight": 1, "tolerance": 0},
        {"metric": "hairpin_gu_percent", "min": 15, "max": 25, "weight": 1, "tolerance": 0},
    ]
    return {
        "name": "Default Hairpin (Classic 0-6)",
        "criteria": criteria,
        "tiers": copy.deepcopy(_DEFAULT_TIERS),
    }


def get_default_full_length_profile(temps: Optional[List[int]] = None):
    """Return a deep copy of the built-in default full-length scoring profile.

    If *temps* is given, generates criteria for those temperatures.
    Otherwise uses the default [25, 37, 42].
    """
    if temps is None:
        temps = _DEFAULT_TEMPS
    criteria = []
    for t in temps:
        criteria.append({"metric": f"original_mfe_{t}", "min": -17, "max": -2, "weight": 1, "tolerance": 0})
    criteria += [
        {"metric": "original_au_percent", "min": 50, "max": 60, "weight": 1, "tolerance": 0},
        {"metric": "original_gc_percent", "min": 0,  "max": 30, "weight": 1, "tolerance": 0},
        {"metric": "original_gu_percent", "min": 15, "max": 25, "weight": 1, "tolerance": 0},
    ]
    return {
        "name": "Default Full-Length (Classic 0-6)",
        "criteria": criteria,
        "tiers": copy.deepcopy(_DEFAULT_TIERS),
    }


# ---------------------------------------------------------------------------
# Core Scoring Functions
# ---------------------------------------------------------------------------

def compute_criterion_score(value, min_val, max_val, tolerance):
    """Score a single criterion value against its range.

    Returns:
        float: 1.0 if in range, linear falloff within tolerance, 0.0 outside.
        None:  if the value is unavailable (N/A, None, unparseable).
    """
    if value is None or str(value).strip().upper() in ("N/A", "NONE", ""):
        return None

    try:
        v = float(str(value).strip("()"))
    except (ValueError, TypeError):
        return None

    if min_val <= v <= max_val:
        return 1.0

    if tolerance > 0:
        if v < min_val:
            dist = min_val - v
            if dist <= tolerance:
                return 1.0 - (dist / tolerance)
        elif v > max_val:
            dist = v - max_val
            if dist <= tolerance:
                return 1.0 - (dist / tolerance)

    return 0.0


def _classify_tier(pct, tiers):
    """Classify a percentage score into a tier label.

    Tiers are checked in order (highest min_pct first).
    Each tier dict: {"label": "Tier 1", "min_pct": 83, "description": "..."}
    """
    if not tiers:
        return "N/A"
    # Sort descending by min_pct so we match the highest tier first
    sorted_tiers = sorted(tiers, key=lambda t: t.get("min_pct", 0), reverse=True)
    for tier in sorted_tiers:
        if pct >= tier.get("min_pct", 0):
            return tier["label"]
    return sorted_tiers[-1]["label"]  # Lowest tier as fallback


def compute_quality_score(result_data, profile_dict, pf_available=False,
                          metrics_registry=None, key_prefix="hp_"):
    """Compute the weighted quality score for one sequence result.

    Args:
        result_data: dict with the sequence analysis results (keyed by data_key).
        profile_dict: scoring profile dict with "criteria" list.
        pf_available: whether PF computations were run this analysis.
        metrics_registry: dict of available metrics (default: AVAILABLE_METRICS_HAIRPIN).
                          Pass AVAILABLE_METRICS_FULL for full-length scoring.
        key_prefix: prefix for result dict keys (default "hp_" for hairpin,
                    use "fl_" for full-length).

    Returns:
        dict with keys:
            {prefix}quality_score         (str)    "X/Y" criteria passed out of evaluated
            {prefix}quality_score_weighted(float)  weighted percentage 0-100
            {prefix}quality_score_class   (str)    tier label (e.g. "Tier 1")
            {prefix}quality_score_breakdown(str)   semicolon-delimited per-criterion scores
    """
    if metrics_registry is None:
        metrics_registry = AVAILABLE_METRICS_HAIRPIN
    criteria = profile_dict.get("criteria", [])
    tiers = profile_dict.get("tiers") or _DEFAULT_TIERS
    if not criteria:
        return {
            f"{key_prefix}quality_score": "0/0",
            f"{key_prefix}quality_score_weighted": 0.0,
            f"{key_prefix}quality_score_class": "N/A",
            f"{key_prefix}quality_score_breakdown": "",
        }

    weighted_sum = 0.0
    weight_total = 0.0
    criteria_passed = 0
    criteria_evaluated = 0
    breakdown_parts = []

    for crit in criteria:
        metric_id = crit.get("metric", "")
        meta = metrics_registry.get(metric_id)
        if meta is None:
            continue

        # Skip PF metrics if PF was not computed
        if meta.get("requires_pf") and not pf_available:
            continue

        data_key = meta["data_key"]
        value = result_data.get(data_key)
        min_val = float(crit.get("min", 0))
        max_val = float(crit.get("max", 0))
        weight = max(1, int(crit.get("weight", 1)))
        tolerance = max(0.0, float(crit.get("tolerance", 0)))

        score = compute_criterion_score(value, min_val, max_val, tolerance)
        short_code = meta.get("short", meta["label"])
        if score is None:
            # Data not available — counts as 0 (still in denominator)
            breakdown_parts.append(f"{short_code}:N/A")
            criteria_evaluated += 1
            weight_total += weight
            continue

        criteria_evaluated += 1
        if score >= 1.0:
            criteria_passed += 1

        weighted_sum += score * weight
        weight_total += weight
        breakdown_parts.append(f"{short_code}:{score:.2f}")

    if weight_total == 0:
        return {
            f"{key_prefix}quality_score": "0/0",
            f"{key_prefix}quality_score_weighted": 0.0,
            f"{key_prefix}quality_score_class": _classify_tier(0.0, tiers),
            f"{key_prefix}quality_score_breakdown": "; ".join(breakdown_parts),
        }

    pct = (weighted_sum / weight_total) * 100.0
    return {
        f"{key_prefix}quality_score": f"{criteria_passed}/{criteria_evaluated}",
        f"{key_prefix}quality_score_weighted": round(pct, 1),
        f"{key_prefix}quality_score_class": _classify_tier(pct, tiers),
        f"{key_prefix}quality_score_breakdown": "; ".join(breakdown_parts),
    }


# ---------------------------------------------------------------------------
# Range Extraction (bridge to existing analysis_settings dict)
# ---------------------------------------------------------------------------

def extract_ranges_from_profile(profile_dict, temps=None):
    """Convert scoring profile criteria into the old-style analysis_settings range dict.

    Returns a dict like {"mfe_25_min": -17, "mfe_25_max": -10, "au_min": 50, ...}.
    Only includes ranges for metrics present in the profile AND that have a
    mapping in the range key table.  Metrics not in the profile are omitted
    (the caller should treat missing keys as "no range defined" -> N/A).
    """
    range_keys = build_metric_range_keys(temps) if temps else _METRIC_TO_RANGE_KEYS
    ranges = {}
    for crit in profile_dict.get("criteria", []):
        metric_id = crit.get("metric", "")
        if metric_id in range_keys:
            min_key, max_key = range_keys[metric_id]
            ranges[min_key] = float(crit.get("min", 0))
            ranges[max_key] = float(crit.get("max", 0))
    return ranges


# ---------------------------------------------------------------------------
# Profile Serialization Helpers
# ---------------------------------------------------------------------------

def validate_profile(profile_dict, metrics_registry=None, temps=None):
    """Validate a scoring profile dict.  Returns (ok, error_message)."""
    if metrics_registry is None:
        # Accept metrics from either registry (temperature-aware if temps given)
        all_metrics = {**build_hairpin_metrics(temps), **build_full_metrics(temps)}
    else:
        all_metrics = metrics_registry

    if not isinstance(profile_dict, dict):
        return False, "Profile must be a dictionary"

    criteria = profile_dict.get("criteria")
    if not isinstance(criteria, list):
        return False, "Profile must contain a 'criteria' list"

    for i, crit in enumerate(criteria):
        metric = crit.get("metric", "")
        if metric not in all_metrics:
            return False, f"Criterion {i+1}: unknown metric '{metric}'"

        try:
            mn = float(crit.get("min", 0))
            mx = float(crit.get("max", 0))
        except (ValueError, TypeError):
            return False, f"Criterion {i+1}: min/max must be numbers"

        if mn >= mx:
            label = all_metrics[metric]["label"]
            return False, f"Criterion {i+1} ({label}): min ({mn}) must be less than max ({mx})"

        weight = crit.get("weight", 1)
        if not isinstance(weight, (int, float)) or weight < 1 or weight > 5:
            return False, f"Criterion {i+1}: weight must be 1-5"

        tol = crit.get("tolerance", 0)
        if not isinstance(tol, (int, float)) or tol < 0:
            return False, f"Criterion {i+1}: tolerance must be >= 0"

    return True, ""
