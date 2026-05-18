from pathlib import Path
import os
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import RNA
import numpy as np
from typing import List, Tuple, Callable, Optional, Dict, Any
import csv
from multiprocessing import Pool

from RnaThermofinder.utils.analysis_helpers import calculate_composition
from RnaThermofinder.utils.analysis_helpers import build_csv_row
from RnaThermofinder.utils.quality_scoring import (
    compute_quality_score, extract_ranges_from_profile,
    AVAILABLE_METRICS_HAIRPIN, AVAILABLE_METRICS_FULL,
    build_hairpin_metrics, build_full_metrics, build_metric_range_keys,
)
from settings_manager import SettingsManager
from RnaThermofinder.core.rbs_config import RbsConfig, resolve_anchor


def get_terminal_hairpin_with_tail(sequence, structure):
    """
    Extracts the rightmost (terminal) hairpin and all trailing unpaired dots.
    Example: ((((((((((...)))))))))))..........
    """
    # Find the rightmost ')'
    last_close = structure.rfind(')')
    if last_close == -1:
        return None  # no paired region found

    # Now find its matching '(' going backward
    depth = 0
    for i in range(last_close, -1, -1):
        if structure[i] == ')':
            depth += 1
        elif structure[i] == '(':
            depth -= 1
            if depth == 0:
                start = i
                break
    else:
        return None  # no matching '(' found

    # Include all trailing unpaired dots after the hairpin
    end = last_close
    while end + 1 < len(structure) and structure[end + 1] == '.':
        end += 1

    # Slice the sequence and structure
    return {
        "start": start,
        "end": end,
        "hairpin_seq": sequence[start:end + 1],
        "hairpin_struct": structure[start:end + 1]
    }




def find_all_hairpins(sequence, fold_temp=25, min_length=15):
    """
    Find ALL hairpins by checking every opening bracket
    Returns ALL of them including overlapping subsets
    """

    # Fold the sequence
    md = RNA.md()
    md.temperature = fold_temp
    md.dangles = 2  # Default
    md.noLP = 1     # No lonely pairs
    md.noGU = 0     # Allow GU pairs (default)
    fc = RNA.fold_compound(sequence, md)
    structure, mfe = fc.mfe()

    # Find ALL hairpins by checking every opening bracket
    all_hairpins = []

    for start in range(len(structure)):
        if structure[start] == '(':
            # Extract hairpin starting here
            depth = 0

            for end in range(start, len(structure)):
                if structure[end] == '(':
                    depth += 1
                elif structure[end] == ')':
                    depth -= 1

                    if depth == 0:
                        # Found complete hairpin
                        hp_seq = sequence[start:end + 1]
                        hp_struct = structure[start:end + 1]

                        if len(hp_seq) >= min_length:
                            all_hairpins.append({
                                'sequence': hp_seq,
                                'structure': hp_struct,
                                'start': start,
                                'end': end + 1,
                                'length': len(hp_seq)
                            })
                        break

    return {
        'full_structure': structure,
        'full_mfe': mfe,
        'hairpins': all_hairpins,
        'num_hairpins': len(all_hairpins)
    }


def filter_exclude_outer(all_hairpins, structure, max_coverage=0.8):
    """
    Exclude hairpins that span too much of the sequence (outer wrappers)
    Then keep largest at each start position, non-overlapping
    """

    total_length = len(structure)

    # Filter out hairpins that cover > max_coverage of total length
    filtered = [hp for hp in all_hairpins
                if hp['length'] / total_length <= max_coverage]

    # Group by start, keep largest at each start
    by_start = {}
    for hp in filtered:
        start = hp['start']
        if start not in by_start or hp['length'] > by_start[start]['length']:
            by_start[start] = hp

    # Get non-overlapping
    unique = list(by_start.values())
    unique.sort(key=lambda x: x['start'])

    kept = []
    last_end = -1

    for hp in unique:
        if hp['start'] >= last_end:
            kept.append(hp)
            last_end = hp['end']

    return kept




def trim_trailing_unpaired(sequence, structure):
    """
    Removes nucleotides corresponding to trailing dots in RNA structure.
    """
    # Count trailing dots
    trailing_dots = len(structure) - len(structure.rstrip('.'))

    if trailing_dots == 0:
        return sequence  # nothing to trim
    else:
        return sequence[:-trailing_dots]

def find_rbs_in_hairpin(hairpin_seq, cfg=None):
    """
    Finds the Shine-Dalgarno-like sequence in a terminal hairpin.

    Args:
        hairpin_seq (str): The RNA sequence of the terminal hairpin.
        cfg (RbsConfig): Anchor + window config. Defaults to RbsConfig()
                         (last "AUG", 5-13 nt upstream window).

    Returns:
        dict: {
            'found_rbs': bool,       # True if a G-rich 6-mer found in the window
            'aug_index': int,        # Start index of the resolved anchor
            'rbs_seq': str or None,  # The 6-nt G-rich Shine-Dalgarno candidate
            'rbs_region': str        # Full upstream region scanned
        }
    """
    if cfg is None:
        cfg = RbsConfig()

    seq = hairpin_seq.upper()
    anchor_pos, _anchor_len = resolve_anchor(seq, cfg)
    if anchor_pos is None:
        return {
            "found_rbs": False,
            "aug_index": None,
            "rbs_seq": None,
            "rbs_region": None,
        }

    # Search the configured window upstream of the anchor
    search_start = max(0, anchor_pos - cfg.max_spacing)
    search_end = max(0, anchor_pos - cfg.min_spacing)
    rbs_region = seq[search_start:search_end]

    found = False
    rbs_seq = None
    for i in range(len(rbs_region) - 5):
        window = rbs_region[i:i + 6]
        if window.count("G") >= 3:
            found = True
            rbs_seq = window
            break  # Take the first valid G-rich window

    return {
        "found_rbs": found,
        "aug_index": anchor_pos,  # anchor start index; key name kept for backward compat
        "rbs_seq": rbs_seq,
        "rbs_region": rbs_region,
    }


def get_rbs_dot_struct(rbs_seq, hairpin_seq, hairpin_struct):
    """
        Extract the RBS dot structure from the hairpin dot structure.

        Args:
            rbs_seq (str): RBS sequence (e.g., "AGGAGG")
            hairpin_seq (str): Full hairpin sequence
            hairpin_struct (str): Dot-bracket structure of the hairpin

        Returns:
            str or None: Dot-bracket structure corresponding to the RBS sequence,
                         or None if RBS not found or structure length mismatch
        """
    # Handle None or empty inputs
    if not rbs_seq or not hairpin_seq or not hairpin_struct:
        return None

    # Validate that structure and sequence lengths match
    if len(hairpin_seq) != len(hairpin_struct):
        return None

    # Find the RBS sequence in the hairpin
    rbs_start = hairpin_seq.find(rbs_seq)

    if rbs_start == -1:
        return None

    # Extract the corresponding structure
    rbs_end = rbs_start + len(rbs_seq)
    rbs_struct = hairpin_struct[rbs_start:rbs_end]

    return rbs_struct

def calc_rbs_paired_percent(rbs_struct):
    """
    Calculate the percentage of paired nucleotides in the RBS structure.

    Args:
        rbs_struct (str): Dot-bracket structure of the RBS sequence
                         ('.' = unpaired, '(' or ')' = paired)

    Returns:
        float: Percentage of paired nucleotides (0-100)
    """
    if len(rbs_struct) == 0:
        return 0.0

    # Count paired positions (both '(' and ')')
    paired_count = sum(1 for char in rbs_struct if char in '()')

    # Calculate percentage
    percent_paired = (paired_count / len(rbs_struct)) * 100

    return percent_paired


def find_rbs_in_full_sequence(full_seq, full_structure, cfg=None):
    """
    Find RBS sequestering in full-length sequence at different temperatures

    Args:
        full_seq: Complete RNA sequence
        full_structure: Dot-bracket structure of full sequence
        cfg: RbsConfig (optional, uses defaults if None)

    Returns:
        dict: {
            'rbs_seq': RBS sequence found,
            'rbs_structure': Dot-bracket structure of RBS,
            'rbs_paired_percent': Percentage of RBS that is paired
        }
    """
    if cfg is None:
        cfg = RbsConfig()
    # Find RBS in the full sequence (same logic as hairpin)
    rbs_result = find_rbs_in_hairpin(full_seq, cfg)

    if not rbs_result["found_rbs"]:
        return {
            "rbs_seq": None,
            "rbs_structure": None,
            "rbs_paired_percent": None
        }

    rbs_seq = rbs_result["rbs_seq"]

    # Get RBS structure from full structure
    rbs_struct = get_rbs_dot_struct(rbs_seq, full_seq, full_structure)

    if rbs_struct is None:
        return {
            "rbs_seq": rbs_seq,
            "rbs_structure": None,
            "rbs_paired_percent": None
        }

    # Calculate paired percentage
    rbs_paired_pct = calc_rbs_paired_percent(rbs_struct)

    return {
        "rbs_seq": rbs_seq,
        "rbs_structure": rbs_struct,
        "rbs_paired_percent": rbs_paired_pct
    }


