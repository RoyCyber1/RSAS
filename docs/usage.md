# Usage guide

This covers everything in RSAS v3.2: the GUI, every settings dialog, the output formats, the scripting API, and the tips that save you time. If you just want to get a result on screen, the README's "60-second version" is faster. This is the reference you come back to when you need detail.

---

## Starting the app

```bash
python main.py
```

The window opens on the Analyze page with a sidebar down the left. Seven pages:

| Page | What it's for |
|---|---|
| **Analyze** | Load files, run the analysis, watch the log, export results |
| **Results** | The most recent run, shown across three read-only tabs (Results Table, Structure Preview, Full Log) |
| **Settings** | Analysis Settings, Performance, Output Columns, Motif Finder, Quality Score Builder, Sequence Options |
| **Sequence Extractor** | Pull upstream/downstream regions from local files or NCBI |
| **Synthetic Pool** | Generate random RNA pools with fixed motif inserts |
| **RNArobo Search** | Find structural motifs (helices and loops) with the bundled RNArobo engine |
| **Pseudoknot Finder** | Predict pseudoknotted structures with the bundled Knotty engine |

Most of your time lives on Analyze and Settings. The other five pages are tools you reach for when a specific job comes up.

---

## Loading input data

### Formats it reads

- **FASTA** (`.fasta`, `.fa`): the usual, one or more sequences.
- **CSV / TSV** (`.csv`, `.tsv`): RSAS auto-detects the delimiter and works out which column is the name and which is the sequence from the header row, so you don't normally pick columns by hand. (From the scripting API you can override the columns explicitly; see the section below.)
- **Two-column text** (`.txt`): one `name<tab>sequence` per line.
- **GenBank** (`.gb`, `.gbk`): pulls the record sequences out. This one needs biopython installed.

A practical note: RSAS works in RNA. T's are converted to U automatically, and stray spaces, dashes, and pipe characters inside a sequence are stripped, but it's cleaner to start from tidy RNA so your output reads the way you expect.

### How to load

Click **Browse** on the Analyze page and pick a file, or just drag the file onto the window. The path shows up in the input field, and you can type or paste a path there directly if that's easier. `Cmd+O` (macOS) or `Ctrl+O` (Windows/Linux) opens the file browser too.

Two things worth knowing. Drag-and-drop relies on an optional library (`tkdnd`); if it isn't installed, the drop silently does nothing and you just use Browse instead. And the "N sequences loaded" badge counts sequences that passed a basic nucleotide check, so if a few entries in your file are malformed they're skipped (with a warning in the log) and the count comes out lower than the number of records in the file.

New here? There's a full worked run, with real output numbers, in [`Examples/README.md`](../Examples/README.md).

---

## Running an analysis

1. Load a file.
2. Adjust settings if you need to (sections below).
3. Click **Analyze**, or press `Cmd+R` / `Ctrl+R`.
4. Progress messages stream into the log as sequences get processed.
5. When it finishes, results are cached to `~/.rsas/Data/Outputs/rna_results.csv` and `rna_results.xlsx`. That's the working copy; Export (below) is how you save a named file wherever you want it.

How long it takes depends mostly on two things: how many sequences, and whether the partition function is on. A few dozen short leaders with MFE only is basically instant. A few thousand sequences with PF enabled is a coffee break, and that's where the CPU-cores setting earns its keep.

### What happens to each sequence

For every sequence, RSAS:

1. Folds the full-length sequence at each temperature (MFE, plus PF if enabled).
2. Finds the hairpin, terminal or RBS-based depending on your setting.
3. Folds that hairpin on its own at each temperature.
4. Measures composition (AU%, GC%, GU%) for the full sequence and the hairpin.
5. Locates the Shine-Dalgarno / RBS and computes its paired percentage at each temperature.
6. Runs your motif search, if you turned it on, and measures sequestering for every hit.
7. Checks each MFE and composition value against the ranges you set.
8. Adds up the quality scores from how many checks passed.
9. Writes the enabled columns to CSV and Excel.

