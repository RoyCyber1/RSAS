# Usage Guide

Everything you need to know about using RSAS v3.0: the GUI, every settings dialog, output formats, the scripting API, and tips for getting the most out of the tool.

---

## Starting the application

```bash
python main.py
```

The main window has a sidebar on the left with five pages:

| Page | What it's for |
|---|---|
| **Analyze** | Load input files, run analysis, view logs, export results |
| **Results** | View the most recent analysis results in a table |
| **Settings** | Analysis Settings, Performance, Output Columns, Motif Finder, Quality Score Builder, Sequence Options |
| **Sequence Extractor** | Extract upstream/downstream sequences from local files or NCBI |
| **Synthetic Pool** | Generate random RNA sequence pools with fixed motif inserts |

---

## Loading input data

### Supported formats

- **FASTA** (`.fasta`, `.fa`) — standard format, one or more sequences
- **CSV** — comma-separated, with configurable name and sequence columns
- **TSV** — tab-separated, same column configuration as CSV

### How to load

- Click **Browse** on the Analyze page and select your file
- Or **drag and drop** a file onto the window
- The file path appears in the input field; you can also type or paste a path directly

### Keyboard shortcut

`Cmd+O` (macOS) or `Ctrl+O` (Windows/Linux) opens the file browser.

---

## Running an analysis

1. Load an input file (see above)
2. (Optional) adjust settings — see sections below
3. Click **Analyze** or press `Cmd+R` / `Ctrl+R`
4. Progress messages appear in the log area as sequences are processed
5. When done, results are written to:
   - `Data/Outputs/rna_results.csv`
   - `Data/Outputs/rna_results.xlsx` (three tabs: Full Sequence, Hairpin Analysis, and optionally Motif Matches)

### What happens during analysis

For each input sequence, RSAS:

1. Folds the full-length sequence at each configured temperature (MFE, and PF if enabled)
2. Detects the terminal hairpin or RBS-sequestering hairpin depending on the configured method
3. Folds the extracted hairpin at each temperature
4. Computes base-pair composition (AU%, GC%, GU%) for both full-length and hairpin
5. Locates the Shine-Dalgarno / RBS region and computes paired percentage at each temp
6. If motif search is enabled, finds all occurrences of the motif and computes sequestering at each temp
7. Runs range checks (is each MFE/composition value within the configured range?)
8. Computes quality scores based on how many criteria pass
9. Writes the enabled columns to CSV and Excel

---

## Settings page

The Settings page has several cards, each opening its own dialog.

### Analysis Settings

Opens a dialog with two tabs:

**Hairpin Detection tab:**
- **Terminal** (default) — finds the rightmost stem-loop structure in the sequence. This works well when the regulatory hairpin is at the 3' end of the leader
- **RBS-based** — finds the hairpin that sequesters the Shine-Dalgarno sequence. Uses an AUG-fallback heuristic for fourU-type thermometers where the RBS overlaps with the AUG. Includes a window-cut approach for large or multi-branch structures
- Filter ranges for hairpin composition (AU%, GC%, GU% min/max) and MFE at each temperature

**Folding Temperatures tab:**
- Configure 1 to 5 folding temperatures (default: 25, 37, 42)
- The lowest temperature is always used as the "base" for hairpin detection and difference calculations
- All output columns dynamically update when you change temperatures — column headers, CSV keys, and Excel tab headers all reflect whatever temperatures you configure
- Add or remove temperature rows with the + and - buttons

### Performance

Opens a compact dialog for CPU core configuration:
- Set the number of cores for parallel processing (1 = sequential, which is fine for small runs)
- The dialog shows your system's total core count as a reference
- For large FASTA files (100+ sequences), try 2-4 cores

### Output Columns

Opens the column configuration dialog:

**Quick presets:**
- **Hairpin Analysis** — hairpin structure, composition, MFE, quality score
- **Full Sequence Analysis** — full-length MFE, composition, range checks, quality score
- **Riboswitch** — RBS sequestering columns + partition function accessibility
- **Full Export** — everything enabled

**Custom presets:**
- Save your current column selection as a named preset
- Load or delete saved presets
- Presets are stored in `csv_output_settings.json`

**Column groups** (collapsible):
- Basic Info (name, sequence, structure)
- Full-Length MFE
- Composition
- Range Checks
- RBS Sequestering
- Hairpin Info
- Partition Function
- Motif Finder
- Quality Scores

Only enabled columns are computed during analysis, so disabling columns you don't need makes runs faster.

### Motif / Sequence Finder

Configure a custom nucleotide pattern to search for in every sequence:

- **Enable/disable** the motif search with the toggle switch
- **Pattern** — enter any IUPAC nucleotide pattern (e.g. `AGGAGG`, `UAUAAUGU`, `NNUANN`)
- Supports all IUPAC degenerate codes:
  - R = A|G, Y = C|U, S = G|C, W = A|U
  - K = G|U, M = A|C, B = C|G|U, D = A|G|U
  - H = A|C|U, V = A|C|G, N = any