def _build_pair_map(structure):
    """
    Build a dictionary mapping each paired position to its partner.
    Internal helper used by hairpin detection functions.

    Args:
        structure: Dot-bracket structure string

    Returns:
        dict: position -> partner position for all paired bases
    """
    stack = []
    pairs = {}
    for i, c in enumerate(structure):
        if c == '(':
            stack.append(i)
        elif c == ')':
            if not stack:
                continue  # unmatched ')' in sub-sliced structures
            j = stack.pop()
            pairs[j] = i
            pairs[i] = j
    return pairs


def _extract_stemloop_around_positions(structure, pairs, paired_positions,
                                      max_local_distance=50, max_gap=20):
    """
    Given a set of paired positions, find the smallest enclosing stem-loop.
    Only considers LOCAL pairs (partner within max_local_distance).
    Expands outward through consecutive base pairs, bulges, and internal loops.

    The expansion crosses gaps of unpaired nucleotides (bulges/internal loops)
    up to max_gap nucleotides wide. This captures elongated stems with bulges
    that are part of the same thermometer structure. Expansion stops at
    multi-branch junctions or large single-stranded regions.

    Args:
        structure: Dot-bracket structure string
        pairs: Pair map from _build_pair_map()
        paired_positions: List of (pos, partner_pos) tuples
        max_local_distance: Maximum distance to consider a pair "local"
        max_gap: Maximum unpaired gap to cross during expansion (default 20)

    Returns:
        (start, end) of the stem-loop, or (None, None) if no local pairs
    """
    # Filter to local pairs only
    local_pairs = [(a, b) for a, b in paired_positions if abs(a - b) <= max_local_distance]

    if not local_pairs:
        return None, None

    # Get boundaries from local paired positions
    all_pos = []
    for a, b in local_pairs:
        all_pos.extend([a, b])
    hp_start = min(all_pos)
    hp_end = max(all_pos)

    # Expand outward, crossing bulges, internal loops, and nested branches
    # up to max_gap unpaired/branch nucleotides on each side.
    expanding = True
    while expanding and hp_start > 0 and hp_end < len(structure) - 1:
        expanding = False

        # Try direct consecutive pair first (most common case)
        if (structure[hp_start - 1] == '(' and
                structure[hp_end + 1] == ')' and
                pairs.get(hp_start - 1) == hp_end + 1):
            hp_start -= 1
            hp_end += 1
            expanding = True
            continue

        # Search leftward for the next enclosing '(' — skip dots AND small nested
        # branches that are part of an internal loop within the same stem.
        #
        # When we encounter a ')' scanning left, it's a nested branch. We skip
        # it ONLY if the branch is small (≤ max_gap nucleotides). Large branches
        # are likely sibling structures at a multi-branch junction — we stop there.
        #
        # Only unpaired nucleotides (dots) count toward the gap limit.
        next_left = None
        scan = hp_start - 1
        gap_count = 0  # count only unpaired nucleotides (dots)
        while scan >= 0 and gap_count <= max_gap:
            if structure[scan] == '.':
                gap_count += 1
                scan -= 1
            elif structure[scan] == ')':
                partner = pairs.get(scan)
                if partner is not None and partner < scan:
                    branch_size = scan - partner + 1
                    if branch_size <= max_gap:
                        # Small internal branch — skip it
                        scan = partner - 1
                    else:
                        # Large branch — likely a junction sibling, stop
                        break
                else:
                    break
            elif structure[scan] == '(':
                # Found the next outer '(' — check if its partner encloses us
                partner = pairs.get(scan)
                if partner is not None and partner > hp_end:
                    next_left = scan
                break
            else:
                break

        if next_left is not None:
            partner = pairs[next_left]
            # Check the right side — scan from hp_end+1 to the partner
            # Only count dots toward gap, skip nested branches
            right_gap = 0
            scan_r = hp_end + 1
            valid_right = False
            while scan_r <= partner:
                if scan_r == partner and structure[scan_r] == ')':
                    valid_right = True
                    break
                elif structure[scan_r] == '.':
                    right_gap += 1
                    scan_r += 1
                elif structure[scan_r] == '(':
                    # Nested branch on the right — skip only if small
                    branch_partner = pairs.get(scan_r)
                    if branch_partner is not None and branch_partner > scan_r:
                        branch_size = branch_partner - scan_r + 1
                        if branch_size <= max_gap:
                            scan_r = branch_partner + 1
                        else:
                            break  # large branch, likely junction sibling
                    else:
                        break
                elif structure[scan_r] == ')':
                    # Should only happen at the partner position
                    if scan_r == partner:
                        valid_right = True
                    break
                else:
                    break

                if right_gap > max_gap:
                    break

            if valid_right and right_gap <= max_gap:
                hp_start = next_left
                hp_end = partner
                expanding = True
                continue

    return hp_start, hp_end


def _cut_window_as_hairpin(full_seq, full_structure, target_pos, target_len,
                            window_size=80):
    """
    Window-cut heuristic: when the stem-loop extraction from the full structure
    gives a hairpin that's too large (>80 nt) or can't be found, just cut
    ~window_size nt around the target (RBS or AUG) and return that as the hairpin.

    The downstream pipeline already folds the extracted hairpin at 25/37/42°C,
    so we do NOT fold here — just cut and trim trailing dots.

    Args:
        full_seq: Complete RNA sequence
        full_structure: Full dot-bracket structure (used only for dot trimming)
        target_pos: Position of the target (RBS start or AUG start) in full_seq
        target_len: Length of target (6 for RBS, 3 for AUG)
        window_size: Size of the window to cut (default 80 nt)

    Returns:
        dict or None: If successful, returns {
            'hairpin_start': int (in full_seq coords),
            'hairpin_end': int (in full_seq coords),
            'hairpin_seq': str,
            'hairpin_length': int,
            'window_cut_used': True,
        }
        Returns None if the window is too small.
    """
    seq_len = len(full_seq)

    # Center the window on the target, biased slightly upstream
    # (thermometer hairpins are typically upstream of the RBS/AUG)
    upstream_pad = int(window_size * 0.65)  # ~52 nt upstream
    downstream_pad = window_size - upstream_pad  # ~28 nt downstream

    window_start = max(0, target_pos - upstream_pad)
    window_end = min(seq_len, target_pos + target_len + downstream_pad)

    # Ensure we have at least window_size nt if possible
    actual_window = window_end - window_start
    if actual_window < window_size and seq_len >= window_size:
        if window_start == 0:
            window_end = min(seq_len, window_size)
        elif window_end == seq_len:
            window_start = max(0, seq_len - window_size)

    # Trim leading/trailing dots from the full structure within the window
    hp_start = window_start
    hp_end = window_end - 1  # inclusive

    if len(full_structure) == len(full_seq):
        while hp_start <= hp_end and full_structure[hp_start] == '.':
            hp_start += 1
        while hp_end >= hp_start and full_structure[hp_end] == '.':
            hp_end -= 1

    hp_length = hp_end - hp_start + 1
    if hp_length < 8:
        return None

    return {
        'hairpin_start': hp_start,
        'hairpin_end': hp_end,
        'hairpin_seq': full_seq[hp_start:hp_end + 1],
        'hairpin_length': hp_length,
        'window_cut_used': True,
    }


