"""
Synthetic Pool Generator.

Generates pools of random RNA sequences with fixed motif inserts and
optional composition filtering (GC%/AU%/GU%). Output is FASTA format.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Optional, TextIO

# IUPAC -> list of matching concrete bases
_IUPAC_RESOLVE: Dict[str, List[str]] = {
    "A": ["A"], "C": ["C"], "G": ["G"], "U": ["U"],
    "R": ["A", "G"],   "Y": ["C", "U"],   "S": ["G", "C"],   "W": ["A", "U"],
    "K": ["G", "U"],   "M": ["A", "C"],
    "B": ["C", "G", "U"], "D": ["A", "G", "U"],
    "H": ["A", "C", "U"], "V": ["A", "C", "G"],
    "N": ["A", "C", "G", "U"],
}

_BASES = ["A", "C", "G", "U"]


def validate_iupac(motif: str) -> Optional[str]:
    """Return error message if motif has invalid IUPAC chars, else None."""
    for ch in motif.upper():
        if ch not in _IUPAC_RESOLVE:
            return f"Invalid IUPAC character: '{ch}'"
    return None


def resolve_iupac_char(char: str, rng: random.Random) -> str:
    """Pick a random concrete nucleotide matching the IUPAC char."""
    options = _IUPAC_RESOLVE.get(char.upper())
    if options is None:
        raise ValueError(f"Invalid IUPAC character: '{char}'")
    return rng.choice(options)


def resolve_iupac_motif(motif: str, rng: random.Random) -> str:
    """Resolve each IUPAC character in motif to a concrete nucleotide."""
    return "".join(resolve_iupac_char(ch, rng) for ch in motif)



def random_region(length: int, rng: random.Random) -> str:
    """Generate a random nucleotide string of given length."""
    return "".join(rng.choice(_BASES) for _ in range(length))



def calc_composition(seq: str) -> Dict[str, float]:
    """Return GC%, AU%, GU% as fractions (0.0-1.0)."""
    n = len(seq)
    if n == 0:
        return {"gc": 0.0, "au": 0.0, "gu": 0.0}
    upper = seq.upper()
    counts = {b: upper.count(b) for b in _BASES}
    return {
        "gc": (counts["G"] + counts["C"]) / n,
        "au": (counts["A"] + counts["U"]) / n,
        "gu": (counts["G"] + counts["U"]) / n,
    }


def check_composition_targets(
    seq: str,
    targets: List[Dict[str, Any]],
) -> bool:
    """True if seq meets all composition constraints (target ± tolerance, in %)."""
    if not targets:
        return True
    comp = calc_composition(seq)
    for t in targets:
        kind = t["type"]
        target_frac = t["target"] / 100.0
        tolerance_frac = t["tolerance"] / 100.0
        actual = comp.get(kind, 0.0)
        if abs(actual - target_frac) > tolerance_frac:
            return False
    return True



def segments_preview(segments: List[Dict[str, Any]]) -> str:
    """Readable preview string, e.g. 'R(84) + GGAGG + R(8) + AUG = 100 nt'."""
    parts = []
    total = 0
    for seg in segments:
        if seg["type"] == "random":
            length = seg["length"]
            parts.append(f"R({length})")
            total += length
        else:
            motif = seg["motif"]
            parts.append(motif)
            total += len(motif)
    return " + ".join(parts) + f" = {total} nt"


def segments_tag(segments: List[Dict[str, Any]]) -> str:
    """Short tag for FASTA headers, e.g. 'R84_GGAGG_R8_AUG'."""
    parts = []
    for seg in segments:
        if seg["type"] == "random":
            parts.append(f"R{seg['length']}")
        else:
            parts.append(seg["motif"])
    return "_".join(parts)



def generate_single_sequence(
    segments: List[Dict[str, Any]],
    rng: random.Random,
    targets: Optional[List[Dict[str, Any]]] = None,
    max_tries: int = 1000,
) -> Optional[str]:
    """Build one sequence from segments. Returns None if composition
    targets can't be met within max_tries."""
    for _ in range(max_tries):
        parts = []
        for seg in segments:
            if seg["type"] == "random":
                parts.append(random_region(seg["length"], rng))
            else:
                parts.append(resolve_iupac_motif(seg["motif"], rng))
        seq = "".join(parts)

        if check_composition_targets(seq, targets or []):
            return seq

    return None  # could not satisfy targets



def generate_pool(
    n: int,
    segments: List[Dict[str, Any]],
    output_file: str,
    *,
    targets: Optional[List[Dict[str, Any]]] = None,
    seed: Optional[int] = None,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Generate n sequences and write FASTA. Returns dict with total/written/failed/file."""
    rng = random.Random(seed)
    seg_tag = segments_tag(segments)

    written = 0
    failed = 0

    report_interval = max(1, n // 100)

    with open(output_file, "w") as fh:
        for i in range(n):
            seq = generate_single_sequence(segments, rng, targets)
            if seq is None:
                failed += 1
                continue

            written += 1
            comp = calc_composition(seq)
            header = (
                f">synth_pool_seq_{written}"
                f"|len={len(seq)}"
                f"|gc={comp['gc']:.3f}"
                f"|au={comp['au']:.3f}"
                f"|gu={comp['gu']:.3f}"
                f"|segments={seg_tag}"
            )
            fh.write(header + "\n")
            fh.write(seq + "\n")

            if progress_callback and (written % report_interval == 0 or i == n - 1):
                progress_callback(
                    i + 1, n,
                    f"Generated {written:,} / {n:,} sequences"
                    + (f" ({failed:,} filtered)" if failed else ""),
                )

    return {
        "total": n,
        "written": written,
        "failed": failed,
        "file": output_file,
    }


# Built-in presets
PRESETS: Dict[str, List[Dict[str, Any]]] = {
    "RBS + AUG": [
        {"type": "random", "length": 84},
        {"type": "fixed",  "motif": "GGAGG"},
        {"type": "random", "length": 8},
        {"type": "fixed",  "motif": "AUG"},
    ],
}
