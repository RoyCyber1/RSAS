"""
Helper functions for RNA sequence analysis and CSV output
"""


def calculate_composition(sequence: str) -> dict:
    """
    Calculate AU, GC, and GU percentages for a given sequence
    
    Args:
        sequence: RNA sequence string (e.g., "ACGUACGU")
    
    Returns:
        dict with 'AU%', 'GC%', 'GU%' keys
    """
    sequence = sequence.upper()
    length = len(sequence)
    
    if length == 0:
        return {"AU%": 0.0, "GC%": 0.0, "GU%": 0.0}
    
    # Count bases
    a_count = sequence.count('A')
    u_count = sequence.count('U')
    g_count = sequence.count('G')
    c_count = sequence.count('C')
    
    # Calculate percentages
    au_percent = ((a_count + u_count) / length) * 100
    gc_percent = ((g_count + c_count) / length) * 100
    gu_percent = ((g_count + u_count) / length) * 100
    
    return {
        "AU%": round(au_percent, 2),
        "GC%": round(gc_percent, 2),
        "GU%": round(gu_percent, 2)
    }


def build_csv_row(result_data: dict, settings_manager) -> list:
    """
    Build a CSV row based on enabled settings

    Args:
        result_data: Dictionary containing all possible result fields
        settings_manager: SettingsManager instance with current configuration

    Returns:
        List of values in the order of enabled columns
    """
    column_settings = settings_manager.settings["csv_output_columns"]
    row = []

    # Define mapping between setting keys and YOUR data keys
    column_map = [
        ("name", "name"),
        ("original_sequence", "original_sequence"),
        ("original_structure", "original_structure"),

        # NEW: Full-length structures
        ("full_structure_37", "full_structure_37"),
        ("full_structure_42", "full_structure_42"),

        ("original_mfe_25", "original_mfe_25"),
        ("original_mfe_37", "original_mfe_37"),
        ("original_mfe_42", "original_mfe_42"),
        ("original_au_percent", "original_au_percent"),
        ("original_gc_percent", "original_gc_percent"),
        ("original_gu_percent", "original_gu_percent"),


        # ✨ NEW: Original sequence range checks
        ("original_mfe_25_in_range", "original_mfe_25_in_range"),
        ("original_mfe_37_in_range", "original_mfe_37_in_range"),
        ("original_mfe_42_in_range", "original_mfe_42_in_range"),
        ("original_au_in_range", "original_au_in_range"),
        ("original_gc_in_range", "original_gc_in_range"),
        ("original_gu_in_range", "original_gu_in_range"),

        # ✨ NEW: Full-length RBS sequestering
        ("full_rbs_25_seq", "full_rbs_25_seq"),
        ("full_rbs_25_struct", "full_rbs_25_struct"),
        ("full_rbs_25_paired", "full_rbs_25_paired"),
        ("full_rbs_37_seq", "full_rbs_37_seq"),
        ("full_rbs_37_struct", "full_rbs_37_struct"),
        ("full_rbs_37_paired", "full_rbs_37_paired"),
        ("full_rbs_42_seq", "full_rbs_42_seq"),
        ("full_rbs_42_struct", "full_rbs_42_struct"),
        ("full_rbs_42_paired", "full_rbs_42_paired"),
        ("rbs_seq_diff_42_25", "rbs_seq_diff_42_25"),
        ("rbs_seq_diff_37_25", "rbs_seq_diff_37_25"),

        ("hairpin_sequence", "hairpin_sequence"),
        ("hairpin_structure", "hairpin_structure"),
        ("hairpin_au_percent", "hairpin_au_percent"),
        ("hairpin_gc_percent", "hairpin_gc_percent"),
        ("hairpin_gu_percent", "hairpin_gu_percent"),
        ("mfe_25c_hairpin", "mfe_25c_hairpin"),
        ("mfe_37c_hairpin", "mfe_37c_hairpin"),
        ("mfe_42c_hairpin", "mfe_42c_hairpin"),
        ("mfe_25_in_range_hairpin", "mfe_25_in_range_hairpin"),
        ("mfe_37_in_range_hairpin", "mfe_37_in_range_hairpin"),
        ("mfe_42_in_range_hairpin", "mfe_42_in_range_hairpin"),
        ("au_in_range_hairpin", "au_in_range_hairpin"),
        ("gc_in_range_hairpin", "gc_in_range_hairpin"),
        ("gu_in_range_hairpin", "gu_in_range_hairpin"),


        ("rbs_sequence", "rbs_sequence"),
        ("rbs_structure", "rbs_structure"),
        ("rbs_paired_percent", "rbs_paired_percent"),
        ("quality_score_hairpin", "quality_score_hairpin"),
        ("quality_score_original", "quality_score_original")
    ]

    # Add values for enabled columns only
    for setting_key, data_key in column_map:
        if column_settings.get(setting_key, False):
            row.append(result_data.get(data_key, ""))

    return row


def format_mfe_value(mfe: float, min_val: float = -15, max_val: float = -5) -> str:
    """
    Format MFE value, showing if it's in range or returning the value
    
    Args:
        mfe: MFE value
        min_val: Minimum threshold
        max_val: Maximum threshold
    
    Returns:
        Formatted string (e.g., "-12.50" or "Not in Range")
    """
    if min_val <= -mfe <= max_val:
        return f"{mfe:.2f}"
    else:
        return "Not in Range"