def find_rbs_containing_hairpin(full_seq, full_structure, cfg=None):
    """
    Find the hairpin stem-loop that sequesters the RBS (Shine-Dalgarno sequence).

    Instead of finding the "terminal hairpin" and hoping the RBS is inside it,
    this function finds the RBS first, then extracts the stem-loop containing it.
    This correctly handles cases where the thermometer hairpin is nested inside
    a larger multi-branch structure.

    Algorithm:
        1. Find RBS using existing find_rbs_in_hairpin() logic
        2. Check how many RBS nucleotides are base-paired in the structure
        3. If >= 3 of 6 are paired (locally): RBS is sequestered
           → Extract the enclosing stem-loop
        4. If < 3 paired: RBS is accessible (probably not a thermometer)

    Args:
        full_seq: Complete RNA sequence
        full_structure: Dot-bracket structure of full sequence at 25°C
        cfg: RbsConfig for anchor/window. Defaults to RbsConfig() when None.

    Returns:
        dict: {
            'found': bool,              # True if a sequestering hairpin was found
            'method': str,              # 'rbs_hairpin', 'none', or 'no_rbs'
            'rbs_seq': str or None,     # The 6-nt RBS sequence
            'rbs_pos': int or None,     # Start position of RBS in full sequence
            'rbs_paired_count': int,    # How many of 6 RBS nt are paired (0-6)
            'rbs_sequestered': bool,    # True if >= 3 paired locally
            'hairpin_start': int,       # Start position of extracted hairpin
            'hairpin_end': int,         # End position of extracted hairpin
            'hairpin_seq': str,         # Sequence of extracted hairpin
            'hairpin_struct': str,      # Structure of extracted hairpin
            'hairpin_length': int,      # Length of extracted hairpin
        }
    """
    if cfg is None:
        cfg = RbsConfig()

    result = {
        'found': False,
        'method': 'none',
        'rbs_seq': None,
        'rbs_pos': None,
        'rbs_paired_count': 0,
        'rbs_sequestered': False,
        'hairpin_start': None,
        'hairpin_end': None,
        'hairpin_seq': None,
        'hairpin_struct': None,
        'hairpin_length': 0,
        'window_cut_used': False,
    }

    if not full_seq or not full_structure or len(full_seq) != len(full_structure):
        return result

    # Step 1: Find RBS
    rbs_result = find_rbs_in_hairpin(full_seq, cfg)

    if not rbs_result["found_rbs"]:
        result['method'] = 'no_rbs'
        return result

    rbs_seq = rbs_result["rbs_seq"]
    # Use the anchor position to find the correct RBS occurrence nearby
    # (find() would return the FIRST occurrence, which may be wrong)
    anchor_pos = rbs_result["aug_index"]
    search_region_start = max(0, anchor_pos - cfg.max_spacing) if anchor_pos is not None else 0
    rbs_start = full_seq.upper().find(rbs_seq.upper(), search_region_start)

    if rbs_start == -1:
        result['method'] = 'no_rbs'
        return result

    result['rbs_seq'] = rbs_seq
    result['rbs_pos'] = rbs_start

    # Step 2: Build pair map and check RBS pairing
    pairs = _build_pair_map(full_structure)

    paired_positions = []
    paired_count = 0
    for i in range(rbs_start, min(rbs_start + len(rbs_seq), len(full_structure))):
        if i in pairs:
            paired_count += 1
            paired_positions.append((i, pairs[i]))

    result['rbs_paired_count'] = paired_count

    # Step 3: Is RBS sequestered?
    if paired_count < 3:
        result['rbs_sequestered'] = False
        result['method'] = 'none'
        return result

    result['rbs_sequestered'] = True

    # Step 4: Extract the enclosing stem-loop (local pairs only)
    hp_start, hp_end = _extract_stemloop_around_positions(
        full_structure, pairs, paired_positions, max_local_distance=50
    )

    # Determine if we need to refold
    need_refold = False
    if hp_start is None:
        need_refold = True  # No hairpin found from full structure
    else:
        hp_length = hp_end - hp_start + 1
        if hp_length > 80:
            need_refold = True  # Hairpin too large — likely a multi-branch junction

    if need_refold:
        # Step 5: Refold heuristic — cut ~80 nt around RBS, refold locally
        cut_result = _cut_window_as_hairpin(
            full_seq, full_structure, target_pos=rbs_start,
            target_len=len(rbs_seq), window_size=80
        )
        if cut_result is not None:
            result['found'] = True
            result['method'] = 'rbs_hairpin_cut'
            result['hairpin_start'] = cut_result['hairpin_start']
            result['hairpin_end'] = cut_result['hairpin_end']
            result['hairpin_seq'] = cut_result['hairpin_seq']
            result['hairpin_struct'] = None  # pipeline folds downstream
            result['hairpin_length'] = cut_result['hairpin_length']
            result['window_cut_used'] = True
            return result

        # Window cut also failed
        if hp_start is None:
            result['rbs_sequestered'] = False
            result['method'] = 'none'
            return result
        # else: fall through to use the oversized hairpin from full structure

    # Trim leading/trailing dots from the full-structure hairpin
    while hp_start <= hp_end and full_structure[hp_start] == '.':
        hp_start += 1
    while hp_end >= hp_start and full_structure[hp_end] == '.':
        hp_end -= 1

    result['found'] = True
    result['method'] = 'rbs_hairpin'
    result['hairpin_start'] = hp_start
    result['hairpin_end'] = hp_end
    result['hairpin_seq'] = full_seq[hp_start:hp_end + 1]
    result['hairpin_struct'] = full_structure[hp_start:hp_end + 1]
    result['hairpin_length'] = hp_end - hp_start + 1

    return result


def find_aug_containing_hairpin(full_seq, full_structure):
    """
    Fallback: find the hairpin stem-loop that sequesters the AUG start codon.

    Used when no RBS (Shine-Dalgarno) is found. Catches fourU-type thermometers
    where UUUU base-pairs directly with the AUG, blocking ribosome binding.

    Algorithm:
        1. Find last AUG in the sequence
        2. Check if AUG nucleotides are base-paired
        3. If >= 2 of 3 are paired locally: AUG is sequestered
           → Extract the enclosing stem-loop

    Args:
        full_seq: Complete RNA sequence
        full_structure: Dot-bracket structure of full sequence at 25°C

    Returns:
        dict: Same structure as find_rbs_containing_hairpin(), but with
              method = 'aug_hairpin' when found
    """
    result = {
        'found': False,
        'method': 'none',
        'rbs_seq': None,
        'rbs_pos': None,
        'rbs_paired_count': 0,
        'rbs_sequestered': False,
        'aug_pos': None,
        'aug_paired_count': 0,
        'aug_sequestered': False,
        'hairpin_start': None,
        'hairpin_end': None,
        'hairpin_seq': None,
        'hairpin_struct': None,
        'hairpin_length': 0,
        'window_cut_used': False,
    }

    if not full_seq or not full_structure or len(full_seq) != len(full_structure):
        return result

    # Find last AUG
    last_aug = full_seq.upper().rfind("AUG")
    if last_aug == -1:
        return result

    result['aug_pos'] = last_aug

    # Build pair map and check AUG pairing
    pairs = _build_pair_map(full_structure)

    paired_positions = []
    paired_count = 0
    for i in range(last_aug, min(last_aug + 3, len(full_structure))):
        if i in pairs:
            paired_count += 1
            paired_positions.append((i, pairs[i]))

    result['aug_paired_count'] = paired_count

    # Is AUG sequestered? (>= 2 of 3 positions paired)
    if paired_count < 2:
        result['aug_sequestered'] = False
        return result

    result['aug_sequestered'] = True

    # Extract enclosing stem-loop
    hp_start, hp_end = _extract_stemloop_around_positions(
        full_structure, pairs, paired_positions, max_local_distance=50
    )

    # Determine if we need to refold
    need_refold = False
    if hp_start is None:
        need_refold = True  # No hairpin found from full structure
    else:
        hp_length = hp_end - hp_start + 1
        if hp_length > 80:
            need_refold = True  # Hairpin too large

    if need_refold:
        # Window-cut heuristic — cut ~80 nt around AUG
        cut_result = _cut_window_as_hairpin(
            full_seq, full_structure, target_pos=last_aug,
            target_len=3, window_size=80
        )
        if cut_result is not None:
            result['found'] = True
            result['method'] = 'aug_hairpin_cut'
            result['hairpin_start'] = cut_result['hairpin_start']
            result['hairpin_end'] = cut_result['hairpin_end']
            result['hairpin_seq'] = cut_result['hairpin_seq']
            result['hairpin_struct'] = None  # pipeline folds downstream
            result['hairpin_length'] = cut_result['hairpin_length']
            result['window_cut_used'] = True
            return result

        # Window cut also failed
        if hp_start is None:
            result['aug_sequestered'] = False
            return result
        # else: fall through to use the oversized hairpin from full structure

    # Trim leading/trailing dots
    while hp_start <= hp_end and full_structure[hp_start] == '.':
        hp_start += 1
    while hp_end >= hp_start and full_structure[hp_end] == '.':
        hp_end -= 1

    result['found'] = True
    result['method'] = 'aug_hairpin'
    result['hairpin_start'] = hp_start
    result['hairpin_end'] = hp_end
    result['hairpin_seq'] = full_seq[hp_start:hp_end + 1]
    result['hairpin_struct'] = full_structure[hp_start:hp_end + 1]
    result['hairpin_length'] = hp_end - hp_start + 1

    return result


def find_thermometer_hairpin(full_seq, full_structure):
    """
    Main entry point: find the thermometer hairpin using the best available method.

    Tries RBS-containing hairpin first. If no RBS found or RBS is accessible,
    falls back to AUG-containing hairpin (catches fourU-type thermometers).

    Args:
        full_seq: Complete RNA sequence
        full_structure: Dot-bracket structure of full sequence at 25°C

    Returns:
        dict: Combined result with all detection info. Key fields:
            'found': bool - whether any thermometer hairpin was detected
            'method': str - 'rbs_hairpin', 'aug_hairpin', or 'none'
            'hairpin_seq': str - the extracted hairpin sequence
            'hairpin_struct': str - the extracted hairpin structure
            'hairpin_length': int - length of the extracted hairpin
            'rbs_sequestered': bool - is the RBS buried in a stem?
            'aug_sequestered': bool - is the AUG buried in a stem?
    """
    # Try RBS-containing hairpin first
    rbs_result = find_rbs_containing_hairpin(full_seq, full_structure)

    if rbs_result['found']:
        # Add aug_sequestered field for completeness
        rbs_result['aug_pos'] = None
        rbs_result['aug_paired_count'] = 0
        rbs_result['aug_sequestered'] = False
        return rbs_result

    # Fallback: try AUG-containing hairpin
    aug_result = find_aug_containing_hairpin(full_seq, full_structure)

    # Carry forward RBS info even when using AUG fallback
    aug_result['rbs_seq'] = rbs_result.get('rbs_seq')
    aug_result['rbs_pos'] = rbs_result.get('rbs_pos')
    aug_result['rbs_paired_count'] = rbs_result.get('rbs_paired_count', 0)
    aug_result['rbs_sequestered'] = rbs_result.get('rbs_sequestered', False)

    return aug_result


