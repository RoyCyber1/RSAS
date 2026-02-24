import os
import csv
import re
from pathlib import Path
from typing import List, Tuple, Optional


def read_fasta_simple(path: str, encoding: str = "utf-8") -> List[Tuple[str, str]]:
    """Simple FASTA parser: returns list of (header, sequence) tuples. Skips empty sequences."""
    sequences = []
    with open(path, "r", encoding=encoding) as f:
        header = None
        seq = ""
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header and seq:
                    sequences.append((header, seq))
                header = line[1:]  # remove '>'
                seq = ""
            else:
                seq += line.upper().replace("T", "U")  # RNA uses U, not T
        if header and seq:
            sequences.append((header, seq))
    return sequences



#CASHES PROGRAM PARSE FUNCTION
def parse_cash_out(path):
    """Parse ORF output file: returns list of (header, sequence) tuples"""
    sequences = []
    header = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("ORF found from"):
                # Extract position info as header
                header = line  # or parse it to get "ORF_0_1404" format
            elif line.startswith("Protein Sequence found"):
                seq = line[line.find(":")+1:].strip()
                if header:
                    sequences.append((header, seq))
                header = None
    return sequences



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


def read_fasta(path: str, convert_to_rna: bool = True, validate: bool = False) -> List[Tuple[str, str]]:
    """
    Parse a FASTA file and return list of (header, sequence) tuples
    Supports standard '>' and Unicode '›' '‹' header markers

    Args:
        path: Path to FASTA file
        convert_to_rna: If True, convert T to U (default: True)
        validate: If True, validate sequence characters (default: False)

    Returns:
        List of (header, sequence) tuples

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid or contains invalid characters
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    sequences = []
    header = None
    seq = ""
    HEADER_MARKERS = ['>', '›', '‹']  # Standard and Unicode variants

    with open(file_path, "r", encoding='utf-8') as f:  # Added UTF-8 encoding
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith(";"):
                continue

            # Check if line starts with any header marker
            is_header = any(line.startswith(marker) for marker in HEADER_MARKERS)

            if is_header:
                # Save previous sequence if exists
                if header is not None:
                    if seq:
                        # Optional validation BEFORE appending
                        if validate:
                            allowed = "ACGU" if convert_to_rna else "ACGT"
                            if not validate_sequence(seq, allowed):
                                invalid = set(seq.upper()) - set(allowed)
                                print(f"Warning: Invalid chars {invalid} in '{header}', skipping.")
                            else:
                                sequences.append((header, seq))
                        else:
                            sequences.append((header, seq))
                    else:
                        print(f"Warning: Empty sequence for header '{header}', skipping.")

                header = line[1:].strip()  # Remove first character (any marker) and whitespace
                seq = ""

            else:
                # Sequence line
                if header is None:
                    raise ValueError(
                        f"Line {line_num}: Sequence data found before header"
                    )
                cleaned = line.upper().replace(" ", "").replace("\t", "").replace("|", "")
                if convert_to_rna:
                    cleaned = cleaned.replace("T", "U")
                seq += cleaned

        # Don't forget the last sequence
        if header is not None:
            if seq:
                # Optional validation for last sequence
                if validate:
                    allowed = "ACGU" if convert_to_rna else "ACGT"
                    if not validate_sequence(seq, allowed):
                        invalid = set(seq.upper()) - set(allowed)
                        print(f"Warning: Invalid chars {invalid} in '{header}', skipping.")
                    else:
                        sequences.append((header, seq))
                else:
                    sequences.append((header, seq))
            else:
                print(f"Warning: Empty sequence for header '{header}', skipping.")

    if not sequences:
        raise ValueError(f"No sequences found in {path}")

    return sequences

def write_fasta(sequences: List[Tuple[str, str]], output_path: str,
                line_width: int = 80) -> None:
    """
    Write sequences to a FASTA file

    Args:
        sequences: List of (header, sequence) tuples
        output_path: Path to output file
        line_width: Maximum characters per line (default: 80)
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for header, sequence in sequences:
            f.write(f">{header}\n")
            # Write sequence in chunks
            for i in range(0, len(sequence), line_width):
                f.write(sequence[i:i + line_width] + '\n')



def get_sequence_stats(sequences: List[Tuple[str, str]]) -> dict:
    """
    Calculate basic statistics for parsed sequences

    Args:
        sequences: List of (header, sequence) tuples

    Returns:
        Dictionary with count, total_length, avg_length, min_length, max_length
    """
    if not sequences:
        return {
            'count': 0,
            'total_length': 0,
            'avg_length': 0,
            'min_length': 0,
            'max_length': 0
        }

    lengths = [len(seq) for _, seq in sequences]
    return {
        'count': len(sequences),
        'total_length': sum(lengths),
        'avg_length': sum(lengths) / len(lengths),
        'min_length': min(lengths),
        'max_length': max(lengths)
    }

