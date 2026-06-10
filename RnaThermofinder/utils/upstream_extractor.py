"""
Sequence Extractor for RSAS: RNA Structure Analysis Suite
Extracts upstream, downstream, or flanking sequences from genes
using GenBank annotations and genome FASTA.

Supports three extraction directions:
  - upstream:   N bases before the CDS start (promoter/5' UTR region)
  - downstream: N bases after the CDS end (terminator/3' UTR region)
  - both:       Separate upstream AND downstream entries per gene

Core extraction logic by Cash (collaborator).
NCBI Entrez integration, module structure, and bidirectional
extraction by RoyCyber1.
"""

from Bio import Entrez, SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from collections import Counter
from pathlib import Path
from typing import Tuple, Optional, Callable, Literal


# ─────────────────────────────────────────────────────────────────────
# Valid extraction directions
# ─────────────────────────────────────────────────────────────────────
DIRECTIONS = ("upstream", "downstream", "both")


# ─────────────────────────────────────────────────────────────────────
# NCBI helpers (unchanged)
# ─────────────────────────────────────────────────────────────────────

def fetch_from_ncbi(accession: str, email: str, output_dir: str,
                    progress_callback: Optional[Callable] = None) -> Tuple[str, str]:
    """
    Fetch GenBank and FASTA files from NCBI by accession number.

    Args:
        accession: NCBI accession number (e.g., 'NZ_CP097882.1')
        email: Email address for NCBI Entrez (required by NCBI)
        output_dir: Directory to save downloaded files
        progress_callback: Optional function to report progress messages

    Returns:
        Tuple of (genbank_path, fasta_path) for the downloaded files

    Raises:
        ValueError: if NCBI returns an empty/invalid record after retries.
        OSError: if no writable output directory can be found.
    """
    import time

    Entrez.email = email

    def log(msg):
        if progress_callback:
            progress_callback(msg)

    # ~/Downloads and similar folders can be write-blocked for a packaged
    # macOS app; fall back to a writable location if so.
    output_path = Path(output_dir)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        probe = output_path / ".rsas_write_test"
        probe.write_text("ok"); probe.unlink()
    except OSError:
        from settings_manager import default_output_dir
        output_path = default_output_dir() / "downloads"
        output_path.mkdir(parents=True, exist_ok=True)
        log(f"Note: '{output_dir}' is not writable; saving to {output_path} instead.")

    def _efetch_text(rettype, retries=3):
        """Fetch a record as text, validating the response and retrying on
        transient errors."""
        last_err = None
        for attempt in range(retries):
            try:
                handle = Entrez.efetch(db="nucleotide", id=accession,
                                       rettype=rettype, retmode="text")
                text = handle.read()
                handle.close()
                if isinstance(text, bytes):
                    text = text.decode("utf-8", "replace")
                if text and text.strip():
                    return text
                last_err = f"empty response for {accession} ({rettype})"
            except Exception as e:  # network error, HTTP 4xx/429, etc.
                last_err = str(e)
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))  # backoff for NCBI rate limits
        raise ValueError(f"NCBI fetch failed for {accession} ({rettype}): {last_err}")

    log(f"Fetching GenBank record for {accession}...")
    # gbwithparts gets full annotations + sequence for CON (contig) records;
    # plain "gb" returns a stub for CON accessions with no CDS/sequence.
    gb_text = _efetch_text("gbwithparts")
    if "LOCUS" not in gb_text or "FEATURES" not in gb_text:
        raise ValueError(
            f"NCBI returned an invalid GenBank record for '{accession}' "
            f"(no LOCUS/FEATURES). Check the accession number.")
    gb_path = str(output_path / f"{accession}.gb")
    with open(gb_path, "w") as f:
        f.write(gb_text)
    log(f"GenBank file saved: {gb_path}")

    log(f"Fetching FASTA record for {accession}...")
    fasta_text = _efetch_text("fasta")
    if not fasta_text.lstrip().startswith(">"):
        raise ValueError(
            f"NCBI returned an invalid FASTA record for '{accession}'.")
    fasta_path = str(output_path / f"{accession}.fasta")
    with open(fasta_path, "w") as f:
        f.write(fasta_text)
    log(f"FASTA file saved: {fasta_path}")

    return gb_path, fasta_path


