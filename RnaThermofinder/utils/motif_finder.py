"""
Motif / Sequence Finder with Sequestering Analysis.

Searches for user-defined motifs (IUPAC patterns) in RNA sequences and
quantifies how sequestered they are at each folding temperature.
Supports both MFE (dot-bracket) and partition-function accessibility.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Any

_IUPAC_RNA = {
    "A": "A", "C": "C", "G": "G", "U": "U",
    "R": "[AG]", "Y": "[CU]", "S": "[GC]", "W": "[AU]",
    "K": "[GU]", "M": "[AC]", "B": "[CGU]", "D": "[AGU]",
    "H": "[ACU]", "V": "[ACG]", "N": "[ACGU]",
}


def _iupac_to_regex(pattern: str) -> str:
    """Convert IUPAC pattern to regex."""
    parts = []
    for ch in pattern.upper():
        replacement = _IUPAC_RNA.get(ch)
        if replacement is None:
            raise ValueError(f"Invalid IUPAC character: '{ch}'")
        parts.append(replacement)
    return "".join(parts)


def find_motif_occurrences(
    sequence: str,
    motif: str,
    *,
    allow_overlap: bool = True,
) -> List[Dict[str, Any]]:
    """Find all occurrences of motif in sequence (IUPAC-aware).

    Returns list of dicts with start, end (0-based half-open), matched_seq.
    """
    seq_upper = sequence.upper().replace("T", "U")
    regex = _iupac_to_regex(motif)
    compiled = re.compile(regex)

    hits: List[Dict[str, Any]] = []
    pos = 0
    while pos < len(seq_upper):
        m = compiled.search(seq_upper, pos)
        if m is None:
            break
        hits.append({
            "start": m.start(),
            "end": m.end(),
            "matched_seq": seq_upper[m.start():m.end()],
        })
        pos = m.start() + 1 if allow_overlap else m.end()
    return hits


def calc_motif_paired_percent(structure: str, start: int, end: int) -> float:
    """% of positions in structure[start:end] that are paired (parens vs dots)."""
    region = structure[start:end]
    if not region:
        return 0.0
    paired = sum(1 for ch in region if ch in "()")
    return paired / len(region) * 100.0


def calc_motif_dot_struct(structure: str, start: int, end: int) -> str:
    """Extract dot-bracket substring for the motif region."""
    return structure[start:end]



def calc_motif_pf_accessibility(
    unpaired_probs: List[float],
    start: int,
    end: int,
) -> Optional[float]:
    """Mean unpaired probability (0-100%) for positions [start, end).
    Returns None if data unavailable."""
    if not unpaired_probs or start >= end:
        return None
    region = unpaired_probs[start:end]
    if not region:
        return None
    return sum(region) / len(region) * 100.0



def analyze_motif_sequestering(
    sequence: str,
    motif: str,
    structures: Dict[int, str],
    temps: List[int],
    *,
    pf_results: Optional[Dict[int, dict]] = None,
    pf_window_info: Optional[dict] = None,
    allow_overlap: bool = True,
) -> Dict[str, Any]:
    """Full motif search + sequestering analysis on one sequence.

    Returns dict with motif_hits (per-occurrence detail), motif_count,
    motif_pattern, best_hit, and summary (flat keys for CSV injection).
    """
    hits = find_motif_occurrences(sequence, motif, allow_overlap=allow_overlap)

    base_temp = temps[0] if temps else 25
    t_first = temps[0] if temps else 25

    pf_offset = 0
    if pf_window_info and pf_window_info.get("windowed"):
        pf_offset = pf_window_info.get("offset", 0)

    detailed_hits: List[Dict[str, Any]] = []

    for hit in hits:
        s, e = hit["start"], hit["end"]
        entry: Dict[str, Any] = {
            "start": s,
            "end": e,
            "matched_seq": hit["matched_seq"],
        }

        for t in temps:
            struct = structures.get(t, "")
            if struct and len(struct) == len(sequence):
                entry[f"mfe_paired_pct_{t}"] = calc_motif_paired_percent(struct, s, e)
                entry[f"mfe_struct_{t}"] = calc_motif_dot_struct(struct, s, e)
            else:
                entry[f"mfe_paired_pct_{t}"] = None
                entry[f"mfe_struct_{t}"] = None

        if pf_results:
            for t in temps:
                pf = pf_results.get(t)
                if pf and "unpaired_probs" in pf:
                    pf_start = s - pf_offset
                    pf_end = e - pf_offset
                    if pf_start >= 0 and pf_end <= len(pf["unpaired_probs"]):
                        entry[f"pf_access_pct_{t}"] = calc_motif_pf_accessibility(
                            pf["unpaired_probs"], pf_start, pf_end
                        )
                    else:
                        entry[f"pf_access_pct_{t}"] = None
                else:
                    entry[f"pf_access_pct_{t}"] = None

        # Temp diffs
        base_pct = entry.get(f"mfe_paired_pct_{t_first}")
        if base_pct is not None and len(temps) >= 2:
            last_pct = entry.get(f"mfe_paired_pct_{temps[-1]}")
            if last_pct is not None:
                entry[f"mfe_paired_diff_{temps[-1]}_{t_first}"] = last_pct - base_pct
        if base_pct is not None and len(temps) >= 3:
            penult_pct = entry.get(f"mfe_paired_pct_{temps[-2]}")
            if penult_pct is not None:
                entry[f"mfe_paired_diff_{temps[-2]}_{t_first}"] = penult_pct - base_pct

        if pf_results:
            base_acc = entry.get(f"pf_access_pct_{t_first}")
            if base_acc is not None and len(temps) >= 2:
                last_acc = entry.get(f"pf_access_pct_{temps[-1]}")
                if last_acc is not None:
                    entry[f"pf_access_diff_{temps[-1]}_{t_first}"] = last_acc - base_acc
            if base_acc is not None and len(temps) >= 3:
                penult_acc = entry.get(f"pf_access_pct_{temps[-2]}")
                if penult_acc is not None:
                    entry[f"pf_access_diff_{temps[-2]}_{t_first}"] = penult_acc - base_acc

        detailed_hits.append(entry)

    best_hit = None
    if detailed_hits:
        best_hit = max(
            detailed_hits,
            key=lambda h: h.get(f"mfe_paired_pct_{base_temp}", 0) or 0,
        )

    summary = _build_summary(detailed_hits, temps, motif, pf_results is not None)
    summary["_motif_hits"] = detailed_hits

    return {
        "motif_hits": detailed_hits,
        "motif_count": len(detailed_hits),
        "motif_pattern": motif,
        "best_hit": best_hit,
        "summary": summary,
    }


def _build_summary(
    hits: List[Dict[str, Any]],
    temps: List[int],
    motif: str,
    has_pf: bool,
) -> Dict[str, Any]:
    """Flat summary dict for CSV/Excel. Multi-match fields are semicolon-joined."""
    t_first = temps[0] if temps else 25
    s: Dict[str, Any] = {
        "motif_pattern": motif,
        "motif_count": len(hits),
    }

    if not hits:
        s["motif_match_seq"] = "Not Found"
        s["motif_match_pos"] = "N/A"
        for t in temps:
            s[f"motif_paired_pct_{t}"] = "N/A"
            s[f"motif_struct_{t}"] = "N/A"
            if has_pf:
                s[f"motif_pf_access_{t}"] = "N/A"
        if len(temps) >= 2:
            s[f"motif_paired_diff_{temps[-1]}_{t_first}"] = "N/A"
            if has_pf:
                s[f"motif_pf_diff_{temps[-1]}_{t_first}"] = "N/A"
        if len(temps) >= 3:
            s[f"motif_paired_diff_{temps[-2]}_{t_first}"] = "N/A"
            if has_pf:
                s[f"motif_pf_diff_{temps[-2]}_{t_first}"] = "N/A"
        return s

    s["motif_match_seq"] = ";".join(h["matched_seq"] for h in hits)
    s["motif_match_pos"] = ";".join(f"{h['start']}-{h['end']}" for h in hits)

    for t in temps:
        # Paired %
        vals = []
        for h in hits:
            pct = h.get(f"mfe_paired_pct_{t}")
            vals.append(f"{pct:.2f}" if pct is not None else "N/A")
        s[f"motif_paired_pct_{t}"] = ";".join(vals)

        # Structure
        structs = []
        for h in hits:
            st = h.get(f"mfe_struct_{t}")
            structs.append(st if st else "N/A")
        s[f"motif_struct_{t}"] = ";".join(structs)

        # PF accessibility
        if has_pf:
            accs = []
            for h in hits:
                acc = h.get(f"pf_access_pct_{t}")
                accs.append(f"{acc:.2f}" if acc is not None else "N/A")
            s[f"motif_pf_access_{t}"] = ";".join(accs)

    # Diffs
    if len(temps) >= 2:
        dvals = []
        for h in hits:
            d = h.get(f"mfe_paired_diff_{temps[-1]}_{t_first}")
            dvals.append(f"{d:+.2f}" if d is not None else "N/A")
        s[f"motif_paired_diff_{temps[-1]}_{t_first}"] = ";".join(dvals)
        if has_pf:
            dvals2 = []
            for h in hits:
                d2 = h.get(f"pf_access_diff_{temps[-1]}_{t_first}")
                dvals2.append(f"{d2:+.2f}" if d2 is not None else "N/A")
            s[f"motif_pf_diff_{temps[-1]}_{t_first}"] = ";".join(dvals2)
    if len(temps) >= 3:
        dvals = []
        for h in hits:
            d = h.get(f"mfe_paired_diff_{temps[-2]}_{t_first}")
            dvals.append(f"{d:+.2f}" if d is not None else "N/A")
        s[f"motif_paired_diff_{temps[-2]}_{t_first}"] = ";".join(dvals)
        if has_pf:
            dvals2 = []
            for h in hits:
                d2 = h.get(f"pf_access_diff_{temps[-2]}_{t_first}")
                dvals2.append(f"{d2:+.2f}" if d2 is not None else "N/A")
            s[f"motif_pf_diff_{temps[-2]}_{t_first}"] = ";".join(dvals2)

    return s