---

## Settings page

The Settings page is a set of cards, each opening its own dialog.

### Analysis Settings

Three tabs.

**Hairpin Detection.** Two methods, and which one you want depends on where the regulatory structure sits:

- **Terminal** (the default) takes the rightmost stem-loop. Use it when the regulatory hairpin is at the 3' end of the leader, which is the common case.
- **RBS-based** finds the hairpin that actually sequesters the Shine-Dalgarno. It falls back to an AUG-based heuristic for fourU-type thermometers where the RBS sits right on the start codon, and it has a window-cut step for large or multi-branch structures. Reach for this when the regulatory hairpin isn't the last one in the sequence.

This tab also holds the filter ranges for hairpin composition (AU/GC/GU min and max) and MFE at each temperature.

**Folding Temperatures.** Set 1 to 5 temperatures (default 25, 37, 42). The lowest one is always the "base" used for hairpin detection and for the difference columns. Add and remove rows with the + and - buttons. Everything downstream, column headers, CSV keys, Excel tabs, re-derives from this list, so if you switch to 15/25/37 the whole report follows.

**RBS Window.** This is where the ribosome binding site search gets configured. It used to be hardcoded; now you control it.

- **Anchor pattern**: what RSAS anchors the RBS search on. IUPAC-aware, so `AUG` is literal but `DTG` matches all three bacterial start codons (AUG, GUG, UUG).
- **Anchor side**: use the first or the last match in the sequence.
- **Spacing window**: how many nucleotides upstream of the anchor to scan for the G-rich RBS. Default 5 to 13.
- **Apply to this run only**: try settings for one run without touching your saved default. When an override is live, the Analyze screen shows a banner so you don't forget it's on.

Leave this tab alone and RBS detection behaves exactly like older versions did.

### Performance

A small dialog for CPU cores. Set 1 for sequential (fine for small runs), or more to fold sequences in parallel. The dialog shows your machine's total core count for reference. For files of 100+ sequences, 2 to 4 cores is a noticeable speedup.

### Output Columns

This dialog decides what ends up in your CSV and Excel, and it matters for speed: only enabled columns get computed, so trimming columns you don't need makes runs faster.

**Quick presets:**

- **Hairpin Analysis**: hairpin structure, composition, MFE, quality score.
- **Full Sequence Analysis**: full-length MFE, composition, range checks, quality score.
- **Riboswitch**: the RBS sequestering columns plus partition-function accessibility.
- **Full Export**: everything on.

**Custom presets:** save your current selection under a name, then load or delete it later. They live in `~/.rsas/csv_output_settings.json`.

**Column groups** (each collapsible, and collapsed by default, so expand or use the search box to find a column): Basic Info, Full-Length MFE, Composition, Range Checks, RBS Sequestering, Hairpin Info, Partition Function, Motif Finder, Quality Scores.

Some columns are derived from others. If you enable a derived column, RSAS turns on the columns it depends on automatically, and it warns you if you try to disable a column that another enabled column needs.

### Motif / Sequence Finder

Set up a pattern to search for in every sequence.

- Toggle the search on or off.
- Enter any IUPAC pattern, for example `AGGAGG`, `UAUAAUGU`, or `NNUANN`.
- The degenerate codes: R = A|G, Y = C|U, S = G|C, W = A|U, K = G|U, M = A|C, B = C|G|U, D = A|G|U, H = A|C|U, V = A|C|G, N = anything.
- Click **Validate** to check the pattern and see how a degenerate one expands.

It reports every overlapping match, not just the best. For each sequence you get:

- `motif_count`: how many matches.
- `motif_match_seq`: the matched subsequences, semicolon-separated when there's more than one.
- `motif_match_pos`: positions, 0-based and half-open.
- Paired percentage, dot-bracket, and PF accessibility at each temperature.
- Temperature-difference columns (paired% at 42 minus paired% at 25, for instance).
- A Motif Matches tab in the Excel file, one row per hit per sequence.

