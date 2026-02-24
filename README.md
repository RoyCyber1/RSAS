# RSAS: RNA Structure Analysis Suite v3.0

A desktop application for identifying and characterizing RNA thermometers, riboswitches, and other regulatory RNA structures in bacterial sequences. Built for researchers who need to screen large pools of candidate sequences and quantify structural features at multiple folding temperatures.

Previously known as RNA Thermometer Finder.

---

## What it does

RSAS takes RNA sequences as input (FASTA, CSV, or TSV), folds them at user-defined temperatures using ViennaRNA, and reports structural features relevant to post-transcriptional regulation. The core analysis pipeline:

1. Folds each sequence at every configured temperature (MFE and optionally partition function)
2. Detects the terminal hairpin or RBS-sequestering hairpin
3. Computes base-pair composition (AU%, GC%, GU%) for both full-length and hairpin
4. Identifies the Shine-Dalgarno / RBS region and measures how sequestered it is at each temperature
5. Scores each sequence against user-defined quality criteria
6. Optionally searches for custom motif patterns and quantifies their sequestering

Results are exported as CSV and Excel workbooks with up to three tabs (Full Sequence, Hairpin Analysis, Motif Matches).

---

## Features

### Core analysis
- **Hairpin detection** — two modes: terminal (rightmost stem-loop) or RBS-based (finds the hairpin that sequesters the Shine-Dalgarno, with AUG fallback for fourU-type thermometers)
- **Customizable folding temperatures** — configure 1 to 5 temperatures (not limited to 25/37/42). All columns, keys, and Excel headers update dynamically
- **MFE folding** — minimum free energy structure at each temperature via ViennaRNA
- **Partition function** (optional) — ensemble energy, mean paired probability, and per-nucleotide unpaired probabilities for accessibility analysis
- **RBS sequestering** — Shine-Dalgarno detection, paired percentage at each temperature, and temperature-difference columns to spot thermometer-like responses
- **Composition analysis** — AU%, GC%, GU% for full-length sequence and extracted hairpin, with configurable "in range" filters

### Motif / Sequence Finder
- Search for any nucleotide pattern using IUPAC degenerate codes (R, Y, S, W, K, M, B, D, H, V, N)
- Reports **all overlapping matches** (not just the best one) with paired percentage, dot-bracket structure, and PF accessibility at each temperature
- Semicolon-separated summary columns in the main CSV; dedicated "Motif Matches" Excel tab with one row per hit per sequence
- Temperature-difference columns highlight motifs that become more accessible at elevated temperatures

### Synthetic Pool Generator
- Build random RNA sequence pools from a customizable template of segments (random regions + fixed IUPAC motifs)
- Built-in preset: RBS + AUG layout (R84 + GGAGG + R8 + AUG)
- Optional composition filtering by GC%, AU%, and/or GU% with independent targets and tolerances
- FASTA output, configurable pool size and random seed for reproducibility

### Quality scoring
- **Terminal Hairpin Quality Score** (0-6) — how many hairpin criteria (MFE and composition at each temp) fall within the configured ranges
- **Full-Length Quality Score** (0-6) — same idea applied to the full sequence
- **Quality Score Builder** — interactive dialog for defining which criteria matter and how they're weighted

### Upstream sequence extraction
- Extract sequences upstream (or downstream) of a genomic feature from local genome + annotation files
- Fetch sequences directly from NCBI by accession
- Configurable region length, start codon inclusion, and direction

### Output and export
- **CSV** with only the columns you've enabled (configurable via Output Columns dialog)
- **Excel** workbook with up to 3 tabs: Full Sequence, Hairpin Analysis, and Motif Matches
- Built-in output presets: Hairpin Analysis, Full Sequence Analysis, Riboswitch, Full Export
- Save/load custom column presets
- Export to any location with timestamped filename suggestions

### GUI
- Modern CustomTkinter interface with dark and light mode support
- Sidebar navigation: Analyze, Results, Settings, Sequence Extractor, Synthetic Pool
- Drag-and-drop file input
- Keyboard shortcuts (Cmd/Ctrl+O open, Cmd/Ctrl+R run, Cmd/Ctrl+E export)
- Multiprocessing with configurable CPU core count
- Progress logging with toast notifications

---

## Quick start

### Pre-built app (no Python needed)