- Click **Validate** to check the pattern and see the regex expansion for degenerate patterns
- The finder reports **all overlapping matches** for each sequence

**What you get in the output:**
- `motif_count` — number of matches found
- `motif_match_seq` — all matched subsequences (semicolon-separated if multiple)
- `motif_match_pos` — positions of each match (0-based, half-open)
- Paired percentage, dot-bracket structure, and PF accessibility at each temperature (semicolon-separated)
- Temperature difference columns (e.g. paired% at 42 minus paired% at 25)
- A dedicated **Motif Matches** tab in the Excel output with one row per hit per sequence

### Terminal Hairpin Quality Score Builder

Define the criteria and weights for the hairpin quality scoring system:
- Select which metrics contribute to the score (MFE at each temp, composition)
- Set weights for each criterion
- Preview how scoring works with the current configuration

### Sequence Options

Optionally modify input sequences before analysis:
- Append a sequence (e.g. `AUG`) at the **start** or **end** of each input sequence
- Useful for adding start codons or other regulatory elements that aren't in your input file

---

## Sequence Extractor page

The sidebar's Sequence Extractor page lets you extract sequences upstream or downstream of a genomic feature before running analysis.

**Local Files tab:**
- Provide a genome file (FASTA) and an annotation file (GFF/GBK)
- Specify the feature type (e.g. CDS), direction (upstream or downstream), and region length
- Choose whether to include the start codon in the extracted region
- Output is a FASTA file you can then load into the Analyze page

**Fetch from NCBI tab:**
- Enter an NCBI accession number
- The tool fetches the genome and annotations automatically
- Same extraction options as Local Files

---

## Synthetic Pool Generator page

Generate random RNA sequence pools for in vitro selection experiments or computational screening.

### Template layout

Build your sequence template by adding segments:
- **Random region** — specify the length (e.g. 84 nt of random A/C/G/U)
- **Fixed motif** — specify an IUPAC pattern (e.g. `GGAGG`). Degenerate characters are resolved to a random matching nucleotide for each generated sequence

The segments are concatenated left to right. For example, the built-in RBS + AUG preset creates:

```
R(84) + GGAGG + R(8) + AUG = 100 nt per sequence
```

### Presets

- **Custom** — start from scratch
- **RBS + AUG** — 84 random + GGAGG + 8 random + AUG (standard RBS library layout)

Click **Load Preset** to populate the segment list.

### Composition targets (optional)

Enable optional filtering to keep only sequences whose composition falls within a target range:
- **GC%** — target percentage ± tolerance
- **AU%** — same
- **GU%** — same

All three are independent and disabled by default. When enabled, sequences that don't meet the targets are discarded (rejection sampling).

### Output

- Set the pool size (number of sequences to generate)
- Optionally set a random seed for reproducibility
- Choose an output file path (default: FASTA format)
- Click **Generate** and watch progress in the log area

---

## Exporting results

After an analysis completes:

1. Click **Export** or press `Cmd+E` / `Ctrl+E`
2. Choose a save location — defaults to Downloads with a timestamped filename
3. Select format: **Excel (.xlsx)** or **CSV (.csv)**
4. Optionally open the containing folder after saving

### Excel output format

The Excel workbook contains up to three tabs:

| Tab | Contents |
|---|---|
| **Full Sequence** | Full-length sequence data: structure at each temp, MFE, composition, RBS sequestering, range checks, quality scores |
| **Hairpin Analysis** | Extracted hairpin data: detection method, hairpin sequence/structure, composition, MFE, PF data, quality scores |
| **Motif Matches** | One row per motif hit per sequence: match position, matched subsequence, paired%, structure, PF accessibility at each temp, diffs |

The Motif Matches tab only appears if motif search was enabled and at least one match was found.

Each tab only includes the columns that were enabled in Output Columns at the time of the analysis run.

### CSV output format

The CSV file contains all enabled columns in a single flat table. Multi-value fields (from the motif finder when there are multiple matches) are semicolon-separated.

---

## Command-line / script usage

You can run the analysis from Python without the GUI:

```python
from pathlib import Path
from RnaThermofinder.core import FastaParse, HairpinAnalysis

# Load sequences
sequences = FastaParse.read_fasta("input.fasta")

# For CSV/TSV input:
# sequences = FastaParse.read_csv_tsv_sequences(
#     "input.csv", skip_rows=30, name_col=0, seq_col=10
# )

# Analysis settings
settings = {
    "au_min": 50, "au_max": 60,
    "gc_min": 0, "gc_max": 30,
    "gu_min": 15, "gu_max": 25,
    "mfe_25_min": -17, "mfe_25_max": -10,
    "mfe_37_min": -13, "mfe_37_max": -6,
    "mfe_42_min": -7, "mfe_42_max": -2,
    "hairpin_detection_method": "terminal",  # or "rbs_based"
    "num_cpu_cores": 1,
    # Original sequence ranges:
    "orig_mfe_25_min": -30, "orig_mfe_25_max": -10,
    "orig_mfe_37_min": -25, "orig_mfe_37_max": -5,
    "orig_mfe_42_min": -20, "orig_mfe_42_max": -2,
    "orig_au_min": 0, "orig_au_max": 100,
    "orig_gc_min": 0, "orig_gc_max": 100,
    "orig_gu_min": 0, "orig_gu_max": 100,
}

output_dir = Path("Data/Outputs")
output_dir.mkdir(parents=True, exist_ok=True)

results = HairpinAnalysis.calculate_results_final(
    sequences,
    output_dir,
    settings,
    progress_callback=print,
    csv_settings_manager=None,  # None = default columns
)

print(f"Analyzed {len(results)} sequences")
print(f"Results in {output_dir / 'rna_results.csv'}")
```

For custom output columns, instantiate a `SettingsManager` from `settings_manager.py` and pass it as `csv_settings_manager`. The same JSON settings file used by the GUI works here too.

### Using the motif finder standalone

```python
from RnaThermofinder.utils.motif_finder import (
    find_motif_occurrences,
    analyze_motif_sequestering,
)

sequence = "AUGCGGAGGCUUAAGCUAGC"
motif = "GGAGG"

# Find all matches
hits = find_motif_occurrences(sequence, motif, allow_overlap=True)
for h in hits:
    print(f"Match at {h['start']}-{h['end']}: {h['matched_seq']}")
```

### Using the synthetic pool generator standalone

```python
from RnaThermofinder.utils.synthetic_pool_generator import generate_pool, PRESETS

segments = PRESETS["RBS + AUG"]
result = generate_pool(
    n=10000,
    segments=segments,
    output_file="my_pool.fasta",
    seed=42,
)
print(f"Wrote {result['written']} sequences to {result['file']}")
```

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl + O` | Open file browser |
| `Cmd/Ctrl + R` | Run analysis |
| `Cmd/Ctrl + E` | Export results |

---

## Tips

- **Start with Hairpin Analysis preset** for quick screening, then switch to Full Export when you need everything
- **RBS-based detection** works better when the regulatory hairpin isn't the rightmost one in the sequence (e.g. nested or multi-branch structures)
- **Increase CPU cores** for large batches (100+ sequences) — go to Performance settings and try 2-4 cores
- **Disable PF columns** if you don't need them — partition function computation is the most expensive part of the analysis
- **Use the motif finder** to screen for specific regulatory elements (e.g. Shine-Dalgarno variants, fourU motifs, anti-anti-sigma factor binding sites)
- **Temperature diffs** are your main signal for thermometer-like behavior: look for motifs or RBS regions where paired% drops significantly between the base temperature and the elevated temperature
- **Quality scores** are sorted descending in the output — the best candidates appear at the top
- **Custom temperatures**: if you're studying cold-shock elements, try lower temperatures (e.g. 15, 25, 37). For heat-shock, try 37, 42, 50
- **Synthetic pool generator**: use composition targets to bias your library toward specific GC content ranges relevant to your organism

---

## File locations

| File | Purpose |
|---|---|
| `Data/Inputs/` | Default location for input files (you can load from anywhere) |
| `Data/Outputs/rna_results.csv` | Most recent analysis results (CSV) |
| `Data/Outputs/rna_results.xlsx` | Most recent analysis results (Excel) |
| `csv_output_settings.json` | Saved column preferences and custom presets |
| `.recent_files.json` | Recently opened files list (auto-generated) |

---

## FAQ

**Q: Can I use DNA sequences (T instead of U)?**
A: RSAS works with RNA sequences (A, C, G, U). If your input has T's, convert them to U's first. Most sequence editors can do this, or use a quick find-and-replace.

**Q: How is the quality score calculated?**
A: Each score (hairpin and full-length) counts how many of the configured criteria are "in range." With default settings there are 6 criteria (MFE at each of 3 temperatures + 3 composition checks), so scores go from 0 to 6. You can customize the criteria in the Quality Score Builder.

**Q: What's the difference between MFE and PF analysis?**
A: MFE gives you the single most stable structure (dot-bracket) — each nucleotide is either paired or unpaired. Partition function considers the ensemble of all possible structures weighted by their energies, giving you a probability of being unpaired at each position. PF is more informative but slower.

**Q: Can I add custom presets for the synthetic pool generator?**
A: Currently the only built-in preset is RBS + AUG. You can build any layout manually using the Add Segment buttons. If you need presets for your lab's common layouts, you can add them to the `PRESETS` dict in `synthetic_pool_generator.py`.

**Q: How do I cite RSAS?**
A: See the Citation section in the [README](../README.md).