### Quality Score Builder

Define what the quality score actually measures. There's a builder for the hairpin score and one for the full-length score; they work the same way. For each criterion you pick a metric (MFE at a given temperature, a composition value, a partition-function value, and so on), set a target min and max, a weight (1 to 5), and an optional **grace** zone. Grace gives partial credit just outside the range instead of a hard pass/fail, so a value a little off-target isn't scored the same as one wildly off. A live formula preview shows how the pieces combine.

Below the criteria you can edit the **classification tiers**: the labels and percentage thresholds that turn a weighted score into a class (the defaults are the Tier 1 to Tier 5 bands described in [How it works](methods.md#quality-scoring)). You can keep several named profiles and switch between them. Metrics that need the partition function are flagged, so you'll know to enable PF if you want to score on them.

### Sequence Options

Tweak input sequences before folding. The main use is appending a sequence (an AUG, say) to the start or end of every input, handy when your file is missing a start codon or some other element you want included in the fold.

---

## Sequence Extractor page

Pull the region around a gene before you analyze it: its 5' leader, its 3' end, or both. Output is a FASTA you load on the Analyze page.

**Direction.** Choose **Upstream** (bases before the CDS start, the promoter / 5' UTR), **Downstream** (bases after the CDS end, the terminator / 3' UTR), or **Both**, which writes the upstream and downstream regions as separate entries per gene. Then set the lengths: upstream defaults to 300 bp, downstream to 200 bp. There's also an optional **second window** if you want to extract two regions of different lengths in one run.

**Local Files tab:** point it at a genome **FASTA** and a **GenBank** annotation file, pick the direction and lengths, and run.

**Fetch from NCBI tab:** enter an accession, give an **email** (NCBI requires one for programmatic access), choose where to save the download, and RSAS fetches the genome and annotations for you and fills in the Local Files tab. Needs an internet connection and biopython.

---

## Synthetic Pool Generator page

Make random RNA pools for in-vitro selection or computational screening.

### Building the template

A template is a list of segments, concatenated left to right:

- **Random region**: a stretch of random A/C/G/U, you set the length.
- **Fixed motif**: an IUPAC pattern like `GGAGG`. Degenerate characters get resolved to a random matching base for each generated sequence.

You can have up to 10 segments, and you can drag a segment by its handle to reorder it. A live preview shows the template as you build it.

The built-in RBS + AUG preset, for example, produces:

```
R(84) + GGAGG + R(8) + AUG = 100 nt per sequence
```

### Presets

**Custom** starts you from scratch; **RBS + AUG** loads the standard library layout above. Click **Load Preset** to fill in the segment list.

### Composition targets (optional)

Turn on filtering to keep only sequences whose composition lands in a target range. GC%, AU%, and GU% each have their own target and tolerance, all independent, all off by default. When a target is on, sequences that miss it are discarded (rejection sampling), so very tight targets can slow generation down or, if they're impossible, never finish, worth keeping in mind.

One thing the dialog warns about, and it's easy to miss: the composition is measured over the **whole** generated sequence, fixed motifs included, not just the random regions. If a chunk of your template is fixed, that fixed content pulls the numbers, so set targets that account for it.

### Output

Set the pool size, optionally fix a random seed for reproducibility, choose an output path (FASTA by default), and click **Generate**. Progress shows in the log.

---

## RNArobo Search page

This searches for *structural* motifs, the kind defined by base-paired helices and unpaired loops, rather than a flat nucleotide string. It drives the bundled [RNArobo](https://github.com/rampasek/RNArobo) 2.1.0 engine.

### Building a descriptor

A descriptor is an ordered list of elements that describe the motif 5' to 3'. The element types:

- **Helix (`h`)**: a paired stem. Allows G-U wobble by default; you can set how many mismatches and mispairs to tolerate.
- **Single-stranded (`s`)**: an unpaired region, optionally constrained to a specific sequence.
- **Relational (`r`)**: like a helix but with a custom pairing transformation string.

Any element can also allow insertions with their own nucleotide constraints. Use the interactive builder to stack elements up, or start from a preset. Order matters, since it defines the layout of the motif.

### Running it

Sequences loaded on the Analyze page carry over, or you can point the dialog at a FASTA. Build a descriptor (the motif-map field plus the "auto-fill elements" button is the fast way to scaffold it), or load a preset, then run. You get back which sequences contain the motif and where, and you can export the matches as TSV.

A few search options worth knowing:

- **Both strands** (`-c`, on by default): also searches the reverse complement.
- **Non-overlapping** (`-u`, off by default): reports only disjoint matches.
- **N-ratio threshold** (optional): skips sequences whose fraction of `N` bases exceeds the value you set.

One caveat: the `rnarobo` binary ships only for macOS. On Windows or Linux, put a built `rnarobo` on your PATH (or in `bin/<platform>/`) and it'll be picked up.

---

## Pseudoknot Finder page

Standard MFE folding (ViennaRNA) can't represent pseudoknots, the crossing base pairs you find in many riboswitches and structured RNAs. This page predicts them with the bundled [Knotty](https://github.com/HosnaJabbari/Knotty) engine, which uses the DP09 energy model.

Load sequences (carried over from Analyze, or from a FASTA), run, and for each one you get whether a pseudoknot is present, the predicted dot-bracket (with pseudoknot brackets), and the minimum free energy. Results export to CSV.

Two parameters matter here, because pseudoknot prediction is expensive (its cost grows with the fourth power of length):

- **Max length** (default 500 nt). Sequences longer than this are **skipped**, not folded. If your long sequences seem to vanish from the results, this is why. Raise it only if you're prepared to wait.
- **Timeout** (default 120 seconds per sequence). A sequence that doesn't finish in time is reported as an error rather than holding up the batch.

Reference: Jabbari et al. (2018), *Bioinformatics* 34(22):3849-3856. Same platform caveat as RNArobo: macOS is bundled, other platforms need a `knotty` binary on PATH.

---

## Exporting results

When a run finishes:

1. Click **Export**, or press `Cmd+E` / `Ctrl+E`.
2. Pick a location. It defaults to Downloads with a timestamped filename so you don't clobber an earlier export.
3. Choose **Excel (.xlsx)** or **CSV (.csv)**.
4. Optionally open the containing folder afterward.

### The Excel file

Up to three tabs:

| Tab | What's in it |
|---|---|
| **Full Sequence** | Full-length data: structure per temperature, MFE, composition, RBS sequestering, range checks, quality scores |
| **Hairpin Analysis** | The extracted hairpin: detection method, sequence and structure, composition, MFE, PF data, quality scores |
| **Motif Matches** | One row per motif hit per sequence: position, matched subsequence, paired%, structure, PF accessibility per temperature, diffs |

The Motif Matches tab only shows up if motif search was on and something matched. Each tab carries only the columns that were enabled when you ran the analysis.

### The CSV file

One flat table with every enabled column. Where the motif finder produced multiple values for a sequence, those fields are semicolon-separated.

---

## Scripting it without the GUI

You can run the analysis straight from Python.

```python
from pathlib import Path
from RnaThermofinder.core import FastaParse, HairpinAnalysis

# Load sequences
sequences = FastaParse.read_fasta("input.fasta")

# For CSV/TSV input instead:
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
    # Full-sequence ranges:
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

To control which columns get written, build a `SettingsManager` from `settings_manager.py` and pass it as `csv_settings_manager`. The same JSON file the GUI uses works here.

### The motif finder on its own

```python
from RnaThermofinder.utils.motif_finder import (
    find_motif_occurrences,
    analyze_motif_sequestering,
)

sequence = "AUGCGGAGGCUUAAGCUAGC"
motif = "GGAGG"

hits = find_motif_occurrences(sequence, motif, allow_overlap=True)
for h in hits:
    print(f"Match at {h['start']}-{h['end']}: {h['matched_seq']}")
```

### The pool generator on its own

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
| `Cmd/Ctrl + O` | Open the file browser |
| `Cmd/Ctrl + R` | Run the analysis |
| `Cmd/Ctrl + E` | Export results |

---

## Tips from actually using it

- Start with the **Hairpin Analysis** preset for quick screening, then switch to **Full Export** once you've found something worth a closer look.
- Use **RBS-based detection** when the regulatory hairpin isn't the rightmost one, nested or multi-branch structures are exactly where terminal mode gets it wrong.
- **Turn off PF columns** when you don't need them. The partition function is the single most expensive part of a run, and most screening passes don't need ensemble numbers.
- The **temperature-difference columns are your main signal.** A thermometer shows a big drop in paired% at the RBS (or a motif) between the base temperature and the high one. That delta is what you're hunting for; everything else is context.
- **Match your temperatures to your biology.** Cold-shock element? Try 15/25/37. Heat-shock? 37/42/50. The defaults are a starting point, not a rule.
- **Quality scores come out sorted high to low,** so your best candidates are already at the top of the export.
- For big batches, bump the cores in **Performance** to 2 to 4. Past that you hit diminishing returns on most machines.
- In the **pool generator**, composition targets bias your library toward a GC range. Useful, but tight targets make rejection sampling slow, so loosen the tolerance if generation drags.

---

## Where files live

Everything RSAS writes lives under `~/.rsas/` in your home folder, not next to the app. That's deliberate: it means the app keeps working when it's installed as a read-only bundle.

| Path | What it is |
|---|---|
| `~/.rsas/Data/Outputs/rna_results.csv` | Working copy of the most recent run (CSV) |
| `~/.rsas/Data/Outputs/rna_results.xlsx` | Working copy of the most recent run (Excel) |
| `~/.rsas/csv_output_settings.json` | All your settings: columns, temperatures, RBS config, scoring profiles, presets (the name is historical; it holds more than columns) |
| `~/.rsas/.recent_files.json` | The recent-files list (created automatically) |
| `Examples/` | Sample FASTA files in the repo, to try things out |

Export writes a separate, named copy wherever you choose (it defaults to your Downloads folder with a timestamped filename), so the `~/.rsas` copies are just the latest working output.

---

## FAQ

**Can I use DNA sequences with T instead of U?**
RSAS works in RNA (A, C, G, U). T's get folded as U, but convert them first so your output columns read the way you expect. Any sequence editor will do a find-and-replace.

**How is the quality score calculated?**
Each score (hairpin and full-length) counts how many of your configured criteria fall in range. With the defaults that's 6 criteria, MFE at each of three temperatures plus three composition checks, so scores run 0 to 6. Change the criteria in the Quality Score Builder.

**MFE versus PF, what's the difference?**
MFE gives you one structure, the single most stable one, where every base is either paired or not. The partition function considers the whole ensemble of possible structures weighted by energy, so instead of a yes/no it gives a probability of being unpaired at each position. PF is more informative and slower.

**Can I add my own pool-generator presets?**
The only built-in is RBS + AUG, but you can build any layout by hand with the Add Segment buttons. If your lab reuses a layout, add it to the `PRESETS` dict in `synthetic_pool_generator.py`.

**RNArobo or Pseudoknot Finder says the engine isn't available.**
Those tools call bundled binaries that ship for macOS only. On Windows or Linux, build `rnarobo` / `knotty` and put them on your PATH (or in `bin/<platform>/`).

**How do I cite RSAS?**
See the Citation section in the [README](../README.md).
