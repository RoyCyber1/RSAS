"""
Switch Finder — detect temperature-dependent structural switching around motifs.

Given a motif and its location in an RNA sequence, determines whether the motif
region transitions from base-paired (sequestered) at low temperature to
single-stranded (accessible) at high temperature — the hallmark of an RNA
thermometer or riboswitch.

Strategy:
  1. Find the motif in the full sequence (reuses motif_finder).
  2. For each hit, create a *truncated* sequence according to the selected
     fold direction:
       - "upstream"   : keep 5' of motif + motif, cut 3'.  Forces motif to
                        fold only against upstream sequence.
       - "downstream" : cut 5', keep motif + 3' of motif.  Forces motif to
                        fold only against downstream sequence.
       - "both"       : apply both truncations independently and report
                        the direction that produces the highest switch score.
  3. Fold the truncated sequence at each configured temperature (MFE + PF).
  4. Compute paired % and PF accessibility of the motif region at each temp.
  5. Report the *switch score*: paired% at T_low minus paired% at T_high.
     A large positive value indicates thermometer-like switching behaviour.
  6. Extract the *partner sequence* — the bases that pair with the motif
     at the lowest temperature, revealing the anti-motif.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import RNA
except ImportError:
    RNA = None  # type: ignore[assignment]

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

from RnaThermofinder.utils.motif_finder import (
    find_motif_occurrences,
    calc_motif_paired_percent,
)


# ---------------------------------------------------------------------------
# Classification thresholds
# ---------------------------------------------------------------------------
STRONG_THERMO_THRESHOLD = 50   # switch score % for strong thermometer
MODERATE_THERMO_THRESHOLD = 25
WEAK_THERMO_THRESHOLD = 10
RIBOSWITCH_PAIRED_MIN = 70     # min paired% at T_low for riboswitch candidate
RIBOSWITCH_SWITCH_MAX = 10     # max |switch score| for riboswitch candidate
ACCESSIBLE_PAIRED_MAX = 30     # below this, motif is not sequestered

# ---------------------------------------------------------------------------
# Low-level folding helpers (self-contained, same params as HairpinAnalysis)
# ---------------------------------------------------------------------------

def _fold_at_temp(seq: str, temp: float) -> Tuple[str, float]:
    """MFE fold with standard RSAS parameters."""
    if RNA is None:
        raise RuntimeError("ViennaRNA (RNA module) is not installed")
    md = RNA.md()
    md.temperature = float(temp)
    md.dangles = 2
    md.noLP = 1
    md.noGU = 0
    fc = RNA.fold_compound(seq, md)
    structure, mfe = fc.mfe()
    return structure, mfe


def _pf_fold_at_temp(seq: str, temp: float) -> Dict[str, Any]:
    """Partition function fold — returns unpaired probabilities per position."""
    if RNA is None:
        raise RuntimeError("ViennaRNA (RNA module) is not installed")
    if np is None:
        raise RuntimeError("numpy is required for partition function analysis")
    md = RNA.md()
    md.temperature = float(temp)
    md.dangles = 2
    md.noLP = 1
    md.noGU = 0

    fc = RNA.fold_compound(seq, md)
    mfe_struct, mfe_energy = fc.mfe()
    fc.exp_params_rescale(mfe_energy)
    _pf_struct, ensemble_energy = fc.pf()

    bpp = fc.bpp()
    n = len(seq)
    # Accumulate per-position paired probability without dense O(n²) matrix
    paired_per_pos = np.zeros(n, dtype=np.float64)
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            val = bpp[i][j]
            if val > 0:
                paired_per_pos[i - 1] += val
                paired_per_pos[j - 1] += val

    unpaired_probs = (1.0 - paired_per_pos).tolist()

    return {
        "ensemble_energy": ensemble_energy,
        "unpaired_probs": unpaired_probs,
    }


# ---------------------------------------------------------------------------
# Partner extraction — identify what the motif pairs with
# ---------------------------------------------------------------------------

def _build_pair_map(structure: str) -> Dict[int, int]:
    """Build a dict mapping each paired position to its partner (0-based)."""
    stack: List[int] = []
    pairs: Dict[int, int] = {}
    for i, ch in enumerate(structure):
        if ch == '(':
            stack.append(i)
        elif ch == ')':
            if not stack:
                continue  # unmatched ')' in sub-sliced structures
            j = stack.pop()
            pairs[j] = i
            pairs[i] = j
    return pairs


def _extract_partner(
    sequence: str,
    structure: str,
    motif_start: int,
    motif_end: int,
) -> Tuple[str, str, int, int]:
    """Identify the partner region that base-pairs with the motif.

    Returns (partner_seq, partner_struct, partner_start, partner_end).
    partner_start/end are 0-based positions within the *truncated* sequence.
    Returns empty strings and -1 if no pairing is found.
    """
    pairs = _build_pair_map(structure)
    partner_positions = set()
    for i in range(motif_start, motif_end):
        if i in pairs:
            partner_positions.add(pairs[i])

    if not partner_positions:
        return "", "", -1, -1

    p_start = min(partner_positions)
    p_end = max(partner_positions) + 1
    return sequence[p_start:p_end], structure[p_start:p_end], p_start, p_end


# ---------------------------------------------------------------------------
# Classification helper
# ---------------------------------------------------------------------------

def _classify_switch(
    mfe_score: Optional[float],
    low_pct: Optional[float],
    all_paired_pcts: Optional[List[Optional[float]]] = None,
) -> str:
    """Classify a motif hit as thermometer, riboswitch candidate, or other.

    Args:
        mfe_score: Switch score (paired% at T_low − paired% at T_high).
        low_pct: Paired percentage at the lowest temperature.
        all_paired_pcts: Paired percentages at ALL temperatures (for riboswitch check).
    """
    if mfe_score is None:
        return "N/A"

    if mfe_score >= STRONG_THERMO_THRESHOLD:
        return "Strong thermometer"
    if mfe_score >= MODERATE_THERMO_THRESHOLD:
        return "Moderate thermometer"
    if mfe_score >= WEAK_THERMO_THRESHOLD:
        return "Weak thermometer"

    # Below thermometer thresholds — check for riboswitch or accessible
    if low_pct is not None:
        # Riboswitch: stably sequestered at ALL temperatures, not just T_low
        if abs(mfe_score) < RIBOSWITCH_SWITCH_MAX:
            stably_paired = True
            if all_paired_pcts:
                for pct in all_paired_pcts:
                    if pct is None or pct < RIBOSWITCH_PAIRED_MIN:
                        stably_paired = False
                        break
            else:
                # Fallback: only T_low available
                stably_paired = low_pct >= RIBOSWITCH_PAIRED_MIN
            if stably_paired:
                return "Riboswitch candidate"

        if low_pct < ACCESSIBLE_PAIRED_MAX:
            return "Accessible (not sequestered)"

    return "No switch"


# ---------------------------------------------------------------------------
# Single-direction fold analysis
# ---------------------------------------------------------------------------

def _analyze_one_direction(
    seq: str,
    hit: Dict[str, Any],
    temps: List[int],
    direction: str,
    flank_past_motif: int,
    context_limit: int,
    use_pf: bool,
) -> Dict[str, Any]:
    """Fold analysis for a single motif hit in a single direction.

    Parameters
    ----------
    seq : str
        Full sequence (already T→U normalised).
    hit : dict
        Motif hit with 'start', 'end', 'matched_seq'.
    direction : str
        "upstream" or "downstream".
    """
    s, e = hit["start"], hit["end"]

    # flank_past_motif = extra nt to keep past the truncation boundary (cut side)
    # context_limit    = limit context on the kept side (0 = keep all)
    if direction == "upstream":
        # Keep upstream + motif, cut 3' side (with optional flank past motif)
        trunc_end = min(e + flank_past_motif, len(seq))
        trunc_start = max(s - context_limit, 0) if context_limit > 0 else 0
    else:  # downstream
        # Keep motif + downstream, cut 5' side (with optional flank before motif)
        trunc_start = max(s - flank_past_motif, 0)
        trunc_end = min(e + context_limit, len(seq)) if context_limit > 0 else len(seq)

    truncated = seq[trunc_start:trunc_end]
    motif_start_t = s - trunc_start
    motif_end_t = e - trunc_start

    entry: Dict[str, Any] = {
        "start": s,
        "end": e,
        "matched_seq": hit["matched_seq"],
        "direction": direction,
        "trunc_start": trunc_start,
        "trunc_end": trunc_end,
        "trunc_len": len(truncated),
        "trunc_seq": truncated,
    }

    # ── Fold at each temperature ────────────────────────────────────
    for temp in temps:
        try:
            struct, mfe = _fold_at_temp(truncated, temp)
            paired_pct = calc_motif_paired_percent(struct, motif_start_t, motif_end_t)
            entry[f"mfe_struct_{temp}"] = struct[motif_start_t:motif_end_t]
            entry[f"mfe_full_struct_{temp}"] = struct
            entry[f"mfe_{temp}"] = round(mfe, 2)
            entry[f"paired_pct_{temp}"] = round(paired_pct, 2)
        except Exception as exc:
            print(f"[RSAS] Switch fold error at {temp}°C ({direction}): {exc}",
                  file=sys.stderr)
            entry[f"mfe_struct_{temp}"] = None
            entry[f"mfe_full_struct_{temp}"] = None
            entry[f"mfe_{temp}"] = None
            entry[f"paired_pct_{temp}"] = None

        # Partition function
        if use_pf:
            try:
                pf = _pf_fold_at_temp(truncated, temp)
                if pf and "unpaired_probs" in pf:
                    uprobs = pf["unpaired_probs"]
                    region = uprobs[motif_start_t:motif_end_t]
                    mean_access = sum(region) / len(region) * 100.0 if region else 0.0
                    entry[f"pf_access_{temp}"] = round(mean_access, 2)
                else:
                    entry[f"pf_access_{temp}"] = None
            except Exception as exc:
                print(f"[RSAS] Switch PF error at {temp}°C ({direction}): {exc}",
                      file=sys.stderr)
                entry[f"pf_access_{temp}"] = None

    # ── Partner extraction at lowest temperature ────────────────────
    t_low = temps[0]
    low_struct = entry.get(f"mfe_full_struct_{t_low}")
    if low_struct:
        partner_seq, partner_struct, p_start, p_end = _extract_partner(
            truncated, low_struct, motif_start_t, motif_end_t
        )
        entry["partner_seq"] = partner_seq
        entry["partner_struct"] = partner_struct
        # Convert partner positions to original sequence coordinates
        if p_start >= 0:
            entry["partner_start"] = p_start + trunc_start
            entry["partner_end"] = p_end + trunc_start
        else:
            entry["partner_start"] = -1
            entry["partner_end"] = -1
    else:
        entry["partner_seq"] = ""
        entry["partner_struct"] = ""
        entry["partner_start"] = -1
        entry["partner_end"] = -1

    # ── Switch scores ───────────────────────────────────────────────
    t_low, t_high = temps[0], temps[-1]

    # Primary: T_low → T_high
    if len(temps) >= 2:
        low_pct = entry.get(f"paired_pct_{t_low}")
        high_pct = entry.get(f"paired_pct_{t_high}")
        if low_pct is not None and high_pct is not None:
            entry["switch_score_mfe"] = round(low_pct - high_pct, 2)
        else:
            entry["switch_score_mfe"] = None

        if use_pf:
            low_acc = entry.get(f"pf_access_{t_low}")
            high_acc = entry.get(f"pf_access_{t_high}")
            if low_acc is not None and high_acc is not None:
                entry["switch_score_pf"] = round(high_acc - low_acc, 2)
            else:
                entry["switch_score_pf"] = None

    # MFE energy delta (thermodynamic destabilisation)
    if len(temps) >= 2:
        mfe_low = entry.get(f"mfe_{t_low}")
        mfe_high = entry.get(f"mfe_{t_high}")
        if mfe_low is not None and mfe_high is not None:
            entry["mfe_delta"] = round(mfe_high - mfe_low, 2)
        else:
            entry["mfe_delta"] = None

    # Intermediate diffs (for 3+ temperatures)
    if len(temps) >= 3:
        for idx in range(len(temps) - 1):
            ta, tb = temps[idx], temps[idx + 1]
            pa = entry.get(f"paired_pct_{ta}")
            pb = entry.get(f"paired_pct_{tb}")
            if pa is not None and pb is not None:
                entry[f"paired_diff_{ta}_{tb}"] = round(pa - pb, 2)

    # ── Classify ────────────────────────────────────────────────────
    # Two phenomena detected:
    #   1. Thermometer: motif switches from paired→unpaired with rising temp
    #   2. Riboswitch candidate: motif stays stably sequestered across all temps
    #      (suggests ligand-dependent regulation, not temperature-dependent)
    mfe_score = entry.get("switch_score_mfe")
    low_pct = entry.get(f"paired_pct_{t_low}")
    all_pcts = [entry.get(f"paired_pct_{t}") for t in temps]

    entry["switch_class"] = _classify_switch(mfe_score, low_pct, all_pcts)

    return entry


# ---------------------------------------------------------------------------
# Core switch analysis
# ---------------------------------------------------------------------------

def analyze_switch(
    sequence: str,
    motif: str,
    temps: List[int],
    *,
    direction: str = "upstream",
    flank_past_motif: int = 0,
    context_limit: int = 0,
    use_pf: bool = True,
    allow_overlap: bool = True,
    progress_callback: Optional[object] = None,
) -> Dict[str, Any]:
    """Run switch analysis on a single sequence.

    Parameters
    ----------
    sequence : str
        Full RNA/DNA sequence (T→U normalised internally).
    motif : str
        IUPAC motif pattern.
    temps : list[int]
        Folding temperatures (sorted ascending recommended).
    direction : str
        "upstream"   — truncate 3' of motif, fold against upstream only.
        "downstream" — truncate 5' of motif, fold against downstream only.
        "both"       — try both directions, report the one with higher switch score.
    flank_past_motif : int
        Extra nt to keep past the truncation boundary (on the cut side).
    context_limit : int
        If >0, limit context on the kept side to this many nt.  0 = keep all.
    use_pf : bool
        Also compute partition function accessibility.
    allow_overlap : bool
        Allow overlapping motif matches.

    Returns
    -------
    dict with keys:
        hits          – list of per-hit result dicts
        motif_pattern – the motif searched
        sequence_len  – length of the original sequence
    """
    if len(temps) < 2:
        raise ValueError("At least two folding temperatures are required for switch analysis")
    seq = sequence.upper().replace("T", "U")
    raw_hits = find_motif_occurrences(seq, motif, allow_overlap=allow_overlap)

    results: List[Dict[str, Any]] = []
    directions = ["upstream", "downstream"] if direction == "both" else [direction]

    for hit in raw_hits:
        best_entry = None
        best_score = -999.0

        for d in directions:
            entry = _analyze_one_direction(
                seq, hit, temps, d,
                flank_past_motif=flank_past_motif,
                context_limit=context_limit,
                use_pf=use_pf,
            )
            score = entry.get("switch_score_mfe")
            if score is None:
                score = -999.0
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is not None:
            results.append(best_entry)

    # Sort by switch score descending, then by position for determinism
    results.sort(
        key=lambda h: (h.get("switch_score_mfe") if h.get("switch_score_mfe") is not None else -999, h.get("start", 0)),
        reverse=True,
    )

    return {
        "hits": results,
        "motif_pattern": motif,
        "sequence_len": len(seq),
    }


def analyze_switch_batch(
    sequences: List[Dict[str, str]],
    motif: str,
    temps: List[int],
    *,
    direction: str = "upstream",
    flank_past_motif: int = 0,
    context_limit: int = 0,
    use_pf: bool = True,
    progress_callback: Optional[object] = None,
) -> List[Dict[str, Any]]:
    """Run switch analysis on multiple sequences.

    Parameters
    ----------
    sequences : list of dict
        Each dict must have 'name' and 'sequence' keys.
    motif, temps, direction, flank_past_motif, context_limit, use_pf :
        Passed through to analyze_switch.
    progress_callback : callable(int, int) or None
        Called with (current_index, total) for progress updates.

    Returns
    -------
    List of dicts, one per sequence, with 'name' and the analyze_switch result.
    """
    all_results: List[Dict[str, Any]] = []
    total = len(sequences)

    for i, seq_info in enumerate(sequences):
        name = seq_info.get("name", f"seq_{i}")
        seq = seq_info.get("sequence", "")

        result = analyze_switch(
            seq, motif, temps,
            direction=direction,
            flank_past_motif=flank_past_motif,
            context_limit=context_limit,
            use_pf=use_pf,
        )
        result["name"] = name
        all_results.append(result)

        if progress_callback is not None:
            try:
                progress_callback(i + 1, total)
            except Exception:
                pass

    return all_results