def validate_sequence(sequence: str, allowed_chars: str = "ACGU") -> bool:
    """
    Check if sequence contains only valid nucleotides

    Args:
        sequence: RNA/DNA sequence string
        allowed_chars: String of allowed characters (default: "ACGU")

    Returns:
        True if valid, False otherwise
    """
    return all(c in allowed_chars for c in sequence.upper())


def base_pair_percentages(sequence, structure):
    """
    Calculate AU%, GC%, GU% for all paired nucleotides.
    sequence: RNA sequence string
    structure: dot-bracket structure string
    """
    stack = []
    pairs = []

    # Find all paired positions
    for i, char in enumerate(structure):
        if char == '(':
            stack.append(i)
        elif char == ')':
            if not stack:
                continue  # skip unmatched closing bracket
            j = stack.pop()
            pairs.append((j, i))

    # Count base pair types
    counts = {'AU': 0, 'UA': 0, 'GC': 0, 'CG': 0, 'GU': 0, 'UG': 0}
    for i, j in pairs:
        pair = sequence[i] + sequence[j]
        if pair in counts:
            counts[pair] += 1

    total_pairs = len(pairs)
    AU_percent = (counts['AU'] + counts['UA']) / total_pairs * 100 if total_pairs else 0
    GC_percent = (counts['GC'] + counts['CG']) / total_pairs * 100 if total_pairs else 0
    GU_percent = (counts['GU'] + counts['UG']) / total_pairs * 100 if total_pairs else 0

    return AU_percent, GC_percent, GU_percent


def gc_content(seq):
    if not seq:
        return 0.0
    gc = seq.count("G") + seq.count("C")
    return gc / len(seq)

def g_content (seq):
    g = seq.count("G")
    return(g)

def c_content (seq):
    c = seq.count("C")
    return(c)


def mfe_in_range(mfe, min_val, max_val):
    """
    Check if an MFE value is between min_val and max_val.

    Args:
        mfe (float or str): Minimum Free Energy value from RNAfold.
        min_val (float): Lower bound (default -15).
        max_val (float): Upper bound (default -5).

    Returns:
        bool: True if mfe is within range, False otherwise.
    """
    try:
        # Convert to float in case mfe is a string (with or without parentheses)
        mfe_float = float(str(mfe).strip("()"))
        return min_val <= mfe_float <= max_val
    except (ValueError, TypeError):
        # In case conversion fails
        return False

def base_pair_in_range(base_content, min_val, max_val):
    try:
        # Convert to float (strip parentheses if present)
        base_content = float(str(base_content).strip("()"))
        return min_val <= base_content <= max_val
    except (ValueError, TypeError):
        # Return False if conversion fails
        return False


def _pf_range_check(pf_value, settings, min_key, max_key, pf_computed):
    """Range check for PF Ensemble values. Returns 'In Range', 'Not in Range', or 'N/A'."""
    if not pf_computed or pf_value == 0.0:
        return "N/A"
    if min_key not in settings or max_key not in settings:
        return "N/A"
    try:
        v = float(str(pf_value).strip("()"))
        if settings[min_key] <= v <= settings[max_key]:
            return "In Range"
        return "Not in Range"
    except (ValueError, TypeError):
        return "N/A"


def _generic_range_check(value, settings, min_key, max_key):
    """Range check for any numeric value. Returns 'In Range', 'Not in Range', or 'N/A'."""
    if value is None:
        return "N/A"
    if min_key not in settings or max_key not in settings:
        return "N/A"
    try:
        v = float(str(value).strip("()"))
        if settings[min_key] <= v <= settings[max_key]:
            return "In Range"
        return "Not in Range"
    except (ValueError, TypeError):
        return "N/A"




def hairpin_mfe_at_temps(hairpin_seq, temps=(25, 37, 42)):
    mfe_results = {}

    for temp in temps:
        md = RNA.md()  # Create a model details object
        md.temperature = float(temp)
        md.dangles = 2  # Default
        md.noLP = 1     # No lonely pairs
        md.noGU = 0     # Allow GU pairs (default)

        fc = RNA.fold_compound(hairpin_seq, md)  # Pass md at creation
        structure, mfe = fc.mfe()
        mfe_results[temp] = (structure, mfe)

    return mfe_results

#
def fold_at_temp(seq, temp):
    md = RNA.md()
    md.temperature = float(temp)
    md.dangles = 2  # Default
    md.noLP = 1  # 0 Allow lonely pairs (default), 1 dont allow LP
    md.noGU = 0  # Allow GU pairs (default)

    fc = RNA.fold_compound(seq, md)
    structure, mfe = fc.mfe()
    return structure, mfe


def base_pairs_at_temps_struct(hairpin_seq, temp=25):
        md = RNA.md()  # Create a model details object
        md.temperature = float(temp)
        md.dangles = 2  # Default
        md.noLP = 1     # No lonely pairs
        md.noGU = 0     # Allow GU pairs (default)

        fc = RNA.fold_compound(hairpin_seq, md)  # Pass md at creation
        structure, mfe = fc.mfe()
        base_pair_temp_struct = structure
        return base_pair_temp_struct



# PARTITION FUNCTION FEATURES
# Unlike MFE which returns a single "best" structure, the partition function
# considers ALL possible structures weighted by their Boltzmann probability.
# This captures the ensemble behavior that defines RNA thermometers.

def pf_fold_at_temp(seq, temp):
    """
    Compute partition function fold at a given temperature.

    Returns dict with ensemble energy, mean base pair probability,
    and per-position unpaired probabilities.

    Optimized: Uses numpy vectorization for BPP matrix processing
    instead of O(n^2) Python loops. ~50-100x faster for typical sequences.
    """
    md = RNA.md()
    md.temperature = float(temp)
    md.dangles = 2
    md.noLP = 1
    md.noGU = 0

    fc = RNA.fold_compound(seq, md)
    mfe_struct, mfe_energy = fc.mfe()

    # Partition function — considers ALL possible structures
    fc.exp_params_rescale(mfe_energy)
    pf_struct, ensemble_energy = fc.pf()

    # Base pair probability matrix — vectorized with numpy
    bpp = fc.bpp()
    n = len(seq)

    # Build upper-triangular numpy array from BPP (1-indexed in ViennaRNA)
    bpp_array = np.zeros((n, n), dtype=np.float64)
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            val = bpp[i][j]
            if val > 0:
                bpp_array[i - 1][j - 1] = val

    # Paired probability per position = sum of row + sum of column
    paired_per_pos = bpp_array.sum(axis=1) + bpp_array.sum(axis=0)
    unpaired_probs = (1.0 - paired_per_pos).tolist()
    mean_paired_prob = float(paired_per_pos.sum()) / max(n, 1)

    return {
        'ensemble_energy': ensemble_energy,
        'mfe_energy': mfe_energy,
        'mean_paired_prob': mean_paired_prob,
        'unpaired_probs': unpaired_probs,
        'n': n
    }


def pf_fold_at_temps_batch(seq, temps=(25, 37, 42), max_pf_len=500):
    """
    Compute partition function at multiple temperatures.

    For sequences longer than max_pf_len, uses a window around the last AUG
    (start codon) instead of the full sequence. This is biologically justified:
    RNA thermometers are local structures within ~200 nt of the start codon.
    Folding a 13,000 nt operon leader adds no information about the thermometer
    and takes hours per PF call (O(n³) complexity).

    Args:
        seq: RNA sequence
        temps: Temperatures to compute PF at
        max_pf_len: Maximum sequence length for PF computation (default 500).
                    Sequences longer than this are windowed around the last AUG.

    Returns:
        dict mapping temp -> pf_result, plus 'pf_window_used' key with info
    """
    original_len = len(seq)
    pf_seq = seq
    window_offset = 0

    if original_len > max_pf_len:
        # Find last AUG (start codon) — the thermometer is upstream of this
        last_aug = seq.upper().rfind("AUG")

        if last_aug >= 0:
            # Take window ending ~30 nt past AUG (for downstream context)
            window_end = min(original_len, last_aug + 3 + 30)
            window_start = max(0, window_end - max_pf_len)
        else:
            # No AUG found — take the last max_pf_len nucleotides
            window_start = original_len - max_pf_len
            window_end = original_len

        pf_seq = seq[window_start:window_end]
        window_offset = window_start

    results = {}
    for temp in temps:
        results[temp] = pf_fold_at_temp(pf_seq, temp)

    # Store window info so caller can log it and use correct seq for RBS lookup
    results['pf_window_used'] = {
        'original_len': original_len,
        'pf_len': len(pf_seq),
        'offset': window_offset,
        'windowed': original_len > max_pf_len,
        'pf_seq': pf_seq  # The actual sequence PF was computed on
    }

    return results