def search_ncbi(query: str, email: str, max_results: int = 10,
                progress_callback: Optional[Callable] = None) -> list:
    """
    Search NCBI nucleotide database by organism or keyword.

    Args:
        query: Search term (e.g., 'Listeria monocytogenes[Orgn] AND complete genome')
        email: Email address for NCBI Entrez
        max_results: Maximum number of results to return
        progress_callback: Optional function to report progress messages

    Returns:
        List of dicts with 'id', 'accession', 'title', 'length' for each result
    """
    Entrez.email = email

    def log(msg):
        if progress_callback:
            progress_callback(msg)

    log(f"Searching NCBI for: {query}")
    handle = Entrez.esearch(db="nucleotide", term=query, retmax=max_results)
    search_results = Entrez.read(handle)
    handle.close()

    ids = search_results.get("IdList", [])
    if not ids:
        log("No results found.")
        return []

    log(f"Found {len(ids)} results, fetching summaries...")
    handle = Entrez.esummary(db="nucleotide", id=",".join(ids))
    summaries = Entrez.read(handle)
    handle.close()

    results = []
    for summary in summaries:
        results.append({
            "id": str(summary.get("Id", "")),
            "accession": str(summary.get("AccessionVersion", summary.get("Caption", ""))),
            "title": str(summary.get("Title", "")),
            "length": int(summary.get("Length", 0)),
        })

    log(f"Retrieved {len(results)} summaries.")
    return results


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _build_fasta_lookup(fasta_file: str, log: Callable) -> dict:
    """
    Load FASTA file into a dictionary keyed by multiple ID variants.
    This handles the common mismatch between GenBank record IDs and FASTA headers.

    Returns dict mapping various ID forms -> sequence (Bio.Seq.Seq)
    """
    fasta_dict = {}
    record_count = 0
    for record in SeqIO.parse(fasta_file, "fasta"):
        record_count += 1
        seq = record.seq
        # Index by multiple ID variants to maximize matching
        # FASTA header: >NZ_CP097882.1 Listeria monocytogenes strain ...
        # GenBank record.id might be: NZ_CP097882, NZ_CP097882.1, etc.
        fasta_dict[record.id] = seq               # e.g. "NZ_CP097882.1"
        fasta_dict[record.name] = seq             # e.g. "NZ_CP097882.1"
        # Also store without version suffix
        base_id = record.id.rsplit(".", 1)[0]
        fasta_dict[base_id] = seq                 # e.g. "NZ_CP097882"
        log(f"  FASTA record: '{record.id}' ({len(seq):,} bp)")

    log(f"Loaded {record_count} FASTA record(s)")
    return fasta_dict


def _find_genome_seq(record, fasta_dict: dict, log: Callable):
    """
    Find the genome sequence for a GenBank record.

    Strategy:
    1. Try matching GenBank record ID to FASTA lookup dict
    2. If GenBank record has its own sequence, use that
    3. If only one FASTA record exists, use it (single-genome case)
    """
    # Try matching by record ID variants
    for candidate_id in [record.id, record.name, record.id.rsplit(".", 1)[0]]:
        if candidate_id in fasta_dict:
            log(f"  Matched GenBank record '{record.id}' to FASTA by ID '{candidate_id}'")
            return fasta_dict[candidate_id]

    # Fallback: GenBank record may contain its own sequence
    # (CON records have UnknownSeq which raises on str(), so we must try/except)
    try:
        if record.seq and len(record.seq) > 0:
            seq_str = str(record.seq)
            if seq_str and set(seq_str) != {"N"} and len(seq_str) > 100:
                log(f"  Using embedded sequence from GenBank record '{record.id}' ({len(record.seq):,} bp)")
                return record.seq
    except Exception:
        pass  # Sequence content is undefined (CON record) — skip this fallback

    # Last resort: if there's only one FASTA record, assume it matches
    unique_seqs = list(set(id(v) for v in fasta_dict.values()))
    if len(unique_seqs) == 1:
        seq = next(iter(fasta_dict.values()))
        log(f"  Single FASTA record available, using it for GenBank record '{record.id}'")
        return seq

    return None


def _extract_upstream(genome_seq, start: int, end: int, strand: int, length: int):
    """Extract upstream sequence relative to CDS, strand-aware."""
    if strand == 1:  # forward
        up_start = max(0, start - length)
        return genome_seq[up_start:start]
    else:  # reverse
        up_end = min(len(genome_seq), end + length)
        return genome_seq[end:up_end].reverse_complement()


