import os
import csv
from pathlib import Path
from typing import List, Tuple

fasta_path = "/Users/royvaknin/PycharmProjects/RNAThermoFinder/Data/Inputs/bly.fasta"





def read_fasta_simple(path):
    """Simple FASTA parser: returns list of (header, sequence) tuples"""
    sequences = []
    with open(path, "r") as f:
        header = None
        seq = ""
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header:
                    sequences.append((header, seq))
                header = line[1:]  # remove '>'
                seq = ""
            else:
                seq += line.upper().replace("T", "U")  # RNA uses U, not T
        if header:
            sequences.append((header, seq))
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
                                print(f"Warning: Invalid Chars '{header}', skipping.")
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
                        print(f"Warning: Invalid Chars '{header}', skipping.")
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
    with open(output_path, 'w') as f:
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




def read_csv_tsv_sequences(
        path: str,
        skip_rows: int = 30,
        name_col: int = 0,
        seq_col: int = 10,
        convert_to_rna: bool = True
) -> List[Tuple[str, str]]:
    """
    Parse a CSV or TSV file containing sequences.

    Args:
        path: Path to the file.
        skip_rows: Number of initial rows to skip (metadata/license info).
        name_col: Column index for sequence names (0-indexed).
        seq_col: Column index for sequences (0-indexed).
        convert_to_rna: If True, convert T to U.

    Returns:
        List of (name, sequence) tuples with cleaned sequences.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Determine delimiter based on extension
    delimiter = "\t" if path.lower().endswith(".tsv") else ","

    sequences = []

    with open(file_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=delimiter)

        # Skip header rows
        for _ in range(skip_rows):
            try:
                next(reader)
            except StopIteration:
                break

        # Read data rows
        for row_num, row in enumerate(reader, start=skip_rows + 1):
            # Check if row has enough columns
            if len(row) <= max(name_col, seq_col):
                continue  # Skip incomplete rows

            try:
                name = row[name_col].strip()
                seq = row[seq_col]

                # Clean sequence
                seq = seq.replace("|", "").replace(" ", "").replace("\t", "").upper()

                # Convert to RNA if requested
                if convert_to_rna:
                    seq = seq.replace("T", "U")

                # Only add non-empty sequences
                if name and seq:
                    sequences.append((name, seq))

            except IndexError:
                print(f"Warning: Row {row_num} has insufficient columns, skipping.")
                continue

    if not sequences:
        raise ValueError(f"No sequences found in {path}")

    return sequences