def calc_rbs_pf_accessibility(seq, rbs_seq, pf_result):
    """
    Calculate RBS accessibility from partition function unpaired probabilities.

    Instead of binary paired/unpaired from MFE, this gives the PROBABILITY
    that each RBS nucleotide is unpaired (continuous, 0-100%).
    """
    if not rbs_seq or not seq or pf_result is None:
        return {'rbs_pf_accessibility_pct': None}

    rbs_start = seq.upper().find(rbs_seq.upper())
    if rbs_start == -1:
        return {'rbs_pf_accessibility_pct': None}

    unpaired_probs = pf_result['unpaired_probs']
    rbs_probs = unpaired_probs[rbs_start:rbs_start + len(rbs_seq)]

    if not rbs_probs:
        return {'rbs_pf_accessibility_pct': None}

    mean_unpaired = sum(rbs_probs) / len(rbs_probs)

    return {
        'rbs_pf_accessibility_pct': mean_unpaired * 100.0
    }


def save_results_to_csv(results: List[Dict[str, Any]], output_file: Path,
                        temps: Optional[List[int]] = None) -> None:
    """Save results to CSV file"""
    if temps is None:
        temps = [25, 37, 42]
    import csv

    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)

        # Dynamic headers based on temperatures
        headers = [
            "Name", "Sequence", "Structure", "MFE",
            "Hairpin Position", "Hairpin Sequence", "Hairpin Structure"
        ]
        headers.extend([f"MFE at {t}°C" for t in temps])
        headers.extend(["PNG Original", "PNG Hairpin"])

        writer.writerow(headers)

        for result in results:
            row = [
                result['name'],
                result['sequence'],
                result['structure'],
                f"{result['mfe']:.2f}",
                f"{result['hairpin_start']}-{result['hairpin_end']}",
                result['hairpin_seq'],
                result['hairpin_struct']
            ]
            row.extend([result.get(f'mfe_{t}', 'N/A') for t in temps])
            row.extend([result['png_original'], result['png_hairpin']])

            writer.writerow(row)

    print(f"Results saved to {output_file}")


