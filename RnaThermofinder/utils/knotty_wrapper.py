"""
Knotty wrapper — subprocess interface for pseudoknot prediction.

Calls the Knotty CLI binary to predict RNA secondary structures
including pseudoknots, then parses the results back into Python.

Knotty uses the DP09 energy model from HotKnots V2.0.
Reference: Jabbari et al. (2018), Bioinformatics 34(22):3849-3856.

CLI usage:  ./knotty <SEQUENCE>       (full output)
            ./knotty -w <SEQUENCE>    (minimal: structure + energy only)

Build from source (requires CMake 3.1+, C++11):
    git clone https://github.com/HosnaJabbari/Knotty.git
    cd Knotty
    cmake -H. -Bbuild
    cmake --build build
    # Binary: build/knotty

Place compiled binary in bin/<platform>/knotty (or knotty.exe on Windows).
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple


# Defence-in-depth: max sequence length enforced at wrapper level.
# GUI also enforces this, but direct callers should be protected too.
MAX_SEQUENCE_LENGTH = 2000

# ---------------------------------------------------------------------------
# Binary resolution
# ---------------------------------------------------------------------------

def _get_knotty_binary() -> Path:
    """Find the knotty binary. Checks frozen bundle, project bin/, then PATH."""
    system = platform.system().lower()
    binary_name = "knotty.exe" if system == "windows" else "knotty"

    # 1. PyInstaller bundle
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidate = base / "bin" / binary_name
        if candidate.is_file():
            return candidate

    # 2. Project bin/<platform>/
    project_root = Path(__file__).resolve().parent.parent.parent
    platform_dir = {"darwin": "macos", "linux": "linux", "windows": "windows"}.get(system, system)
    candidate = project_root / "bin" / platform_dir / binary_name
    if candidate.is_file():
        return candidate

    # 3. System PATH
    found = shutil.which("knotty")
    if found:
        return Path(found)

    raise FileNotFoundError(
        f"Knotty binary not found. Expected at {candidate} or on system PATH.\n"
        f"Build from source: https://github.com/HosnaJabbari/Knotty"
    )


def check_knotty_available() -> Tuple[bool, str]:
    """Check if Knotty is installed. Returns (available, message)."""
    try:
        binary = _get_knotty_binary()
        if not os.access(binary, os.X_OK):
            os.chmod(binary, os.stat(binary).st_mode | stat.S_IEXEC)
        return True, str(binary)
    except FileNotFoundError as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Result data structure
# ---------------------------------------------------------------------------

@dataclass
class KnottyResult:
    """Result from a single Knotty prediction."""
    seq_name: str = ""
    sequence: str = ""
    structure: str = ""
    energy: float = 0.0
    has_pseudoknot: bool = False
    raw_stdout: str = ""
    raw_stderr: str = ""
    return_code: int = 0
    error: str = ""


# ---------------------------------------------------------------------------
# Run + parse
# ---------------------------------------------------------------------------

def _parse_knotty_output(stdout: str) -> Tuple[str, float, bool]:
    """Parse Knotty output to extract structure, energy, and pseudoknot status.

    Knotty output (with -w flag) is minimal: structure and energy.
    Without -w, there may be additional diagnostic lines.

    Returns (structure, energy, has_pseudoknot).
    """
    structure = ""
    energy = 0.0

    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # Knotty -w output: "...(((...)))... -2.32" (structure + energy on one line)
        # Also handle structure-only or energy-only lines.
        match = re.match(r'([.()\[\]{}<>]+)\s+(-?\d+\.?\d*)', line)
        if match:
            structure = match.group(1)
            energy = float(match.group(2))
            continue

        # Standalone dot-bracket structure line
        if re.fullmatch(r'[.()\[\]{}<>]+', line):
            structure = line
            continue

        # Standalone energy value (line containing only a number)
        if re.fullmatch(r'\s*-?\d+\.?\d*\s*', line):
            try:
                energy = float(line.strip())
            except ValueError:
                pass

    # Pseudoknot detection: [] = first crossing level, {} = second, <> = third
    has_pseudoknot = bool(re.search(r'[\[\]{}<>]', structure))

    return structure, energy, has_pseudoknot


def run_knotty(
    sequence: str,
    seq_name: str = "",
    *,
    timeout: int = 120,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> KnottyResult:
    """Run Knotty on a single RNA sequence.

    Args:
        sequence: RNA sequence (ACGU). T is auto-converted to U.
        seq_name: Optional name for the sequence.
        timeout: Max seconds to wait (default 120).
        progress_callback: Optional logging callback.

    Returns:
        KnottyResult with predicted structure, energy, and pseudoknot flag.
    """
    binary = _get_knotty_binary()

    # Ensure executable
    if not os.access(binary, os.X_OK):
        os.chmod(binary, os.stat(binary).st_mode | stat.S_IEXEC)

    # RNA conversion — Knotty expects ACGU
    # NOTE: When adapting for DNA, this conversion should be made conditional
    upper_seq = sequence.upper()
    t_count = upper_seq.count("T")
    clean_seq = upper_seq.replace("T", "U")

    # Warn about IUPAC ambiguity codes before stripping
    iupac_chars = set(re.findall(r'[RYSWKMBDHVN]', clean_seq))
    iupac_count = len(re.findall(r'[RYSWKMBDHVN]', clean_seq))

    # Strip non-nucleotide characters
    clean_seq = re.sub(r'[^ACGU]', '', clean_seq)

    if not clean_seq:
        return KnottyResult(
            seq_name=seq_name, sequence=sequence,
            error="Empty sequence after cleaning",
        )

    if len(clean_seq) > MAX_SEQUENCE_LENGTH:
        return KnottyResult(
            seq_name=seq_name, sequence=clean_seq,
            error=f"Sequence too long ({len(clean_seq)} nt, max {MAX_SEQUENCE_LENGTH})",
        )

    if progress_callback:
        if t_count:
            progress_callback(f"  Converted {t_count} T→U for RNA folding")
        if iupac_count:
            progress_callback(
                f"  Warning: removed {iupac_count} ambiguous bases "
                f"({', '.join(sorted(iupac_chars))}) from {seq_name or 'sequence'}"
            )

    cmd = [str(binary), clean_seq, "-w"]

    # Knotty loads energy parameters from simfold/params/ relative to cwd,
    # or from $CONDA_PREFIX/share/simfold/params/. We cd to the binary's
    # directory (where we placed the params) and unset CONDA_PREFIX to
    # ensure the relative path is used.
    bin_dir = str(binary.parent)
    env = dict(os.environ)
    env.pop("CONDA_PREFIX", None)

    if progress_callback:
        progress_callback(f"Running Knotty on {seq_name or 'sequence'} ({len(clean_seq)} nt)")

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=bin_dir, env=env,
        )

        if proc.returncode != 0:
            return KnottyResult(
                seq_name=seq_name, sequence=clean_seq,
                raw_stdout=proc.stdout, raw_stderr=proc.stderr,
                return_code=proc.returncode,
                error=f"Knotty exited with code {proc.returncode}: {proc.stderr.strip()}",
            )

        structure, energy, has_pk = _parse_knotty_output(proc.stdout)

        return KnottyResult(
            seq_name=seq_name,
            sequence=clean_seq,
            structure=structure,
            energy=energy,
            has_pseudoknot=has_pk,
            raw_stdout=proc.stdout,
            raw_stderr=proc.stderr,
            return_code=proc.returncode,
        )

    except subprocess.TimeoutExpired:
        return KnottyResult(
            seq_name=seq_name, sequence=clean_seq,
            error=f"Timed out after {timeout}s (sequence may be too long)",
        )
    except Exception as e:
        return KnottyResult(
            seq_name=seq_name, sequence=clean_seq,
            error=str(e),
        )


def run_knotty_batch(
    sequences: List[Tuple[str, str]],
    *,
    timeout: int = 120,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_event: Optional["threading.Event"] = None,
) -> List[KnottyResult]:
    """Run Knotty on multiple sequences.

    Args:
        sequences: List of (name, sequence) tuples.
        timeout: Max seconds per sequence.
        progress_callback: Called with (current, total) for progress updates.
        log_callback: Called with log messages.
        cancel_event: Optional threading.Event; if set, stops the batch early.

    Returns:
        List of KnottyResult objects (may be partial if cancelled).
    """
    import threading as _threading
    results: List[KnottyResult] = []
    total = len(sequences)

    for i, (name, seq) in enumerate(sequences):
        if cancel_event is not None and cancel_event.is_set():
            if log_callback:
                log_callback(f"Cancelled after {i}/{total} sequences")
            break

        result = run_knotty(
            seq, seq_name=name, timeout=timeout,
            progress_callback=log_callback,
        )
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, total)

    return results