_MIN_SEQ_LEN = 15

# Patterns that identify a "name" column header.
# Uses substring matching so CamelCase ("operonName") and prefixed ("1)geneName") work.
# Also includes common short-form headers that match as whole words.
_NAME_PATTERNS = re.compile(
    r"(?:name|identifier|accession|locus|label|operon|header|description|organism|gene)"
    r"|(?:^|\b)(?:id)(?:\b|$)",   # "id" only as a whole word
    re.IGNORECASE,
)

# Patterns that identify a "sequence" column header.
_SEQ_PATTERNS = re.compile(
    r"(?:sequence|nucleotide|mrna|5.?utr|3.?utr|cds|nt_?seq)"
    r"|(?:^|\b)(?:seq|dna|rna)(?:\b|$)",  # short forms only as whole words
    re.IGNORECASE,
)

# Columns that are definitely NOT sequences even though they might contain
# gene-like text (coordinates, strand, type info, etc.)
_SEQ_EXCLUSION = re.compile(
    r"(?:coordinate|position|strand|type|terminator|promoter|start|end|tss|left|right)",
    re.IGNORECASE,
)

# Valid nucleotide characters (after uppercasing)
_NUC_RE = re.compile(r"^[ACGTURYSWKMBDHVN]+$")


def _looks_like_sequence(cell: str) -> bool:
    """Return True if *cell* looks like a nucleotide sequence."""
    cleaned = cell.strip().upper().replace(" ", "").replace("|", "").replace("-", "")
    if len(cleaned) < _MIN_SEQ_LEN:
        return False
    if not _NUC_RE.match(cleaned):
        return False
    # Extra sanity: at least 80% must be ACGTU (not ambiguity codes)
    core = sum(1 for c in cleaned if c in "ACGTU")
    return core / len(cleaned) >= 0.80


def _detect_delimiter(lines: List[str]) -> str:
    """
    Detect the column delimiter used in *lines* (non-comment, non-blank).

    Candidates (in priority): ``||``, ``\\t``, ``,``, ``;``, ``|``.
    We pick the candidate that yields the most consistent (and largest)
    column count across the sample lines.
    """
    candidates = [
        ("||", "||"),
        ("\t", "\t"),
        (",",  ","),
        (";",  ";"),
        ("|",  "|"),
    ]
    best_delim = "\t"
    best_score = 0

    for _label, delim in candidates:
        counts = [len(line.split(delim)) for line in lines if line.strip()]
        if not counts:
            continue
        # Only consider delimiters that give ≥2 columns
        useful = [c for c in counts if c >= 2]
        if not useful:
            continue
        # Score = (median column count) * (fraction of rows with that count)
        from collections import Counter
        freq = Counter(useful)
        mode_count, mode_freq = freq.most_common(1)[0]
        consistency = mode_freq / len(useful)
        score = mode_count * consistency
        if score > best_score:
            best_score = score
            best_delim = delim

    return best_delim


def _find_header_and_columns(
    lines: List[str],
    delimiter: str,
) -> Tuple[int, Optional[int], Optional[int]]:
    """
    Scan *lines* for a header row containing recognisable column names.

    Returns ``(header_row_index, name_col_index, seq_col_index)``.
    If no header is found, returns ``(-1, None, None)``.
    """
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        cols = [c.strip() for c in line.split(delimiter)]
        if len(cols) < 2:
            continue

        name_candidates: List[int] = []
        seq_candidates: List[int] = []

        for ci, col_text in enumerate(cols):
            # Skip columns that look like coordinates / positional info
            if _SEQ_EXCLUSION.search(col_text):
                continue
            if _NAME_PATTERNS.search(col_text):
                name_candidates.append(ci)
            if _SEQ_PATTERNS.search(col_text):
                seq_candidates.append(ci)

        if seq_candidates:
            # Prefer the first sequence column found
            seq_col = seq_candidates[0]
            # For name, prefer a candidate that is NOT the same as seq_col
            name_col = None
            for nc in name_candidates:
                if nc != seq_col:
                    name_col = nc
                    break
            # If no separate name column, use column 0 if it's not the seq column
            if name_col is None and seq_col != 0:
                name_col = 0
            return idx, name_col, seq_col

    return -1, None, None


