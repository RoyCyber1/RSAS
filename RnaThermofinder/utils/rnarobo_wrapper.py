"""
RNArobo wrapper — subprocess interface and output parser.

Calls the rnarobo CLI binary to search for structural RNA motifs
in FASTA sequences, then parses the results back into Python.

Descriptor format (from RNArobo 2.1.0 guide):
  - Helix (h):  h1 mismatches:mispairs pos_strand:neg_strand
                 h1 mismatches:mispairs:insertions pos_strand:neg_strand:insert_nuc
  - Single (s): s1 mismatches sequence
                 s1 mismatches:insertions sequence:insert_nuc
  - Relational (r): like helix but with a transformation string
                 r1 mismatches:mispairs pos_strand:neg_strand transform
                 r1 mismatches:mispairs:insertions pos_strand:neg_strand:insert_nuc transform
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Binary resolution
# ---------------------------------------------------------------------------

def _get_rnarobo_binary() -> Path:
    """Find the rnarobo binary. Checks frozen bundle, project bin/, then PATH."""
    system = platform.system().lower()
    binary_name = "rnarobo.exe" if system == "windows" else "rnarobo"

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
    found = shutil.which("rnarobo")
    if found:
        return Path(found)

    raise FileNotFoundError(
        f"rnarobo binary not found. Expected at {candidate} or on system PATH."
    )


def check_rnarobo_available() -> Tuple[bool, str]:
    """Check if rnarobo is installed. Returns (available, message)."""
    try:
        binary = _get_rnarobo_binary()
        if not os.access(binary, os.X_OK):
            os.chmod(binary, os.stat(binary).st_mode | stat.S_IEXEC)
        return True, str(binary)
    except FileNotFoundError as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Descriptor data structures
# ---------------------------------------------------------------------------

@dataclass
class HelixElement:
    """A helix (h) element — paired stem with positive and negative strands.

    Format: h1 mismatches:mispairs pos_strand:neg_strand
    With insertions: h1 mismatches:mispairs:insertions pos:neg:insert_nuc
    Default pairing allows G-U wobble (transformation = TGYR).
    """
    name: str                   # e.g. "h1"
    mismatches: int = 0         # mismatches in positive strand
    mispairs: int = 0           # allowed mispairs in helix
    pos_strand: str = ""        # e.g. "NNN**CC"
    neg_strand: str = ""        # e.g. "GG**NNN"
    insertions: int = 0         # max single-nucleotide insertions
    insertion_nuc: str = ""     # IUPAC code for allowed insertions (e.g. "A")


@dataclass
class SingleStrandedElement:
    """A single-stranded (s) element.

    Format: s1 mismatches sequence
    With insertions: s1 mismatches:insertions sequence:insert_nuc
    """
    name: str                   # e.g. "s1"
    mismatches: int = 0
    sequence: str = ""          # e.g. "ACCRNNT", wildcards * allowed
    insertions: int = 0
    insertion_nuc: str = ""     # e.g. "Y" (pyrimidine)


@dataclass
class RelationalElement:
    """A relational (r) element — like a helix but with custom pairing rules.

    Format: r1 mismatches:mispairs pos_strand:neg_strand transform
    The transform string (e.g. "TGCA") defines what pairs with A, C, G, T
    in that order. Default helix uses "TGYR" (allows G-U wobble).
    "TGCA" restricts to canonical Watson-Crick pairs only.
    """
    name: str                   # e.g. "r1"
    mismatches: int = 0
    mispairs: int = 0
    pos_strand: str = ""
    neg_strand: str = ""
    insertions: int = 0
    insertion_nuc: str = ""
    transform: str = "TGCA"     # pairing rules: what pairs with A, C, G, T


@dataclass
class DescriptorSpec:
    """Complete RNArobo descriptor (motif map + element specs)."""
    motif_map: str = ""
    elements: List[Any] = field(default_factory=list)

    def to_descriptor_text(self) -> str:
        """Generate the descriptor file content for rnarobo."""
        lines = [self.motif_map, ""]
        for elem in self.elements:
            lines.append(_format_element(elem))
        return "\n".join(lines) + "\n"


def _format_element(elem) -> str:
    """Format a single element into its descriptor line."""
    if isinstance(elem, HelixElement):
        # Build mismatch spec: mismatches:mispairs or mismatches:mispairs:insertions
        mm_spec = f"{elem.mismatches}:{elem.mispairs}"
        if elem.insertions > 0:
            mm_spec += f":{elem.insertions}"

        # Build sequence spec: pos_strand:neg_strand or pos:neg:insert_nuc
        pos = elem.pos_strand if elem.pos_strand else "NNNN"
        neg = elem.neg_strand if elem.neg_strand else "NNNN"
        seq_spec = f"{pos}:{neg}"
        if elem.insertions > 0 and elem.insertion_nuc:
            seq_spec += f":{elem.insertion_nuc}"

        return f"{elem.name} {mm_spec} {seq_spec}"

    elif isinstance(elem, RelationalElement):
        # Same as helix but with transform string appended
        mm_spec = f"{elem.mismatches}:{elem.mispairs}"
        if elem.insertions > 0:
            mm_spec += f":{elem.insertions}"

        pos = elem.pos_strand if elem.pos_strand else "NNNN"
        neg = elem.neg_strand if elem.neg_strand else "NNNN"
        seq_spec = f"{pos}:{neg}"
        if elem.insertions > 0 and elem.insertion_nuc:
            seq_spec += f":{elem.insertion_nuc}"

        transform = elem.transform if elem.transform else "TGCA"
        return f"{elem.name} {mm_spec} {seq_spec} {transform}"

    elif isinstance(elem, SingleStrandedElement):
        # Build mismatch spec: mismatches or mismatches:insertions
        mm_spec = str(elem.mismatches)
        if elem.insertions > 0:
            mm_spec += f":{elem.insertions}"

        # Build sequence spec: sequence or sequence:insert_nuc
        seq = elem.sequence if elem.sequence else "N***"
        seq_spec = seq
        if elem.insertions > 0 and elem.insertion_nuc:
            seq_spec += f":{elem.insertion_nuc}"

        return f"{elem.name} {mm_spec} {seq_spec}"

    return ""


@dataclass
class RNAroboMatch:
    """One match from rnarobo output."""
    seq_name: str = ""
    description: str = ""
    seq_from: int = 0
    seq_to: int = 0
    is_reverse: bool = False
    elements: str = ""       # pipe-delimited matched elements


@dataclass
class RNAroboResult:
    """Full result set from an rnarobo run."""
    matches: List[RNAroboMatch] = field(default_factory=list)
    total_matches: int = 0
    total_bases: int = 0
    raw_stdout: str = ""
    raw_stderr: str = ""
    return_code: int = 0


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

RNAROBO_PRESETS: Dict[str, DescriptorSpec] = {
    "Simple Hairpin": DescriptorSpec(
        motif_map="h1 s1 h1'",
        elements=[
            HelixElement(name="h1", mismatches=1, mispairs=0,
                         pos_strand="NNN**CC", neg_strand="GG**NNN"),
            SingleStrandedElement(name="s1", mismatches=0, sequence="NNN***"),
        ],
    ),
    "Hairpin with Insertions": DescriptorSpec(
        motif_map="h1 s1 h1'",
        elements=[
            HelixElement(name="h1", mismatches=0, mispairs=0,
                         pos_strand="NNN**CC", neg_strand="GG**NNN",
                         insertions=2, insertion_nuc="A"),
            SingleStrandedElement(name="s1", mismatches=0, sequence="ACCRNNT",
                                  insertions=1, insertion_nuc="Y"),
        ],
    ),
    "Two-Stem Junction": DescriptorSpec(
        motif_map="h1 s1 h2 s2 h2' s3 h1'",
        elements=[
            HelixElement(name="h1", mismatches=0, mispairs=0,
                         pos_strand="NNNN", neg_strand="NNNN"),
            SingleStrandedElement(name="s1", mismatches=0, sequence="N***"),
            HelixElement(name="h2", mismatches=0, mispairs=0,
                         pos_strand="NNN", neg_strand="NNN"),
            SingleStrandedElement(name="s2", mismatches=0, sequence="NNN***"),
            SingleStrandedElement(name="s3", mismatches=0, sequence="N***"),
        ],
    ),
    "Relational (canonical only)": DescriptorSpec(
        motif_map="r1 s1 r1'",
        elements=[
            RelationalElement(name="r1", mismatches=0, mispairs=0,
                              pos_strand="NNN**CC", neg_strand="GG**NNN",
                              transform="TGCA"),
            SingleStrandedElement(name="s1", mismatches=0, sequence="NNN***"),
        ],
    ),
    "RNA Thermometer (3-stem)": DescriptorSpec(
        motif_map="h1 s1 h2 s2 h2' s3 h3 s4 h3' h1'",
        elements=[
            HelixElement(name="h1", mismatches=1, mispairs=0,
                         pos_strand="NNNNNN", neg_strand="NNNNNN"),
            SingleStrandedElement(name="s1", mismatches=0, sequence="NN***"),
            HelixElement(name="h2", mismatches=0, mispairs=0,
                         pos_strand="NNNN", neg_strand="NNNN"),
            SingleStrandedElement(name="s2", mismatches=0, sequence="NNN***"),
            SingleStrandedElement(name="s3", mismatches=0, sequence="N***"),
            HelixElement(name="h3", mismatches=0, mispairs=0,
                         pos_strand="NNN", neg_strand="NNN"),
            SingleStrandedElement(name="s4", mismatches=0, sequence="NNN***"),
        ],
    ),
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_descriptor(descriptor: DescriptorSpec) -> Optional[str]:
    """Validate a descriptor spec. Returns error message or None if valid."""
    if not descriptor.motif_map.strip():
        return "Motif map cannot be empty."

    tokens = descriptor.motif_map.strip().split()
    defined = {e.name for e in descriptor.elements}

    for token in tokens:
        base = token.rstrip("'")
        if base not in defined:
            return f"Element '{base}' is in the motif map but has no specification."

    # Primed elements must reference a helix or relational element
    for token in tokens:
        if token.endswith("'"):
            base = token.rstrip("'")
            elem = next((e for e in descriptor.elements if e.name == base), None)
            if elem and isinstance(elem, SingleStrandedElement):
                return f"Primed element '{token}' requires '{base}' to be a helix (h) or relational (r)."

    # Element names must start with the correct type prefix.
    # RNArobo uses the FIRST CHARACTER of the element name to determine its type:
    #   h → helix, s → single-stranded, r → relational
    # A helix named "stem1" would silently be treated as single-stranded (starts with 's'),
    # producing scientifically incorrect motif matches with no error from rnarobo.
    _required_prefix: Dict[type, str] = {
        HelixElement: "h",
        SingleStrandedElement: "s",
        RelationalElement: "r",
    }
    _type_label: Dict[type, str] = {
        HelixElement: "helix (h)",
        SingleStrandedElement: "single-stranded (s)",
        RelationalElement: "relational (r)",
    }
    for elem in descriptor.elements:
        if not elem.name:
            return "All elements must have a name."
        prefix = _required_prefix.get(type(elem))
        if prefix and not elem.name.startswith(prefix):
            label = _type_label.get(type(elem), type(elem).__name__)
            return (
                f"Element '{elem.name}' is a {label} element but its name does not start "
                f"with '{prefix}'. RNArobo uses the first character to determine element "
                f"type — rename it to something like '{prefix}1'."
            )

    # Numeric constraints must be non-negative
    for elem in descriptor.elements:
        if elem.mismatches < 0:
            return f"Element '{elem.name}': mismatches must be ≥ 0 (got {elem.mismatches})."
        if isinstance(elem, (HelixElement, RelationalElement)) and elem.mispairs < 0:
            return f"Element '{elem.name}': mispairs must be ≥ 0 (got {elem.mispairs})."
        if elem.insertions < 0:
            return f"Element '{elem.name}': insertions must be ≥ 0 (got {elem.insertions})."

    # Single-stranded elements: wildcard (*) must not be flanked by nucleotides
    # on both sides (e.g. N*N, ACG*UU). RNArobo performs exponential backtracking
    # on such patterns and the search will hang or fail.
    for elem in descriptor.elements:
        if not isinstance(elem, SingleStrandedElement):
            continue
        seq = elem.sequence
        if '*' not in seq:
            continue
        first_star = seq.index('*')
        last_star = len(seq) - 1 - seq[::-1].index('*')
        has_before = first_star > 0          # characters before first *
        has_after = last_star < len(seq) - 1  # characters after last *
        if has_before and has_after:
            return (
                f"Single-stranded element '{elem.name}': the wildcard (*) cannot have "
                f"nucleotides on both sides (e.g. 'N*N'). "
                f"Place * only at the start or end of the sequence (e.g. 'NNN*' or '*NNN'), "
                f"or use * alone to match any loop length."
            )

    return None


# ---------------------------------------------------------------------------
# Run + parse
# ---------------------------------------------------------------------------

def run_rnarobo(
    descriptor: DescriptorSpec,
    sequence_file: str,
    *,
    both_strands: bool = True,
    non_overlapping: bool = False,
    fasta_output: bool = False,
    nratio: Optional[float] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> RNAroboResult:
    """Run rnarobo on a FASTA file with the given descriptor.

    Writes a temp descriptor file, invokes the binary, parses output.
    """
    binary = _get_rnarobo_binary()

    # Make sure it's executable
    if not os.access(binary, os.X_OK):
        os.chmod(binary, os.stat(binary).st_mode | stat.S_IEXEC)

    desc_text = descriptor.to_descriptor_text()
    if progress_callback:
        progress_callback(f"Descriptor:\n{desc_text}")

    # Write descriptor to temp file
    fd, desc_path = tempfile.mkstemp(suffix=".desc", prefix="rnarobo_")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(desc_text)

        cmd = [str(binary)]
        if both_strands:
            cmd.append("-c")
        if non_overlapping:
            cmd.append("-u")
        if fasta_output:
            cmd.append("-f")
        if nratio is not None:
            cmd.extend(["--nratio", str(nratio)])
        cmd.extend([desc_path, sequence_file])

        if progress_callback:
            progress_callback(f"Running: {' '.join(cmd)}")

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )

        if progress_callback:
            progress_callback(f"rnarobo exited with code {proc.returncode}")

        matches, total_bases = _parse_rnarobo_output(proc.stdout)

        return RNAroboResult(
            matches=matches,
            total_matches=len(matches),
            total_bases=total_bases,
            raw_stdout=proc.stdout,
            raw_stderr=proc.stderr,
            return_code=proc.returncode,
        )

    finally:
        try:
            os.unlink(desc_path)
        except OSError:
            pass


def _parse_rnarobo_output(stdout: str) -> Tuple[List[RNAroboMatch], int]:
    """Parse rnarobo's default tabular output.

    Format:
      Header block (Starting rnarobo... dashes... settings)
      Match block:
        seq-f  seq-t  name  description
        |elem1|elem2|...|
      Footer: ----- SEARCH DONE -----
    """
    matches: List[RNAroboMatch] = []
    total_bases = 0
    lines = stdout.splitlines()

    # Find the data section (after the column header separator)
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("-------"):
            i += 1
            break
        i += 1

    # Parse matches: alternating position-line + element-line
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("----- SEARCH DONE"):
            # Parse footer for stats
            for j in range(i, len(lines)):
                fl = lines[j].strip()
                if fl.startswith("Total bases scanned:"):
                    try:
                        total_bases = int(fl.split(":")[-1].strip())
                    except ValueError:
                        pass
            break

        if not line:
            i += 1
            continue

        # Position line: seq-f  seq-t  name  description
        parts = line.split()
        if len(parts) >= 3:
            try:
                seq_f = int(parts[0])
                seq_t = int(parts[1])
                name = parts[2] if len(parts) >= 3 else ""
                desc = " ".join(parts[3:]) if len(parts) > 3 else ""

                # Next line should be the pipe-delimited elements
                elements_str = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith("|"):
                        elements_str = next_line
                        i += 1

                matches.append(RNAroboMatch(
                    seq_name=name,
                    description=desc,
                    seq_from=seq_f,
                    seq_to=seq_t,
                    is_reverse=(seq_f > seq_t),
                    elements=elements_str,
                ))
            except ValueError:
                pass  # not a data line

        i += 1

    return matches, total_bases
