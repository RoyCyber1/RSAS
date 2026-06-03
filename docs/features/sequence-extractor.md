# Sequence Extractor

Pull the region around a gene, upstream, downstream, or both, from local files or fetched straight from NCBI, and write it out as a FASTA you then load on the Analyze page.

---

## Overview

RNA thermometers and other regulatory elements live in the untranslated flanks of a gene, not in the coding sequence itself. A fourU or ROSE-type thermometer sits in the 5' leader ahead of the start codon; a terminator or 3' regulatory structure sits past the stop. The Sequence Extractor is how you cut those flanks out of a whole genome so you can fold them.

You give it two things: a genome **FASTA** (the raw sequence) and a **GenBank** annotation (where the genes are). For every CDS feature in the annotation it walks out a fixed number of bases from the coding boundary and writes that slice to a FASTA entry. Upstream pulls the bases before the CDS start, the promoter / 5' leader region. Downstream pulls the bases after the CDS end, the terminator / 3' end. Both writes each as its own entry. The result is a FASTA, one entry per gene per direction, ready to drop into the Analyze page.

The extraction is strand-aware. For a gene on the minus strand the "upstream" region is physically downstream in genome coordinates, and the extractor reverse-complements it so the sequence you get always reads 5' to 3' relative to the gene, not the chromosome.

---

## When to use it

- You have a genome and want the 5' leaders of every gene to screen for thermometers, but you only have the assembly, not pre-cut leader sequences.
- You want the 3' ends instead, to look at terminators or 3' UTR structure.
- You want both flanks in one pass.
- You only have an NCBI accession and no files on disk yet. The Fetch from NCBI tab downloads the genome and annotation for you.
- You want to compare two window sizes (say a 300 bp and a 150 bp leader) in a single run without re-running the tool. That is what the optional second window is for.

If you already have a FASTA of leader sequences, you do not need this tool. Go straight to Analyze.

---

## Step by step

### From local files

1. Open the **Sequence Extractor** page.
2. Stay on the **Local Files** tab.
3. Browse to your genome **FASTA** file (`.fasta`, `.fa`, `.fna`).
4. Browse to your **GenBank** annotation file (`.flat`, `.gb`, `.gbk`).
5. Pick a **Direction**: Upstream, Downstream, or Both.
6. Set the lengths. Upstream defaults to 300 bp, downstream to 200 bp. Only the field for your chosen direction is shown.
7. (Optional) Tick **Window 2** to extract a second region of a different length in the same run.
8. Set the **Output File** path (a `.fasta`). The Save As dialog defaults to your Downloads folder with the name `extracted_sequences.fasta`.
9. Click **Run Extraction**. Progress streams into the log, and a summary box reports how many genes were processed.

### Fetching from NCBI

1. Open the **Sequence Extractor** page and switch to the **Fetch from NCBI** tab.
2. Enter an **Accession Number**, for example `NZ_CP097882.1`.
3. Enter your **Email**. NCBI requires an email address for programmatic access.
4. Choose where to **Save Downloads To** (defaults to your Downloads folder).
5. Click **Fetch from NCBI**. RSAS downloads both the GenBank record and the FASTA, saves them to that folder, and fills the file paths into the Local Files tab automatically, then switches you back to it.
6. From there, pick your direction and lengths, set an output path, and click **Run Extraction** exactly as in the local-files flow.

---

## Options in detail

### The two tabs

**Local Files.** Two file pickers: a genome FASTA and a GenBank annotation. This is the tab the extraction actually runs from. Even when you fetch from NCBI, the downloaded paths land here before you run.

**Fetch from NCBI.** Three inputs (accession, email, download directory) plus a Fetch button. It calls NCBI Entrez to pull the GenBank record (using `gbwithparts` so contig / CON records come back with full annotations and sequence, not a stub) and the FASTA, writes both into your chosen directory as `<accession>.gb` and `<accession>.fasta`, and then populates the Local Files tab. Fetching is a separate step from extracting, you fetch first, then run.

### Direction

A segmented control with three choices. The info text next to it updates as you switch.

- **Upstream** (the default): "Extract N bases before the CDS start (promoter / 5' UTR region)." Writes one upstream entry per gene.
- **Downstream**: "Extract N bases after the CDS end (terminator / 3' UTR region)." Writes one downstream entry per gene.
- **Both**: "Extract upstream AND downstream as separate entries per gene." Writes two entries per gene, one upstream and one downstream. They are not concatenated; each is its own FASTA record.