1. Download the latest release from [Releases](https://github.com/RoyCyber1/RNAThermoFinder/releases)
2. Unzip and double-click `RSAS.app` (macOS) or `RSAS.exe` (Windows)
3. If macOS blocks it: right-click the app, click Open, then click Open again

### From source

```bash
# 1. Install ViennaRNA (required for folding)
brew install viennarna          # macOS
# sudo apt-get install viennarna  # Ubuntu/Debian

# 2. Clone and install
git clone https://github.com/RoyCyber1/RNAThermoFinder.git
cd RNAThermoFinder
pip install -r requirements.txt

# 3. Run
python main.py
```

See [docs/installation.md](docs/installation.md) for detailed instructions and troubleshooting.

---

## Basic workflow

1. **Load sequences** — click Browse or drag a FASTA/CSV/TSV file onto the window
2. **Configure (optional)**
   - **Analysis Settings** — set hairpin detection method, folding temperatures
   - **Performance** — set CPU core count for parallel analysis
   - **Output Columns** — pick a preset or enable/disable individual columns
   - **Motif Finder** — enter a pattern to search for across all sequences
   - **Sequence Options** — optionally append a sequence (e.g. AUG) before analysis
3. **Run** — click Analyze. Progress is shown in the log area
4. **Export** — click Export to save results as `.xlsx` or `.csv` to any location

---

## Output columns

Results include (depending on what's enabled):

| Category | Example columns |
|---|---|
| Sequence info | Name, Sequence, Structure at each temp |
| Full-length MFE | MFE at each configured temperature |
| Composition | AU%, GC%, GU%, in-range flags |
| RBS sequestering | RBS sequence, structure, paired% at each temp, temperature diffs |
| Hairpin | Detection method, sequence, structure, composition, MFE at each temp |
| Partition function | Ensemble energy, mean paired prob, RBS accessibility |
| Motif finder | Pattern, match count, match positions, paired%, structure, PF accessibility, diffs |
| Quality scores | Hairpin score (0-6), full-length score (0-6), class, breakdown |

---

## Project structure

```
RNAThermoFinder/
├── main.py                    # entry point
├── settings_manager.py        # JSON-based config persistence
├── setup.py                   # package setup
├── build_app.py               # PyInstaller build script
├── requirements.txt
├── RNAThermoFinder.spec       # PyInstaller spec
├── RnaThermofinder/
│   ├── core/
│   │   ├── FastaParse.py      # FASTA/CSV/TSV input parsing
│   │   └── HairpinAnalysis.py # main analysis pipeline
│   ├── gui/
│   │   ├── RNAGUI.py          # main application window
│   │   ├── settings_dialog.py # analysis + performance settings
│   │   ├── settings_dialog_csv.py    # output column config
│   │   ├── motif_finder_dialog.py    # motif search config
│   │   ├── quality_score_builder.py  # quality score criteria
│   │   ├── synthetic_pool_dialog.py  # pool generator UI
│   │   ├── upstream_extractor_dialog.py
│   │   └── sequence_settings_dialog.py
│   └── utils/
│       ├── analysis_helpers.py       # CSV/Excel output builders
│       ├── motif_finder.py           # IUPAC motif search + sequestering
│       ├── quality_scoring.py        # scoring logic
│       ├── synthetic_pool_generator.py
│       └── upstream_extractor.py
├── Data/
│   ├── Inputs/                # place input files here
│   └── Outputs/               # analysis results written here
└── docs/
    ├── installation.md
    └── usage.md
```

---

## Building from source

To create a standalone app bundle:

```bash
pip install pyinstaller
python build_app.py
```

This produces `dist/RSAS.app` (macOS), `dist/RSAS.exe` (Windows), or `dist/RSAS` (Linux).

You can also use the spec file directly:

```bash
pyinstaller RNAThermoFinder.spec
```

---

## Documentation

- **[Installation guide](docs/installation.md)** — system requirements, ViennaRNA setup, Python dependencies, verification, troubleshooting
- **[Usage guide](docs/usage.md)** — GUI walkthrough, all settings dialogs, output format details, scripting API, tips

---

## Citation

If you use RSAS in published research:

```
Vaknin, R. (2025). RSAS: RNA Structure Analysis Suite v3.0.
GitHub: https://github.com/RoyCyber1/RNAThermoFinder
```

---

## Changelog

See [CHANGELOG.md](RnaThermofinder/CHANGELOG.md) for full version history.

---

## License

MIT License — see [LICENSE.md](LICENSE.md).

## Author

Roy Vaknin
- Email: roycyber13@gmail.com
- GitHub: [RoyCyber1](https://github.com/RoyCyber1)

## Acknowledgments

- [ViennaRNA](https://www.tbi.univie.ac.at/RNA/) for RNA folding algorithms
- Dr. Abdelsayed for experimental validation data
- SCREAM team for testing and feedback