def _analyze_single_sequence(args):
    """
    Process a single RNA sequence for thermometer properties.
    Module-level function required by multiprocessing Pool (must be picklable).
    Supports dynamic folding temperatures (1-5 configurable values).
    """
    (idx, total, og_name, og_seq, settings, calc_settings, seq_settings,
     need_pf_full, need_pf_hairpin, temps) = args

    base_temp = temps[0]
    t_first = temps[0]
    found_count = 0

    # Skip very short sequences
    if len(og_seq) <= 4:
        return None

    # Apply sequence preprocessing
    if seq_settings.get("append_sequence_enabled", False):
        append_seq = seq_settings.get("append_sequence", "AUG").upper()
        position = seq_settings.get("append_position", "end")
        if position == "start":
            og_seq = append_seq + og_seq
        else:
            og_seq = og_seq + append_seq

    # Calculate composition for ORIGINAL sequence
    original_comp = {"AU%": 0, "GC%": 0, "GU%": 0}
    if calc_settings.get("calculate_original_composition", False):
        original_comp = calculate_composition(og_seq)

    # Original sequence MFE at temps (dynamic loop)
    structures = {}
    mfes = {}
    if calc_settings.get("calculate_original_mfe_temps", False):
        for t in temps:
            structures[t], mfes[t] = fold_at_temp(og_seq, t)
    else:
        structures[base_temp], mfes[base_temp] = fold_at_temp(og_seq, base_temp)
        for t in temps:
            if t not in mfes:
                mfes[t] = 0.0
                structures[t] = ""

    # Partition Function analysis (full sequence) — skip if no PF columns selected
    pf_full = {}            # temp -> pf_result dict
    pf_full_ensemble = {}   # temp -> float
    pf_full_mean_paired = {}  # temp -> float
    pf_window_info = None

    for t in temps:
        pf_full[t] = None
        pf_full_ensemble[t] = 0.0
        pf_full_mean_paired[t] = 0.0

    if calc_settings.get("calculate_original_mfe_temps", False) and need_pf_full:
        try:
            pf_full_batch = pf_fold_at_temps_batch(og_seq, temps=tuple(temps))
            pf_window_info = pf_full_batch.get('pf_window_used', {})
            for t in temps:
                pf_full[t] = pf_full_batch[t]
                pf_full_ensemble[t] = pf_full[t]['ensemble_energy']
                pf_full_mean_paired[t] = pf_full[t]['mean_paired_prob']
        except Exception as e:
            print(f"[RSAS] Warning: partition function (full sequence) failed for '{og_name}': {e}", file=sys.stderr)

    # Original sequence range checks (dynamic)
    calc_orig_temps = calc_settings.get("calculate_original_mfe_temps", False)
    calc_orig_comp = calc_settings.get("calculate_original_composition", False)

    orig_mfe_str = {}
    for t in temps:
        if t == base_temp or calc_orig_temps:
            in_range = mfe_in_range(mfes.get(t, 0.0),
                                    settings.get(f'orig_mfe_{t}_min', -100),
                                    settings.get(f'orig_mfe_{t}_max', 100))
            orig_mfe_str[t] = "In Range" if in_range else "Not in Range"
        else:
            orig_mfe_str[t] = "N/A"

    orig_au_str = ("In Range" if base_pair_in_range(original_comp["AU%"], settings.get('orig_au_min', 0),
                                                     settings.get('orig_au_max', 100)) else "Not in Range") if calc_orig_comp else "N/A"
    orig_gc_str = ("In Range" if base_pair_in_range(original_comp["GC%"], settings.get('orig_gc_min', 0),
                                                     settings.get('orig_gc_max', 100)) else "Not in Range") if calc_orig_comp else "N/A"
    orig_gu_str = ("In Range" if base_pair_in_range(original_comp["GU%"], settings.get('orig_gu_min', 0),
                                                     settings.get('orig_gu_max', 100)) else "Not in Range") if calc_orig_comp else "N/A"

    # Full-length RBS sequestering analysis (dynamic)
    full_rbs = {}  # temp -> {"seq":, "struct":, "paired":}
    for t in temps:
        full_rbs[t] = {"seq": None, "struct": None, "paired": None}

    rbs_seq_diffs = {}  # key like "42_25" -> float

    if calc_settings.get("calculate_rbs_full_length", True):
        # Always compute for base temp
        rbs_base = find_rbs_in_full_sequence(og_seq, structures.get(base_temp, ""))
        full_rbs[base_temp] = {"seq": rbs_base["rbs_seq"], "struct": rbs_base["rbs_structure"],
                                "paired": rbs_base["rbs_paired_percent"]}

        if calc_orig_temps:
            for t in temps:
                if t != base_temp:
                    rbs_t = find_rbs_in_full_sequence(og_seq, structures.get(t, ""))
                    full_rbs[t] = {"seq": rbs_t["rbs_seq"], "struct": rbs_t["rbs_structure"],
                                    "paired": rbs_t["rbs_paired_percent"]}

            base_paired = full_rbs[t_first]["paired"]
            if len(temps) >= 2 and base_paired is not None:
                last_paired = full_rbs[temps[-1]]["paired"]
                if last_paired is not None:
                    rbs_seq_diffs[f"{temps[-1]}_{t_first}"] = last_paired - base_paired
            if len(temps) >= 3 and base_paired is not None:
                penult_paired = full_rbs[temps[-2]]["paired"]
                if penult_paired is not None:
                    rbs_seq_diffs[f"{temps[-2]}_{t_first}"] = penult_paired - base_paired

    # PF RBS Accessibility — skip if no PF columns selected
    pf_rbs_access = {}   # temp -> float or None
    pf_rbs_diffs = {}    # key like "42_25" -> float
    for t in temps:
        pf_rbs_access[t] = None

    if need_pf_hairpin:
        rbs_seq_for_pf = full_rbs[base_temp]["seq"]
        pf_rbs_seq = pf_window_info.get('pf_seq', og_seq) if pf_window_info else og_seq
        if rbs_seq_for_pf and pf_full[base_temp] is not None:
            try:
                for t in temps:
                    if pf_full[t] is not None:
                        res = calc_rbs_pf_accessibility(pf_rbs_seq, rbs_seq_for_pf, pf_full[t])
                        pf_rbs_access[t] = res['rbs_pf_accessibility_pct']

                base_acc = pf_rbs_access[t_first]
                if len(temps) >= 2 and base_acc is not None and pf_rbs_access[temps[-1]] is not None:
                    pf_rbs_diffs[f"{temps[-1]}_{t_first}"] = pf_rbs_access[temps[-1]] - base_acc
                if len(temps) >= 3 and base_acc is not None and pf_rbs_access[temps[-2]] is not None:
                    pf_rbs_diffs[f"{temps[-2]}_{t_first}"] = pf_rbs_access[temps[-2]] - base_acc
            except Exception as e:
                print(f"[RSAS] Warning: RBS PF accessibility failed for '{og_name}': {e}", file=sys.stderr)

    # Hairpin Detection (uses base_temp structure)
    hairpin_method = settings.get('hairpin_detection_method', 'terminal')
    hairpin_detection_label = ""
    RBS_seq = RBS_dot_struct = RBS_paired_percent = None

    base_structure = structures.get(base_temp, "")
    if hairpin_method == 'rbs_based':
        thermo_result = find_thermometer_hairpin(og_seq, base_structure)
        if thermo_result['found']:
            hairpin_seq = thermo_result['hairpin_seq']
            hairpin_struct = thermo_result.get('hairpin_struct')
            hairpin_detection_label = thermo_result['method']
            if hairpin_struct is None:
                hairpin_struct, _ = fold_at_temp(hairpin_seq, base_temp)
            hairpin_seq_trimmed = trim_trailing_unpaired(hairpin_seq, hairpin_struct)
            RBS_seq = thermo_result.get('rbs_seq')
            if RBS_seq and hairpin_struct:
                RBS_dot_struct = get_rbs_dot_struct(RBS_seq, hairpin_seq, hairpin_struct)
                if RBS_dot_struct is not None:
                    RBS_paired_percent = calc_rbs_paired_percent(RBS_dot_struct)
        else:
            return None  # No hairpin found
    else:
        term_results = get_terminal_hairpin_with_tail(og_seq, base_structure)
        hairpin_detection_label = "terminal"
        if term_results is None or term_results.get("hairpin_seq") is None:
            return None  # No hairpin found
        hairpin_seq = term_results["hairpin_seq"]
        hairpin_struct = term_results["hairpin_struct"]
        hairpin_seq_trimmed = trim_trailing_unpaired(hairpin_seq, hairpin_struct)
        if calc_settings.get("calculate_rbs", True):
            RBS_results = find_rbs_in_hairpin(hairpin_seq)
            RBS_seq = RBS_results["rbs_seq"]
            if RBS_seq:
                RBS_dot_struct = get_rbs_dot_struct(RBS_seq, hairpin_seq, hairpin_struct)
                if RBS_dot_struct is not None:
                    RBS_paired_percent = calc_rbs_paired_percent(RBS_dot_struct)

    # MFE at configured temperatures (dynamic)
    MFE_results = hairpin_mfe_at_temps(hairpin_seq_trimmed, temps=temps)
    hp_mfe = {t: MFE_results[t][1] for t in temps}

    # Range checks for hairpin MFE (dynamic)
    hp_mfe_str = {}
    for t in temps:
        min_k, max_k = f'mfe_{t}_min', f'mfe_{t}_max'
        if min_k in settings and max_k in settings:
            in_range = mfe_in_range(hp_mfe[t], settings[min_k], settings[max_k])
            hp_mfe_str[t] = "In Range" if in_range else "Not in Range"
            if in_range:
                found_count += 1
        else:
            hp_mfe_str[t] = "N/A"

    # Partition Function for hairpin — skip if no PF columns selected
    pf_hp_ensemble = {}
    pf_hp_mean_paired = {}
    for t in temps:
        pf_hp_ensemble[t] = 0.0
        pf_hp_mean_paired[t] = 0.0

    if need_pf_hairpin:
        try:
            pf_hp_batch = pf_fold_at_temps_batch(hairpin_seq_trimmed, temps=tuple(temps))
            for t in temps:
                pf_hp_ensemble[t] = pf_hp_batch[t]['ensemble_energy']
                pf_hp_mean_paired[t] = pf_hp_batch[t]['mean_paired_prob']
        except Exception as e:
            print(f"[RSAS] Warning: partition function (hairpin) failed for '{og_name}': {e}", file=sys.stderr)

    # Base pair composition
    AU, GC, GU = base_pair_percentages(hairpin_seq, hairpin_struct)

    if 'au_min' in settings and 'au_max' in settings:
        AU_in_range = base_pair_in_range(AU, settings['au_min'], settings['au_max'])
        AU_str = "In Range" if AU_in_range else "Not in Range"
        if AU_in_range: found_count += 1
    else:
        AU_str = "N/A"

    if 'gc_min' in settings and 'gc_max' in settings:
        GC_in_range = base_pair_in_range(GC, settings['gc_min'], settings['gc_max'])
        GC_str = "In Range" if GC_in_range else "Not in Range"
        if GC_in_range: found_count += 1
    else:
        GC_str = "N/A"

    if 'gu_min' in settings and 'gu_max' in settings:
        GU_in_range = base_pair_in_range(GU, settings['gu_min'], settings['gu_max'])
        GU_str = "In Range" if GU_in_range else "Not in Range"
        if GU_in_range: found_count += 1
    else:
        GU_str = "N/A"

    total_found_count = found_count

    # ── Build result dictionary (dynamic temperature keys) ──
    result_data = {
        "name": og_name,
        "original_sequence": og_seq,
        "original_structure": structures.get(base_temp, ""),
        "original_au_percent": original_comp["AU%"],
        "original_gc_percent": original_comp["GC%"],
        "original_gu_percent": original_comp["GU%"],
        "original_au_in_range": orig_au_str,
        "original_gc_in_range": orig_gc_str,
        "original_gu_in_range": orig_gu_str,
        "hairpin_detection_method": hairpin_detection_label,
        "hairpin_sequence": hairpin_seq,
        "hairpin_structure": hairpin_struct,
        "hairpin_au_percent": AU,
        "hairpin_gc_percent": GC,
        "hairpin_gu_percent": GU,
        "au_in_range_hairpin": AU_str,
        "gc_in_range_hairpin": GC_str,
        "gu_in_range_hairpin": GU_str,
        "rbs_sequence": RBS_seq if RBS_seq else "Not Found",
        "rbs_structure": RBS_dot_struct if RBS_dot_struct else "N/A",
        "rbs_paired_percent": f"{RBS_paired_percent:.2f}" if RBS_paired_percent is not None else "N/A",
        "rbs_paired_in_range": _generic_range_check(RBS_paired_percent, settings, 'rbs_paired_min', 'rbs_paired_max'),
        "hp_quality_score": f"{total_found_count}/6",  # Legacy fallback, overwritten by profile
        "hp_quality_score_class": "N/A",  # Overwritten by profile scoring
    }

    # Temperature-dependent keys
    for t in temps:
        # Full-length structures (non-base temps)
        if t != base_temp:
            result_data[f"full_structure_{t}"] = structures.get(t, "") if calc_orig_temps else ""

        # Original MFE
        result_data[f"original_mfe_{t}"] = f"{mfes.get(t, 0.0):.2f}"
        result_data[f"original_mfe_{t}_in_range"] = orig_mfe_str.get(t, "N/A")

        # Full RBS
        rbs_t = full_rbs.get(t, {})
        result_data[f"full_rbs_{t}_seq"] = rbs_t.get("seq") if rbs_t.get("seq") else "Not Found"
        result_data[f"full_rbs_{t}_struct"] = rbs_t.get("struct") if rbs_t.get("struct") else "N/A"
        p = rbs_t.get("paired")
        result_data[f"full_rbs_{t}_paired"] = f"{p:.2f}" if p is not None else "N/A"

        # Hairpin MFE
        result_data[f"mfe_{t}c_hairpin"] = f"{hp_mfe[t]:.2f}"
        result_data[f"mfe_{t}_in_range_hairpin"] = hp_mfe_str.get(t, "N/A")

        # PF full sequence
        result_data[f"pf_full_ensemble_{t}"] = f"{pf_full_ensemble.get(t, 0.0):.2f}"
        result_data[f"pf_full_mean_paired_{t}"] = f"{pf_full_mean_paired.get(t, 0.0):.4f}"

        # PF hairpin
        result_data[f"pf_hp_ensemble_{t}"] = f"{pf_hp_ensemble.get(t, 0.0):.2f}"
        result_data[f"pf_hp_ensemble_{t}_in_range"] = _pf_range_check(
            pf_hp_ensemble.get(t, 0.0), settings,
            f'pf_ensemble_{t}_min', f'pf_ensemble_{t}_max', need_pf_hairpin)
        result_data[f"pf_hp_mean_paired_{t}"] = f"{pf_hp_mean_paired.get(t, 0.0):.4f}"

        # PF RBS accessibility
        acc = pf_rbs_access.get(t)
        result_data[f"pf_rbs_access_{t}"] = f"{acc:.2f}" if acc is not None else "N/A"

    # RBS sequestering diffs
    for diff_key, diff_val in rbs_seq_diffs.items():
        result_data[f"rbs_seq_diff_{diff_key}"] = f"{diff_val:+.2f}"
    # Ensure diff keys exist even if no data
    if len(temps) >= 2:
        dk = f"rbs_seq_diff_{temps[-1]}_{t_first}"
        result_data.setdefault(dk, "N/A")
    if len(temps) >= 3:
        dk = f"rbs_seq_diff_{temps[-2]}_{t_first}"
        result_data.setdefault(dk, "N/A")

    # PF RBS diffs
    for diff_key, diff_val in pf_rbs_diffs.items():
        result_data[f"pf_rbs_diff_{diff_key}"] = f"{diff_val:+.2f}"
    if len(temps) >= 2:
        dk = f"pf_rbs_diff_{temps[-1]}_{t_first}"
        result_data.setdefault(dk, "N/A")
    if len(temps) >= 3:
        dk = f"pf_rbs_diff_{temps[-2]}_{t_first}"
        result_data.setdefault(dk, "N/A")

    # ── Motif / Sequence Finder ──
    motif_pattern = calc_settings.get("motif_pattern", "")
    motif_enabled = calc_settings.get("motif_search_enabled", False) and bool(motif_pattern)
    if motif_enabled:
        try:
            from RnaThermofinder.utils.motif_finder import analyze_motif_sequestering
            _motif_pf = {}
            if need_pf_full:
                for t in temps:
                    if pf_full.get(t) is not None:
                        _motif_pf[t] = pf_full[t]
            motif_result = analyze_motif_sequestering(
                og_seq, motif_pattern, structures, temps,
                pf_results=_motif_pf if _motif_pf else None,
                pf_window_info=pf_window_info,
            )
            result_data.update(motif_result["summary"])
        except Exception as e:
            print(f"[RSAS] Warning: motif analysis failed for '{og_name}': {e}", file=sys.stderr)
            result_data["motif_pattern"] = motif_pattern
            result_data["motif_count"] = 0
            result_data["motif_match_seq"] = "Error"
            result_data["motif_match_pos"] = "N/A"
    elif motif_pattern:
        # Motif configured but search disabled — add placeholder keys
        result_data["motif_pattern"] = motif_pattern
        result_data["motif_count"] = 0
        result_data["motif_match_seq"] = "Disabled"
        result_data["motif_match_pos"] = "N/A"

    # ── Compute quality scores using temperature-aware metric registries ──
    hp_metrics = settings.get('_hp_metrics_registry', AVAILABLE_METRICS_HAIRPIN)
    fl_metrics = settings.get('_fl_metrics_registry', AVAILABLE_METRICS_FULL)

    hp_profile = settings.get('_scoring_profile', None)
    if hp_profile:
        qs = compute_quality_score(result_data, hp_profile, pf_available=need_pf_hairpin,
                                   metrics_registry=hp_metrics, key_prefix="hp_")
        result_data.update(qs)
    else:
        result_data["hp_quality_score"] = f"{total_found_count}/6"
        result_data["hp_quality_score_weighted"] = round(total_found_count / 6 * 100, 1) if total_found_count else 0.0
        result_data["hp_quality_score_class"] = "N/A"
        result_data["hp_quality_score_breakdown"] = ""

    fl_profile = settings.get('_scoring_profile_full', None)
    if fl_profile:
        qs_fl = compute_quality_score(result_data, fl_profile, pf_available=need_pf_full,
                                      metrics_registry=fl_metrics, key_prefix="fl_")
        result_data.update(qs_fl)
    else:
        result_data["fl_quality_score"] = "N/A"
        result_data["fl_quality_score_weighted"] = 0.0
        result_data["fl_quality_score_class"] = "N/A"
        result_data["fl_quality_score_breakdown"] = ""

    return result_data