The direction also controls which length fields are visible. Upstream shows only the upstream length, Downstream shows only the downstream length, Both shows both.

### Upstream and downstream lengths

- **Upstream Length (bp)**: how many bases before the CDS start to take. Default **300**. Used when the direction is Upstream or Both. Required and must be a positive integer.
- **Downstream Length (bp)**: how many bases after the CDS end to take. Default **200**. Used when the direction is Downstream or Both. Required and must be a positive integer.

If a gene sits near the end of the chromosome and there are not enough bases to fill the requested length, you get whatever is available. The extractor clamps to the sequence boundary rather than failing, and the FASTA header reports the actual length extracted, which may be shorter than what you asked for.

### The optional second window

Tick **Window 2** to extract a second region per direction in the same run. When enabled it exposes its own small length fields:

- **Up** (default 150) for a second upstream window.
- **Down** (default 100) for a second downstream window.

Which sub-fields appear follows the same direction logic as the main lengths. With Window 2 on and direction Upstream, each gene gets two upstream entries (one at the primary length, one at the Window 2 length). With Both, you can get up to four entries per gene. The second window is only used when the checkbox is ticked and its value is a positive integer; left unticked, it is ignored.

This is a convenience for comparing window sizes without a second run, for example a long leader to catch distal structure and a short one focused near the start codon.

### NCBI email and save location

NCBI requires a contact email for Entrez requests, so the **Email** field is mandatory on the Fetch tab. The extractor sets it as the Entrez email before any download. The **Save Downloads To** directory is where the fetched `.gb` and `.fasta` files are written; it is created if it does not exist, and defaults to your Downloads folder.

---

## What you get

The output is a single FASTA file at the path you chose. One entry is written per gene per direction. Each header is standardized and packs the gene's metadata:

```
>gene|protein_id|product|strand=+|CDS=start-end|start_codon=AUG|stop_codon=UGA|upstream=300bp
SEQUENCE...
```

The trailing `upstream=Nbp` or `downstream=Nbp` field reports the **actual** number of bases extracted, which is the requested length unless the gene was near a chromosome boundary, in which case it is the shorter slice that was available.

**Both** writes the upstream and downstream regions as **separate entries** for each gene, not a single merged sequence. So a gene named `tlpA` produces two records: one with `upstream=300bp` and one with `downstream=200bp`, each with its own header carrying the same gene metadata but a different direction label and sequence. If Window 2 is on, the additional windows appear as further separate entries with the same per-gene metadata.

When a CDS has no `gene`, `product`, or `protein_id` qualifier in the annotation, the header falls back to `unknown`, `unknown product`, or `no_protein_id` respectively.

---

## How it works

The work happens in `RnaThermofinder/utils/upstream_extractor.py`.

`extract_sequences()` is the entry point. It validates the direction and the lengths (upstream must be positive for Upstream or Both; downstream must be positive for Downstream or Both), then loads the genome and walks every annotation record.

The genome FASTA is read into a lookup dictionary by `_build_fasta_lookup()`. Each record is indexed under several ID variants (full ID, name, and the ID stripped of its version suffix) because GenBank record IDs and FASTA headers often disagree on the `.1` version tag. For each GenBank record, `_find_genome_seq()` matches it to a sequence: first by trying those ID variants, then by using the record's own embedded sequence if it has one, and finally, if the FASTA holds a single record, assuming it is the match.

Then it iterates the CDS features. For each one it reads `feature.location.start`, `.end`, and `.strand`, does a boundary check, and extracts the coding slice to derive the start and stop codons for the header (reverse-complementing on the minus strand).

The flank extraction itself is two small strand-aware helpers:

- `_extract_upstream(genome_seq, start, end, strand, length)`: on the plus strand it takes `genome_seq[start-length : start]`; on the minus strand it takes `genome_seq[end : end+length]` and reverse-complements it. Either way it clamps to the genome ends with `max(0, ...)` and `min(len, ...)`.
- `_extract_downstream(...)`: the mirror image. Plus strand takes `genome_seq[end : end+length]`; minus strand takes `genome_seq[start-length : start]` reverse-complemented.

Each slice is handed to `_write_fasta_entry()`, which builds the standardized header (reporting `len(seq)`, the true extracted length) and appends the record to the open output file. The function returns a `(total_genes, successful_extractions)` tuple, which the dialog turns into the summary message.