def _find_first_data_row(
    lines: List[str],
    delimiter: str,
) -> Tuple[int, Optional[int], Optional[int]]:
    """
    Fallback: scan lines for the first row that contains a cell looking
    like a nucleotide sequence.  Returns ``(row_index, name_col, seq_col)``.
    Assumes column 0 is the name if a sequence is found elsewhere.
    """
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        cols = [c.strip() for c in line.split(delimiter)]
        for ci, cell in enumerate(cols):
            if _looks_like_sequence(cell):
                name_col = 0 if ci != 0 else (1 if len(cols) > 1 else None)
                return idx, name_col, ci
    return -1, None, None


def read_csv_tsv_sequences(
    path: str,
    skip_rows: int = -1,
    name_col: int = -1,
    seq_col: int = -1,
    convert_to_rna: bool = True,
) -> List[Tuple[str, str]]:
    """
    Smart CSV/TSV parser with automatic detection of:
      - delimiter (tab, comma, semicolon, pipe, double-pipe)
      - header row (by scanning for column names like "sequence", "name", etc.)
      - sequence & name columns (by header keywords or by content heuristics)

    When *skip_rows*, *name_col*, or *seq_col* are **-1** (the default),
    the corresponding value is auto-detected.  Explicit values override
    auto-detection for that parameter only.

    Args:
        path:           Path to the CSV / TSV file.
        skip_rows:      Rows to skip before data (-1 = auto-detect).
        name_col:       Column index for names (-1 = auto-detect).
        seq_col:        Column index for sequences (-1 = auto-detect).
        convert_to_rna: If True, convert T → U.

    Returns:
        List of (name, sequence) tuples.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # ── Read all lines (for sniffing) ──────────────────────────────────
    with open(file_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    if not all_lines:
        raise ValueError(f"File is empty: {path}")

    # Strip trailing whitespace / newlines but keep content
    raw_lines = [ln.rstrip("\n\r") for ln in all_lines]

    # ── Filter out comment / blank lines for sniffing ──────────────────
    sniff_lines = [ln for ln in raw_lines if ln.strip() and not ln.lstrip().startswith("#")]
    if not sniff_lines:
        raise ValueError(f"No data lines found in {path} (all lines are comments or blank)")

    # ── Step 1: Detect delimiter ──────────────────────────────────────
    delimiter = _detect_delimiter(sniff_lines[:50])

    # ── Step 2: Detect header / column positions ──────────────────────
    auto_skip = -1
    auto_name = None
    auto_seq = None

    hdr_idx, hdr_name, hdr_seq = _find_header_and_columns(raw_lines, delimiter)
    if hdr_idx >= 0 and hdr_seq is not None:
        # Header found — data starts on the next non-comment line after header
        auto_skip = hdr_idx + 1
        auto_name = hdr_name
        auto_seq = hdr_seq
    else:
        # No header recognised — fall back to content-based detection
        data_idx, det_name, det_seq = _find_first_data_row(raw_lines, delimiter)
        if data_idx >= 0 and det_seq is not None:
            auto_skip = data_idx  # data starts on this line
            auto_name = det_name
            auto_seq = det_seq

    # ── Apply overrides (explicit params win over auto) ────────────────
    final_skip = skip_rows if skip_rows >= 0 else (auto_skip if auto_skip >= 0 else 0)
    final_seq  = seq_col   if seq_col  >= 0 else (auto_seq  if auto_seq  is not None else 0)
    final_name = name_col  if name_col >= 0 else (auto_name if auto_name is not None else 0)

    # ── Step 3: Parse data rows ───────────────────────────────────────
    sequences: List[Tuple[str, str]] = []
    unnamed_counter = 0

    for row_idx, line in enumerate(raw_lines):
        if row_idx < final_skip:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        cols = line.split(delimiter)

        # Ensure row has enough columns
        required = max(final_name, final_seq) + 1
        if len(cols) < required:
            continue

        # Extract name
        raw_name = cols[final_name].strip() if final_name is not None else ""
        # Extract sequence
        raw_seq = cols[final_seq].strip() if final_seq is not None else ""

        if not raw_seq or raw_seq.lower() in ("none", "null", "na", "n/a", ""):
            continue

        # Clean sequence: remove pipes, spaces, dashes
        seq = raw_seq.upper().replace("|", "").replace(" ", "").replace("\t", "").replace("-", "")
        if convert_to_rna:
            seq = seq.replace("T", "U")

        # Validate it's actually a nucleotide sequence (at least mostly)
        if len(seq) < 4:
            continue
        nuc_chars = sum(1 for c in seq if c in "ACGTURYSWKMBDHVN")
        if nuc_chars / len(seq) < 0.80:
            continue

        # Generate name if empty
        if not raw_name or raw_name.lower() in ("none", "null", "na", "n/a"):
            unnamed_counter += 1
            raw_name = f"seq_{unnamed_counter}"

        sequences.append((raw_name, seq))

    if not sequences:
        raise ValueError(
            f"No sequences found in {path}.\n"
            f"  Auto-detected: delimiter={'TAB' if delimiter == chr(9) else repr(delimiter)}, "
            f"skip_rows={final_skip}, name_col={final_name}, seq_col={final_seq}.\n"
            f"  If this looks wrong, check your file format."
        )

    return sequences


def read_two_column(
    path: str,
    convert_to_rna: bool = True,
    delimiter: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """
    Parse a two-column text file (name and sequence per line).
    Common in genomics pipelines. Lines are: name TAB sequence or name WHITESPACE sequence.

    Args:
        path: Path to the file.
        convert_to_rna: If True, convert T to U.
        delimiter: If set, split each line on this (e.g. '\\t'). If None, split on first tab or first run of whitespace.

    Returns:
        List of (name, sequence) tuples.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    sequences = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if delimiter is not None:
                parts = line.split(delimiter, 1)
            else:
                if "\t" in line:
                    parts = line.split("\t", 1)
                else:
                    parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            name = parts[0].strip()
            raw = parts[1].strip().replace(" ", "").replace("\t", "").replace("|", "").upper()
            if convert_to_rna:
                raw = raw.replace("T", "U")
            if name and raw:
                sequences.append((name, raw))

    if not sequences:
        raise ValueError(f"No name/sequence pairs found in {path}")

    return sequences