def _build_fallback_data_keys(temps):
    """Return the ordered list of result-dict keys matching _build_fallback_headers."""
    base = temps[0]
    t_first = temps[0]
    keys = ["name", "original_sequence", "original_structure"]
    # Full-length structures (non-base temps)
    for t in temps:
        if t != base:
            keys.append(f"full_structure_{t}")
    # Original MFE
    for t in temps:
        keys.append(f"original_mfe_{t}")
    keys += ["original_au_percent", "original_gc_percent", "original_gu_percent"]
    # Original range checks
    for t in temps:
        keys.append(f"original_mfe_{t}_in_range")
    keys += ["original_au_in_range", "original_gc_in_range", "original_gu_in_range"]
    # Full-length RBS
    for t in temps:
        keys += [f"full_rbs_{t}_seq", f"full_rbs_{t}_struct", f"full_rbs_{t}_paired"]
    if len(temps) >= 2:
        keys.append(f"rbs_seq_diff_{temps[-1]}_{t_first}")
    if len(temps) >= 3:
        keys.append(f"rbs_seq_diff_{temps[-2]}_{t_first}")
    # Hairpin
    keys += ["hairpin_detection_method", "hairpin_sequence", "hairpin_structure",
             "hairpin_au_percent", "hairpin_gc_percent", "hairpin_gu_percent"]
    for t in temps:
        keys.append(f"mfe_{t}c_hairpin")
    for t in temps:
        keys.append(f"mfe_{t}_in_range_hairpin")
    keys += ["au_in_range_hairpin", "gc_in_range_hairpin", "gu_in_range_hairpin"]
    keys += ["rbs_sequence", "rbs_structure", "rbs_paired_percent"]
    # PF full
    for t in temps:
        keys.append(f"pf_full_ensemble_{t}")
    for t in temps:
        keys.append(f"pf_full_mean_paired_{t}")
    # PF hairpin
    for t in temps:
        keys.append(f"pf_hp_ensemble_{t}")
    for t in temps:
        keys.append(f"pf_hp_mean_paired_{t}")
    # PF RBS
    for t in temps:
        keys.append(f"pf_rbs_access_{t}")
    if len(temps) >= 2:
        keys.append(f"pf_rbs_diff_{temps[-1]}_{t_first}")
    if len(temps) >= 3:
        keys.append(f"pf_rbs_diff_{temps[-2]}_{t_first}")
    # PF ensemble range checks
    for t in temps:
        keys.append(f"pf_hp_ensemble_{t}_in_range")
    keys.append("rbs_paired_in_range")
    # Motif / Sequence Finder
    keys += ["motif_pattern", "motif_count", "motif_match_seq", "motif_match_pos"]
    for t in temps:
        keys += [f"motif_paired_pct_{t}", f"motif_struct_{t}", f"motif_pf_access_{t}"]
    if len(temps) >= 2:
        keys += [f"motif_paired_diff_{temps[-1]}_{t_first}",
                 f"motif_pf_diff_{temps[-1]}_{t_first}"]
    if len(temps) >= 3:
        keys += [f"motif_paired_diff_{temps[-2]}_{t_first}",
                 f"motif_pf_diff_{temps[-2]}_{t_first}"]
    # Quality scores
    keys += ["hp_quality_score", "hp_quality_score_weighted",
             "hp_quality_score_class", "hp_quality_score_breakdown",
             "fl_quality_score", "fl_quality_score_weighted",
             "fl_quality_score_class", "fl_quality_score_breakdown"]
    return keys


def _build_fallback_headers(temps):
    """Build display-name headers matching _build_fallback_data_keys order."""
    base = temps[0]
    t_first = temps[0]
    hdrs = ["Name", "Sequence", "Structure"]
    for t in temps:
        if t != base:
            hdrs.append(f"Full_Structure_{t}C")
    for t in temps:
        hdrs.append(f"Original_MFE_{t}C")
    hdrs += ["Original_AU%", "Original_GC%", "Original_GU%"]
    for t in temps:
        hdrs.append(f"Original_MFE_{t}C_InRange")
    hdrs += ["Original_AU%_InRange", "Original_GC%_InRange", "Original_GU%_InRange"]
    for t in temps:
        hdrs += [f"Full_RBS_{t}C_Seq", f"Full_RBS_{t}C_Struct", f"Full_RBS_{t}C_Paired%"]
    if len(temps) >= 2:
        hdrs.append(f"RBS_Seq_Diff_{temps[-1]}-{t_first}")
    if len(temps) >= 3:
        hdrs.append(f"RBS_Seq_Diff_{temps[-2]}-{t_first}")
    hdrs += ["Hairpin_Detection_Method", "Hairpin_Sequence", "Hairpin_Structure",
             "Hairpin_AU%", "Hairpin_GC%", "Hairpin_GU%"]
    for t in temps:
        hdrs.append(f"Hairpin_MFE_{t}C")
    for t in temps:
        hdrs.append(f"Hairpin_MFE_{t}C_InRange")
    hdrs += ["Hairpin_AU%_InRange", "Hairpin_GC%_InRange", "Hairpin_GU%_InRange"]
    hdrs += ["RBS_Sequence", "RBS_Structure", "RBS_Paired%"]
    for t in temps:
        hdrs.append(f"PF_Full_Ensemble_{t}C")
    for t in temps:
        hdrs.append(f"PF_Full_MeanPaired_{t}C")
    for t in temps:
        hdrs.append(f"PF_HP_Ensemble_{t}C")
    for t in temps:
        hdrs.append(f"PF_HP_MeanPaired_{t}C")
    for t in temps:
        hdrs.append(f"PF_RBS_Access_{t}C")
    if len(temps) >= 2:
        hdrs.append(f"PF_RBS_Diff_{temps[-1]}-{t_first}")
    if len(temps) >= 3:
        hdrs.append(f"PF_RBS_Diff_{temps[-2]}-{t_first}")
    for t in temps:
        hdrs.append(f"PF_HP_Ensemble_{t}C_InRange")
    hdrs.append("RBS_Paired%_InRange")
    # Motif / Sequence Finder
    hdrs += ["Motif_Pattern", "Motif_Count", "Motif_Match_Seq", "Motif_Match_Pos"]
    for t in temps:
        hdrs += [f"Motif_Paired%_{t}C", f"Motif_Struct_{t}C", f"Motif_PF_Access_{t}C"]
    if len(temps) >= 2:
        hdrs += [f"Motif_Paired_Diff_{temps[-1]}-{t_first}",
                 f"Motif_PF_Diff_{temps[-1]}-{t_first}"]
    if len(temps) >= 3:
        hdrs += [f"Motif_Paired_Diff_{temps[-2]}-{t_first}",
                 f"Motif_PF_Diff_{temps[-2]}-{t_first}"]
    hdrs += ["HP_Quality_Score", "HP_Quality_Score_Weighted",
             "HP_Quality_Score_Class", "HP_Quality_Score_Breakdown",
             "FL_Quality_Score", "FL_Quality_Score_Weighted",
             "FL_Quality_Score_Class", "FL_Quality_Score_Breakdown"]
    return hdrs