A legacy wrapper, `extract_upstream_sequences()`, still exists for older callers; it just calls `extract_sequences()` with the direction fixed to upstream.

The NCBI side is `fetch_from_ncbi()`, which sets `Entrez.email`, calls `Entrez.efetch` twice (once `gbwithparts` for the GenBank file, once `fasta` for the sequence), and writes both to disk. (There is also a `search_ncbi()` helper in the module for accession lookup by organism, not currently wired into this dialog.)

---

## Worked example

You want the 5' leaders of every gene in a *Listeria monocytogenes* assembly to screen for thermometers, and you only have the accession.

1. Open the **Sequence Extractor** page, switch to **Fetch from NCBI**.
2. Accession: `NZ_CP097882.1`. Email: your address. Save to: your Downloads folder.
3. Click **Fetch from NCBI**. The log shows the GenBank and FASTA files being saved, and the Local Files tab fills in.
4. Direction stays on **Upstream**. Upstream Length stays at **300**.
5. You also want a tighter window near the start codon, so tick **Window 2** and set **Up** to 150.
6. Output File: `listeria_leaders.fasta` in Downloads.
7. Click **Run Extraction**. The log streams `Processed 500 CDS features...` checkpoints and ends with `Extraction complete: N/N genes processed`.

You now have a FASTA with two entries per gene (a 300 bp leader and a 150 bp leader), each header tagged with the gene name, strand, CDS coordinates, and codons. Load it on the Analyze page and run your thermometer screen.

---

## Tips

- **Upstream is the common case for thermometers.** RNA thermometers regulate translation initiation, so the 5' leader is where they live. Start there.
- **Use Both when you are unsure** which flank holds the structure, then split the results by the `upstream=` / `downstream=` tag in the headers.
- **Window 2 saves a run.** If you routinely compare a long and a short leader, set them both in one pass instead of extracting twice.
- **The header metadata travels with the sequence.** Strand, CDS coordinates, and the start/stop codons stay attached through the FASTA, so you can trace any Analyze result back to its gene.
- **Pick a sensible save location up front.** Fetched files land in the download directory you choose and the output FASTA defaults to Downloads, so keep a run's files together if you are processing several genomes.

---

## Limitations and gotchas

- **NCBI fetch needs internet, biopython, and a valid email.** The fetch runs through Bio.Entrez, so biopython must be installed, you must be online, and the email field is not optional. NCBI rejects programmatic requests without one.
- **Only CDS features are extracted.** The tool iterates features of type `CDS`. tRNA, rRNA, ncRNA, and pseudogene features without a CDS are not picked up.
- **Genes near a chromosome boundary come out short.** A leader requested at 300 bp on a gene that starts 120 bp from the contig edge yields 120 bp. This is expected, and the header's `upstream=120bp` tells you it happened.
- **Both does not merge the flanks.** You get two separate records per gene, never one concatenated leader-plus-terminator sequence.
- **The output is overwritten, not appended.** Running into an existing output path replaces it.
- **Matching the genome to the annotation can fail.** If the GenBank record ID and the FASTA header cannot be reconciled (and the FASTA holds more than one record so the single-record fallback does not apply), that record's CDS features are skipped, and the log warns with the count.

---

## Troubleshooting

**"Select a GenBank file" / "Select a FASTA file" error.** Both source files are required before extraction. If you fetched from NCBI, confirm the fetch finished and populated the Local Files tab. If you typed paths, confirm both files exist; the dialog checks the disk before running.

**"Upstream length must be a positive integer" (or downstream / Window 2).** The length fields accept whole positive numbers only. Clear any blank, zero, or non-numeric value. The same rule applies to the Window 2 fields when that box is ticked.

**Fetch fails or hangs.** Check your internet connection and that biopython is installed. Confirm the accession is valid and the email field is filled. The fetch status label reports "Fetch failed" and the error appears in the log.

**A run reports far fewer genes than you expected, or "Skipped N CDS features."** The genome FASTA and the GenBank annotation are not matching up by record ID. Make sure both files describe the same assembly (and ideally came from the same source or the same NCBI fetch), so their identifiers line up.

**The output FASTA is empty.** Either no CDS features were found in the annotation, or no genome sequence could be matched to any record. Check the log: it prints the record count, the CDS count per record, and whether each record had an embedded or matched sequence.

**A gene's extracted region is shorter than the length you set.** The gene is near a sequence boundary. This is by design; the header reports the true length.