def read_genbank(path: str, convert_to_rna: bool = True) -> List[Tuple[str, str]]:
    """
    Parse a GenBank file and return list of (record_id, sequence) tuples.
    Requires Biopython: pip install biopython

    Args:
        path: Path to .gb or .gbk file.
        convert_to_rna: If True, convert T to U in sequence.    Returns:
        List of (name, sequence) tuples.
    """
    try:
        from Bio import SeqIO
    except ImportError:
        raise ImportError(
            "GenBank support requires biopython. Install with: pip install biopython"
        ) from None

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    sequences = []
    with open(file_path, "r", encoding="utf-8") as f:
        for record in SeqIO.parse(f, "genbank"):
            name = record.id or record.name or f"record_{len(sequences)}"
            seq = str(record.seq).upper().replace(" ", "").replace("\t", "").replace("|", "")
            if convert_to_rna:
                seq = seq.replace("T", "U")
            if seq:
                sequences.append((name, seq))

    if not sequences:
        raise ValueError(f"No sequences found in GenBank file {path}")

    return sequences


def load_sequences(
    path: str,
    convert_to_rna: bool = True,
    validate_fasta: bool = False,
    csv_skip_rows: int = -1,
    csv_seq_col: int = -1,
    csv_name_col: int = -1,
) -> List[Tuple[str, str]]:
    """
    Load name/sequence pairs from a file. Format is chosen by extension.

    Supported extensions:
        .fa, .fasta -> FASTA
        .csv        -> CSV  (auto-detects header, delimiter, name/seq columns)
        .tsv        -> TSV  (auto-detects header, delimiter, name/seq columns)
        .txt        -> Two-column text (name and sequence per line)
        .gb, .gbk   -> GenBank (requires biopython)

    Args:
        path: Path to the file.
        convert_to_rna: If True, convert T to U (default True).
        validate_fasta: If True, validate FASTA sequences and skip invalid (only for FASTA).
        csv_skip_rows: Rows to skip for CSV/TSV (-1 = auto-detect).
        csv_seq_col: Sequence column index for CSV/TSV (-1 = auto-detect).
        csv_name_col: Name column index for CSV/TSV (-1 = auto-detect).

    Returns:
        List of (name, sequence) tuples.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If extension is not supported or no sequences found.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = p.suffix.lower()
    if ext in (".fa", ".fasta"):
        return read_fasta(path, convert_to_rna=convert_to_rna, validate=validate_fasta)
    if ext in (".csv", ".tsv"):
        return read_csv_tsv_sequences(
            path,
            skip_rows=csv_skip_rows,
            name_col=csv_name_col,
            seq_col=csv_seq_col,
            convert_to_rna=convert_to_rna,
        )
    if ext == ".txt":
        return read_two_column(path, convert_to_rna=convert_to_rna)
    if ext in (".gb", ".gbk"):
        return read_genbank(path, convert_to_rna=convert_to_rna)

    raise ValueError(
        f"Unsupported file type: '{ext}'. "
        "Supported: .fasta, .fa, .csv, .tsv, .txt (two-column), .gb, .gbk (GenBank; requires biopython)."
    )