def _extract_downstream(genome_seq, start: int, end: int, strand: int, length: int):
    """Extract downstream sequence relative to CDS, strand-aware."""
    if strand == 1:  # forward
        dn_end = min(len(genome_seq), end + length)
        return genome_seq[end:dn_end]
    else:  # reverse
        dn_start = max(0, start - length)
        return genome_seq[dn_start:start].reverse_complement()


def _write_fasta_entry(out_fasta, gene, protein_id, product, strand_str,
                       start, end, start_codon, stop_codon,
                       direction_label, length, seq):
    """Write a single FASTA entry with standardised header.

    The header reports the ACTUAL extracted length (len(seq)), which may be
    shorter than the requested ``length`` for genes near chromosome boundaries.
    This ensures scientific accuracy — readers see the true sequence length.
    """
    actual_length = len(seq)
    header = (f">{gene}|{protein_id}|{product}|"
              f"strand={strand_str}|CDS={start}-{end}|"
              f"start_codon={start_codon}|stop_codon={stop_codon}|"
              f"{direction_label}={actual_length}bp")
    out_fasta.write(f"{header}\n{str(seq)}\n")


# ─────────────────────────────────────────────────────────────────────
# Main extraction function
# ─────────────────────────────────────────────────────────────────────

def extract_sequences(
        genbank_file: str,
        fasta_file: str,
        output_file: str,
        upstream_length: int = 0,
        downstream_length: int = 0,
        direction: str = "upstream",
        upstream_length_2: Optional[int] = None,
        downstream_length_2: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
) -> Tuple[int, int]:
    """
    Extract upstream, downstream, or flanking sequences from genes in a genome.

    Core extraction logic by Cash. Bidirectional extension by RoyCyber1.

    Args:
        genbank_file:       Path to GenBank annotation file (.gb, .flat, .gbk)
        fasta_file:         Path to genome FASTA file
        output_file:        Path for output FASTA file
        upstream_length:    Bases upstream of CDS to extract (used when direction
                            is "upstream" or "both")
        downstream_length:  Bases downstream of CDS to extract (used when direction
                            is "downstream" or "both")
        direction:          "upstream", "downstream", or "both"
        upstream_length_2:  Optional second window for upstream
        downstream_length_2: Optional second window for downstream
        progress_callback:  Optional function to report progress messages

    Returns:
        Tuple of (total_genes, successful_extractions)
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"Invalid direction '{direction}'. Must be one of: {DIRECTIONS}")

    def log(msg):
        if progress_callback:
            progress_callback(msg)

    # Validate lengths based on direction
    if direction == "upstream" and upstream_length <= 0:
        raise ValueError("upstream_length must be > 0 for upstream extraction")
    if direction == "downstream" and downstream_length <= 0:
        raise ValueError("downstream_length must be > 0 for downstream extraction")
    if direction == "both":
        if upstream_length <= 0:
            raise ValueError("upstream_length must be > 0 for 'both' direction")
        if downstream_length <= 0:
            raise ValueError("downstream_length must be > 0 for 'both' direction")

    dir_desc = {
        "upstream": f"upstream ({upstream_length} bp)",
        "downstream": f"downstream ({downstream_length} bp)",
        "both": f"upstream ({upstream_length} bp) + downstream ({downstream_length} bp)",
    }
    log(f"Extraction mode: {dir_desc[direction]}")

    # Load FASTA into lookup dictionary (handles multi-record FASTA and ID variants)
    log(f"Loading genome from FASTA: {fasta_file}")
    fasta_dict = _build_fasta_lookup(fasta_file, log)

    if not fasta_dict:
        log("ERROR: No sequences found in FASTA file!")
        return 0, 0

    log(f"Parsing GenBank annotations: {genbank_file}")

    # Count GenBank records and features for diagnostics
    gb_records = list(SeqIO.parse(genbank_file, "genbank"))
    log(f"Found {len(gb_records)} GenBank record(s)")
    for i, rec in enumerate(gb_records):
        cds_count = sum(1 for f in rec.features if f.type == "CDS")
        # Check for undefined/CON sequences safely
        try:
            seq_len = len(rec.seq)
            _ = str(rec.seq[:1])  # Test if sequence content is accessible
            has_seq = seq_len > 0
        except Exception:
            seq_len = 0
            has_seq = False
        log(f"  Record {i+1}: '{rec.id}' | {len(rec.features)} features ({cds_count} CDS) | "
            f"embedded seq: {'yes' if has_seq else 'no (CON/reference only)'} ({seq_len:,} bp)")

    total = 0
    successful = 0
    skipped_no_seq = 0

    with open(output_file, "w") as out_fasta:
        for record in gb_records:
            # Find the matching genome sequence for this record
            genome_seq = _find_genome_seq(record, fasta_dict, log)

            if genome_seq is None:
                cds_in_record = sum(1 for f in record.features if f.type == "CDS")
                log(f"WARNING: Could not find genome sequence for record '{record.id}' "
                    f"(has {cds_in_record} CDS features) - skipping")
                skipped_no_seq += cds_in_record
                continue

            for feature in record.features:
                if feature.type != "CDS":
                    continue

                total += 1

                gene = feature.qualifiers.get("gene", ["unknown"])[0]
                product = feature.qualifiers.get("product", ["unknown product"])[0]
                protein_id = feature.qualifiers.get("protein_id", ["no_protein_id"])[0]

                # Get start, end, and strand of CDS
                start = int(feature.location.start)
                end = int(feature.location.end)
                strand = feature.location.strand

                # Boundary check
                if start < 0 or end > len(genome_seq):
                    log(f"  WARNING: CDS {gene} ({start}-{end}) exceeds sequence length "
                        f"({len(genome_seq)} bp) - skipping")
                    continue

                # Extract CDS sequence for codon info (reverse complement if minus strand)
                cds_seq = genome_seq[start:end]
                if strand == -1:
                    cds_seq = cds_seq.reverse_complement()

                start_codon = str(cds_seq[:3])
                stop_codon = str(cds_seq[-3:])
                strand_str = "+" if strand == 1 else "-"

                # Common header fields
                hdr_args = dict(gene=gene, protein_id=protein_id, product=product,
                                strand_str=strand_str, start=start, end=end,
                                start_codon=start_codon, stop_codon=stop_codon)

                # ── Upstream extraction ───────────────────────────────
                if direction in ("upstream", "both"):
                    seq = _extract_upstream(genome_seq, start, end, strand, upstream_length)
                    _write_fasta_entry(out_fasta, **hdr_args,
                                       direction_label="upstream", length=upstream_length, seq=seq)

                    # Optional second upstream window
                    if upstream_length_2 is not None and upstream_length_2 > 0:
                        seq2 = _extract_upstream(genome_seq, start, end, strand, upstream_length_2)
                        _write_fasta_entry(out_fasta, **hdr_args,
                                           direction_label="upstream", length=upstream_length_2, seq=seq2)

                # ── Downstream extraction ─────────────────────────────
                if direction in ("downstream", "both"):
                    seq = _extract_downstream(genome_seq, start, end, strand, downstream_length)
                    _write_fasta_entry(out_fasta, **hdr_args,
                                       direction_label="downstream", length=downstream_length, seq=seq)

                    # Optional second downstream window
                    if downstream_length_2 is not None and downstream_length_2 > 0:
                        seq2 = _extract_downstream(genome_seq, start, end, strand, downstream_length_2)
                        _write_fasta_entry(out_fasta, **hdr_args,
                                           direction_label="downstream", length=downstream_length_2, seq=seq2)

                successful += 1

                if total % 500 == 0:
                    log(f"Processed {total} CDS features ({successful} successful)...")

    if skipped_no_seq > 0:
        log(f"WARNING: Skipped {skipped_no_seq} CDS features due to unmatched records")
    log(f"Extraction complete: {successful}/{total} genes processed")
    log(f"Output saved to: {output_file}")

    return total, successful


# ─────────────────────────────────────────────────────────────────────
# Backward-compatible alias
# ─────────────────────────────────────────────────────────────────────

def extract_upstream_sequences(
        genbank_file: str,
        fasta_file: str,
        output_file: str,
        upstream_length: int,
        upstream_length_2: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
) -> Tuple[int, int]:
    """
    Legacy wrapper — extracts upstream sequences only.
    New code should use ``extract_sequences()`` directly.
    """
    return extract_sequences(
        genbank_file=genbank_file,
        fasta_file=fasta_file,
        output_file=output_file,
        upstream_length=upstream_length,
        downstream_length=0,
        direction="upstream",
        upstream_length_2=upstream_length_2,
        downstream_length_2=None,
        progress_callback=progress_callback,
    )