def calculate_results_final(
        sequences: List[Tuple[str, str]],
        output_dir: Path,
        settings: Dict[str, int],
        progress_callback: Optional[Callable[[str], None]] = None,
        csv_settings_manager = None
) -> List[Dict[str, Any]]:
    """
    Analyze RNA sequences for thermometer properties.
    Supports multiprocessing for parallel analysis across CPU cores.

    Args:
        sequences: List of (name, sequence) tuples
        output_dir: Directory for output files
        settings: Analysis filter settings (MFE ranges, composition ranges, etc.)
        progress_callback: Optional function to call with progress messages
        csv_settings_manager: Settings manager for output column configuration

    Returns:
        List of result dictionaries
    """
    results = []
    start_time = time.time()

    def log(message: str):
        print(message)
        if progress_callback:
            progress_callback(message)

    def elapsed():
        """Format elapsed time since analysis started."""
        secs = time.time() - start_time
        if secs < 60:
            return f"{secs:.1f}s"
        mins, secs = divmod(secs, 60)
        if mins < 60:
            return f"{int(mins)}m {secs:.0f}s"
        hrs, mins = divmod(mins, 60)
        return f"{int(hrs)}h {int(mins)}m {secs:.0f}s"

    structures_dir = output_dir / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)

    total = len(sequences)

    # Load settings for workers
    calc_settings = {}
    seq_settings = {}
    if csv_settings_manager:
        calc_settings = csv_settings_manager.settings.get("calculation_settings", {})
        seq_settings = csv_settings_manager.settings.get("sequence_processing", {})

    # ── Resolve folding temperatures ──
    from settings_manager import DEFAULT_TEMPERATURES
    if csv_settings_manager:
        temps = csv_settings_manager.get_temperatures()
    else:
        temps = list(DEFAULT_TEMPERATURES)
    log(f"  Folding temperatures: {temps}")

    # ── Build temperature-aware metric registries ──
    hp_metrics = build_hairpin_metrics(temps)
    fl_metrics = build_full_metrics(temps)
    range_keys = build_metric_range_keys(temps)

    # Inject active scoring profiles into settings and extract ranges
    if csv_settings_manager:
        settings = dict(settings)  # copy to avoid mutating caller's dict

        # Inject metric registries for workers
        settings['_hp_metrics_registry'] = hp_metrics
        settings['_fl_metrics_registry'] = fl_metrics
        settings['_metric_range_keys'] = range_keys

        # Hairpin scoring profile
        active_profile = csv_settings_manager.get_active_scoring_profile()
        if active_profile:
            settings['_scoring_profile'] = active_profile
            # Extract ranges from profile into the settings dict
            profile_ranges = extract_ranges_from_profile(active_profile, temps=temps)
            settings.update(profile_ranges)

        # Full-length scoring profile
        active_full_profile = csv_settings_manager.get_active_full_scoring_profile()
        if active_full_profile:
            settings['_scoring_profile_full'] = active_full_profile
            # Extract full-length ranges too
            fl_ranges = extract_ranges_from_profile(active_full_profile, temps=temps)
            settings.update(fl_ranges)

    # Check which PF calculations are needed based on selected output columns
    enabled_columns = csv_settings_manager.get_enabled_columns() if csv_settings_manager else []
    need_pf_full = any(c.startswith("PF_Full_") for c in enabled_columns)
    need_pf_hairpin = any(c.startswith("PF_HP_") or c.startswith("PF_RBS_") for c in enabled_columns)

    # Also enable PF if scoring profiles reference PF metrics
    if csv_settings_manager:
        if not need_pf_hairpin:
            active_profile = csv_settings_manager.get_active_scoring_profile()
            if active_profile:
                for crit in active_profile.get("criteria", []):
                    metric_id = crit.get("metric", "")
                    if metric_id.startswith("pf_hp_"):
                        need_pf_hairpin = True
                        break
        if not need_pf_full:
            active_full_profile = csv_settings_manager.get_active_full_scoring_profile()
            if active_full_profile:
                for crit in active_full_profile.get("criteria", []):
                    metric_id = crit.get("metric", "")
                    if metric_id.startswith("pf_full_"):
                        need_pf_full = True
                        break

    pf_status = "enabled" if (need_pf_full or need_pf_hairpin) else "skipped (no PF columns selected)"
    log(f"  Partition function: {pf_status}")

    # Resolve CPU core count (default 1; user chooses how many)
    num_cores = settings.get('num_cpu_cores', 1)
    if num_cores <= 0:
        num_cores = 1
    num_cores = min(num_cores, os.cpu_count() or 1)
    num_cores = min(num_cores, total)  # no more cores than sequences
    num_cores = max(1, num_cores)

    log(f"Analyzing {total} RNA sequences using {num_cores} CPU core(s)...\n")

    work_items = []
    for idx, (og_name, og_seq) in enumerate(sequences, 1):
        work_items.append((
            idx, total, og_name, og_seq, settings, calc_settings, seq_settings,
            need_pf_full, need_pf_hairpin, temps
        ))

    if num_cores == 1:
        # Sequential mode with per-sequence logging
        for item in work_items:
            idx, _, og_name = item[0], item[1], item[2]
            log(f"[{idx}/{total}] Processing: {og_name} ({len(item[3])} nt)")
            result = _analyze_single_sequence(item)
            if result is not None:
                results.append(result)
                pct = result.get('hp_quality_score_weighted', 0)
                log(f"  Done {og_name} (score: {pct:.0f}%) [{elapsed()}]")
            else:
                log(f"  Skipped {og_name} (no hairpin or too short)")
    else:
        # Parallel mode
        log(f"Starting parallel analysis with {num_cores} workers...")
        with Pool(processes=num_cores) as pool:
            for i, result in enumerate(pool.imap_unordered(_analyze_single_sequence, work_items)):
                if result is not None:
                    results.append(result)
                completed = i + 1
                if completed % 50 == 0 or completed == total:
                    log(f"  Progress: {completed}/{total} sequences [{elapsed()}]")

        log(f"  Parallel processing complete: {len(results)} results from {total} sequences")

    # Sort by quality score (best candidates first)
    log(f"\n{'=' * 60}")
    log(f"Sorting results by quality score...")
    results.sort(key=lambda x: (-x.get("hp_quality_score_weighted", 0), x.get("name", "")))

    top_candidates = [r for r in results if r.get("hp_quality_score_weighted", 0) >= 67]
    if top_candidates:
        log(f"\nTop candidates (67%+ score): {len(top_candidates)} sequences")
        for result in top_candidates[:5]:
            pct = result.get('hp_quality_score_weighted', 0)
            qs = result.get('hp_quality_score', '')
            tier = result.get('hp_quality_score_class', '')
            log(f"   {result['name']} - {pct:.0f}% [{qs}] {tier}")
        if len(top_candidates) > 5:
            log(f"   ... and {len(top_candidates) - 5} more")

    log(f"\n{'=' * 60}")
    log(f"Saving results to CSV...")

    output_file = output_dir / "rna_results.csv"

    csv_settings = csv_settings_manager
    try:
        if csv_settings:
            headers = csv_settings.get_enabled_columns()
            log(f"  Using {len(headers)} selected output columns")
        else:
            raise ValueError("No settings manager provided")
    except Exception:
        log("  No column settings found, using all columns")
        headers = _build_fallback_headers(temps)
        csv_settings = None

    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        # Write data rows
        from RnaThermofinder.utils.analysis_helpers import build_csv_row
        for result_data in results:
            row = None
            if csv_settings:
                # Use settings to build row
                row = build_csv_row(result_data, csv_settings)

                # If build_csv_row failed, use fallback for THIS row only
                # (don't permanently switch to fallback — that misaligns columns)
                if row is None or not isinstance(row, list):
                    log(f"Warning: build_csv_row returned invalid data for {result_data.get('name', '?')}")
                    row = None

            if row is None:
                # Fallback: use the same key order as _build_fallback_headers
                fallback_keys = _build_fallback_data_keys(temps)
                row = [result_data.get(k, "") for k in fallback_keys]

            writer.writerow(row)
    log(f"CSV saved to: {output_file.name}")

    # Save Excel with two tabs
    try:
        from RnaThermofinder.utils.analysis_helpers import write_excel_with_tabs
        excel_file = output_dir / "rna_results.xlsx"
        write_excel_with_tabs(results, excel_file, csv_settings, temps=temps)
        log(f"Excel saved to: {excel_file.name} (Full Sequence + Hairpin Analysis tabs)")
    except ImportError:
        log("openpyxl not installed, skipping Excel export. Run: pip install openpyxl")
    except Exception as e:
        log(f"Excel export failed: {e}")

    log(f"\nAnalysis complete: {len(results)} sequences processed in {elapsed()}")

    return results


