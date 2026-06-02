# Changelog

All notable changes to RSAS (RNA Structure Analysis Suite) will be documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Removed
- Switch Finder is gone from the public release. The temperature-switching tool,
  its nav item, page, dialog, and the `switch_finder` and `switch_finder_dialog`
  modules, is no longer part of RSAS. Older changelog entries that mention
  `switch_finder.py` stay as they are, since they record what happened at the time.

### Changed
- Rewrote the README, installation, and usage guides. They now cover the RNArobo
  Search and Pseudoknot Finder tools, the configurable RBS Window, the seven-page
  sidebar, and the current project layout, and they read like a person wrote them.
- Fixed two things the old docs got wrong: the PyInstaller spec is `RSAS.spec`,
  not `RNAThermoFinder.spec`, and the sample file lives at
  `Examples/Test_Thermo_RV.fasta`.
- Bumped the package version to 3.2.0 in `setup.py` so it matches the docs, and
  documented the minimum Python as 3.9 to match it.

## [3.2.0] - 2026-05-18

### Added
- **Configurable RBS anchor and window**: the ribosome binding site search is
  no longer hardcoded to "5-13 nt upstream of the last AUG". A new "RBS Window"
  tab in Analysis Settings configures the anchor pattern (IUPAC-aware, e.g.
  `DTG` matches all three bacterial start codons AUG/GUG/UUG), whether the
  first or last anchor match is used, and the min/max upstream spacing. Settings
  persist as a default or can be applied to a single run via an "Apply to this
  run only" checkbox, with an Analyze-screen banner when an override is active.
- **`RBS_Detection_Params` output column** (optional, default off): records the
  anchor/side/window used for each run, e.g. `AUG/last/5-13`.

### Changed
- RBS detection is driven by a new `RbsConfig` object threaded through the
  analysis pipeline; the duplicated `5`/`13` window literals in
  `find_rbs_in_hairpin` and `find_rbs_containing_hairpin` are now a single
  source of truth. The AUG fallback (`find_aug_containing_hairpin`) honors the
  configured anchor, with its pairing threshold generalized to ceil(2/3 x L).
- Default behavior is unchanged: with default settings the RBS search is
  byte-identical to previous releases.

## [3.1.0] - 2026-03-23

### Added
- **Pseudoknot Finder (Knotty)**: new sidebar page and dialog for pseudoknot prediction using the Knotty engine (Jabbari et al., Bioinformatics 2018). Wraps the Knotty binary via subprocess, supports batch FASTA input, reports dot-bracket structure with pseudoknot brackets (`[]`, `{}`), MFE energy, and pseudoknot detection flag. Includes CSV export with formula injection sanitization, configurable max sequence length (default 500 nt), and per-sequence timeout (default 120s)
- **Switch Finder**: new sidebar page and dialog for RNA thermometer and riboswitch candidate detection via sequence truncation and temperature-dependent folding. Truncates sequence at motif boundary (upstream, downstream, or both directions), folds at each temperature with ViennaRNA, computes paired% switch score (MFE) and accessibility switch score (PF). Classifies hits as Strong/Moderate/Weak thermometer, Riboswitch candidate, Accessible, or No switch. Includes partner extraction, CSV export, and threaded batch processing

### Fixed

#### Critical (scientifically wrong)
- **RNArobo FASTA output silently returned 0 matches**: GUI exposed a `-f` (FASTA output) checkbox, but the output parser only handles tabular format. FASTA output produced zero parsed results with no error. Removed the checkbox from the GUI
- **Riboswitch classification checked only T_low paired%**: code checked `paired_pct(T_low) >= 70%` but documentation stated "paired at all temps." Now verifies `paired_pct >= 70%` at every temperature in the series
- **Switch Finder flank parameters swapped for downstream direction**: `flank_3prime` and `flank_5prime` had opposite meaning depending on direction, producing incorrect truncation windows for downstream analysis. Renamed to direction-neutral `flank_past_motif` and `context_limit`

#### High
- **`0.0 or -999.0` Python falsy bug** (switch_finder.py): switch score of exactly 0.0 was treated as -999.0 in "both" direction comparison due to `or` short-circuit. Fixed with explicit `is not None` check
- **O(n^2) memory for BPP matrix** (switch_finder.py): dense `np.zeros((n,n))` replaced with `np.zeros(n)` sparse accumulation. For 10,000 nt: ~800MB -> ~80KB
- **Knotty help text had malformed pseudoknot example**: `((([[..))..]]` has mismatched parentheses. Corrected to valid H-type pseudoknot notation
- **Silent T->U conversion in Knotty**: DNA sequences were converted to RNA with no user notification. Now logs conversion count when thymines are detected

#### Medium
- **Single-temperature switch analysis silently produced N/A**: changed validation to require >= 2 temperatures with descriptive ValueError
- **Classification threshold magic numbers duplicated**: extracted to named constants (`STRONG_THERMO_THRESHOLD`, etc.) and single `_classify_switch()` helper
- **Progress callback flooding UI**: 1000+ sequences scheduled 1000+ `after(0,...)` callbacks. Throttled to log every 10%
- **FASTA parser accepted comment lines**: lines starting with `;` were included as sequence data. Added skip for blank and comment lines
- **Knotty energy regex fallback too greedy**: standalone energy parser could match diagnostic numbers. Tightened to require number-only lines
- **Knotty IUPAC ambiguity codes silently stripped**: now warns user when N/R/Y/etc. bases are removed from sequences
- **Knotty missing simfold/params in PyInstaller build**: added `--add-data` for energy parameter files in build_app.py
- **Switch Finder sort key non-deterministic**: added `start` position as secondary sort key
- **macOS `grab_set()` timing bug in 10 dialog classes**: replaced immediate `grab_set()` with `after(100, _try_grab)` across all 8 dialog files
- **No cancel button for batch analysis**: added cancel mechanism (threading.Event + Cancel button) to Switch Finder and Knotty dialogs

#### Low
- **SettingsManager thread safety**: added `threading.Lock` around get/set temperatures, save_settings, and get_enabled_columns
- **Missing `openpyxl` hidden import** in PyInstaller build config
- **Knotty help text missing DP09 ligand caveat**: added note that energy model does not account for ligand-RNA interactions
- **Double T->U conversion**: FASTA parser and wrapper both converted; consolidated to wrapper only
- **CSV injection sanitization**: added `_sanitize_csv()` with quote-prefix for `=`, `+`, `-`, `@` in Knotty and Switch Finder CSV export

## [3.0.1] - 2026-03-11

### Added
- **RNArobo Search integration**: new sidebar page and dialog for structural motif searching using the RNArobo engine. Includes a descriptor builder GUI with preset motifs (Simple Hairpin, Two-Stem Junction, Thermometer-like), auto-fill from motif map, real-time descriptor preview, threaded search execution, and TSV export of results
- `get_user_data_dir()` helper in `settings_manager.py`: all mutable data (settings, recent files, default outputs) now stored in `~/.rsas/` so the app works correctly when distributed as a read-only macOS `.app` bundle
- macOS DMG installer with `Install RSAS.sh` script that auto-strips quarantine flags

### Fixed

#### Critical
- **`_build_pair_map` crash on sub-sliced structures** (`HairpinAnalysis.py`): window-cut sub-structures from `find_rbs_containing_hairpin` and `find_aug_containing_hairpin` could have unmatched closing brackets, causing an `IndexError` when popping from an empty stack. Added guard: `if not stack: continue`
- **Broken `pip install` entry point** (`main.py` / `setup.py`): `main.py` had no `main()` function, and root-level modules (`main.py`, `settings_manager.py`) were not included in pip installs because `find_packages()` only finds directories with `__init__.py`. Added `def main()` wrapper and `py_modules=["main", "settings_manager"]` to `setup.py`

#### High: macOS UI freezes
- **8 messagebox calls missing `parent=`** (`quality_score_builder.py`): on macOS, messageboxes without a parent appear behind the modal dialog, freezing the entire application with no way to dismiss them. Added `parent=self.dialog` to all 8 calls
- **2 file dialog calls missing `parent=`** (`RNAGUI.py`): `filedialog.askopenfilename` and `filedialog.asksaveasfilename` could appear behind the main window. Added `parent=self.root`
- **1 confirmation dialog missing `parent=`** (`RNAGUI.py`): `messagebox.askyesno` in the clear-results handler. Added `parent=self.root`
- **`quality_score_builder.py` window close leak**: closing via the X button bypassed `grab_release()`, leaving the grab active and blocking all input. Added proper `_close()` method with `grab_release()` before `destroy()`, and `WM_DELETE_WINDOW` protocol handler

#### High: Data correctness
- **T→U normalization missing in `calculate_composition`** (`analysis_helpers.py`): DNA sequences (containing T) passed through without conversion, producing incorrect AU/GC/GU composition percentages. Added `.upper().replace("T", "U")`
- **Non-deterministic output sort** (`HairpinAnalysis.py`): results with tied quality scores could appear in different orders across runs, breaking reproducibility for publication. Added secondary sort key by sequence name
- **Concurrent analysis data corruption** (`RNAGUI.py`): `Cmd+R` keyboard shortcut called `run_analysis()` directly, bypassing the disabled-button check. Two concurrent analysis threads would write to the same `self.results`, progress bar, and output files. Added `_analysis_running` flag guard
- **Python 3.8 falsely advertised** (`setup.py`): code uses `list[str]` and `dict[str, ...]` syntax (PEP 585, requires Python 3.9+), but `setup.py` declared `python_requires=">=3.8"`. Updated to `">=3.9"` and removed Python 3.8 from classifiers

#### High: PyInstaller / distribution
- **Output directory inside read-only `.app` bundle** (`RNAGUI.py`): `Path(__file__).parent.parent.parent / "Data" / "Outputs"` resolves inside the `.app` on macOS, causing write failures. Now uses `get_user_data_dir() / "Data" / "Outputs"`
- **Recent files path inside read-only `.app` bundle** (`RNAGUI.py`): same issue with `.recent_files.json`. Now uses `get_user_data_dir() / ".recent_files.json"`
- **Settings file uses unpredictable CWD** (`settings_manager.py`): `Path("csv_output_settings.json")` resolves relative to CWD, which is unpredictable in PyInstaller. Now defaults to `get_user_data_dir() / filename`
- **Deprecated `--deep` codesign flag** (`build_app.py`): Apple deprecated the `--deep` flag. Removed it from the `codesign` call
- **Import ordering bug** (`HairpinAnalysis.py`): `sys.path.insert()` was placed *after* `from settings_manager import SettingsManager`, so the module could only be imported if something else had already modified `sys.path`. Moved path setup before all project imports
- **Missing `sys.path` setup** (`settings_dialog.py`): imported `from settings_manager import DEFAULT_TEMPERATURES` without adding the project root to `sys.path`. Only worked by accident when imported through `RNAGUI.py`. Added explicit path setup

#### Medium
- **3 silent partition function exceptions** (`HairpinAnalysis.py`): `except Exception: pass` blocks at PF computation sites silently swallowed errors, making failures invisible. Changed to log warnings to stderr
- **Silent motif analysis exception** (`HairpinAnalysis.py`): broad `except Exception: pass` hid failures in motif analysis. Changed to log with sequence name to stderr
- **Mutable default arguments** (`HairpinAnalysis.py`): `temps=[25,37,42]` and `temps: List[int] = [25, 37, 42]`, mutable defaults shared across calls. Changed to `temps=(25,37,42)` and `Optional[List[int]] = None` with guard
- **Empty motif guard** (`motif_finder.py`): empty or whitespace-only motif pattern caused unnecessary processing. Added early return for empty motifs
- **Fractional temperatures silently truncated** (`settings_dialog.py`): float values like `37.5` were silently cast to `int`. Now explicitly rejected with an error message
- **IntVar crash on CPU cores** (`settings_dialog.py`): non-integer input in the CPU cores field raised `TclError`. Wrapped in try/except with user-friendly error message
- **Tooltip dark mode** (`settings_dialog_csv.py`): hardcoded light-mode colors (`#f8f9fa` background) appeared as bright white boxes in dark mode. Now detects appearance mode and uses appropriate colors
- **Tooltip Toplevel leak** (`settings_dialog_csv.py`): rapidly hovering between elements could create multiple tooltip windows. Added `_hide()` cleanup before creating new tooltip, with `TclError` guard on destroy
- **KeyError on corrupted settings** (`settings_dialog_csv.py`): direct dict access `self.settings_manager.settings["csv_output_columns"]` could crash on corrupted settings files. Changed to `.get("csv_output_columns", {})`
- **Toast race condition** (`settings_dialog_csv.py`, `sequence_settings_dialog.py`): toast duration (3500ms) exceeded dialog destroy timing (1200ms), causing `TclError` on dismiss. Reduced to `duration=1000`
- **Drag-and-drop path corruption** (`RNAGUI.py`): `strip("{}")` would strip any of those characters from anywhere in the path. Changed to proper brace-pair stripping: `if path.startswith("{") and path.endswith("}"): path = path[1:-1]`
- **`_open_recent` ValueError** (`RNAGUI.py`): `self._recent_files.remove(path)` could raise `ValueError` if path was already removed. Added existence check before removal
- **`.as_posix()` in sys.path** (`settings_dialog_csv.py`): used `.as_posix()` which produces forward-slash paths on Windows. Changed to standard `str(Path(...))`

#### Low
- **Toast `_dismiss` exception scope too broad** (`RNAGUI.py`, `settings_dialog_csv.py`, `sequence_settings_dialog.py`): `except Exception` in toast dismiss handlers caught everything; narrowed to `except tk.TclError`
- **Unused import** (`RNAGUI.py`): removed unused `SettingsDialogModern` import
- **JSON I/O encoding** (`settings_manager.py`): missing `encoding='utf-8'` on file open calls, could cause encoding issues on some systems. Added explicit encoding
- **Save error handling** (`settings_manager.py`): only caught `IOError`; added `TypeError` and `ValueError` for robustness

### Known Issues (deferred, require design decisions)
- `quality_scoring.py`: weight clamping at `max(1.0)`, needs a decision on whether to allow fractional weights
- `quality_scoring.py`: N/A metrics count as 0 in the denominator, needs a decision on scoring methodology
- `settings_manager.py`: `set_temperatures()` does not auto-update scoring profiles, needs a migration strategy
- `sys.path` hacks across 5 files: functional but inelegant; the proper fix is moving `settings_manager.py` into the package

## [3.0.0] - 2025-02-23

### Added
- Rebranded from RNA Thermometer Finder to RSAS: RNA Structure Analysis Suite
- Modern CustomTkinter GUI with sidebar navigation, dark/light mode support
- Dual quality scoring system (hairpin 0-6, full-length 0-6)
- Drag-and-drop file input
- Keyboard shortcuts (Cmd/Ctrl+O, R, E)
- Toast notifications for user feedback
- **Customizable folding temperatures**: configure 1-5 folding temperatures instead of the fixed 25/37/42. All output columns, CSV headers, and Excel tabs update dynamically based on the configured temperatures
- **Motif / Sequence Finder**: search for any user-defined nucleotide pattern (IUPAC-aware, including degenerate codes like R, Y, N) across all input sequences. Reports paired percentage, dot-bracket structure, and partition-function accessibility at each temperature. Includes temperature difference columns to detect thermometer-like behavior
- **All motif matches reported**: every overlapping occurrence of the motif is shown (semicolon-separated in the CSV summary columns). A dedicated "Motif Matches" Excel tab provides one row per hit per sequence with full detail
- **Synthetic Pool Generator**: generate pools of random RNA sequences with user-defined segment layouts (random regions + fixed IUPAC motifs). Includes a preset for RBS+AUG (R84 + GGAGG + R8 + AUG). Optional composition filtering by GC%, AU%, and/or GU% with independent target and tolerance per metric. Output is FASTA format
- **Terminal Hairpin Quality Score Builder**: interactive dialog for configuring the criteria and weights used in the hairpin quality scoring system
- **Bidirectional upstream sequence extractor**: supports extracting sequences from either side (upstream or downstream) of a feature, with configurable inclusion/exclusion of the start codon
- **Separate settings dialogs**: Analysis Settings (hairpin detection + folding temperatures) and Performance Settings (CPU cores) are now independent cards with their own dialogs
- **Sidebar navigation for new tools**: Synthetic Pool Generator and Sequence Extractor each have their own page accessible from the sidebar

### Changed
- Complete GUI rewrite from legacy tkinter to CustomTkinter
- Card-based settings page with separate Analysis Settings and Performance cards
- Excel export now supports up to 3 tabs (Full Sequence, Hairpin Analysis, Motif Matches) depending on enabled features
- All internal column key generation uses the configured temperature list dynamically

### Fixed
- `gc_content()` in HairpinAnalysis.py now handles empty strings without ZeroDivisionError
- Synthetic pool dialog segment type callback correctly captures the segment index
- Consistent use of `t_first` variable in hairpin Excel column builder

## [2.1.0] - 2025-02-14

### Added
- RBS-based hairpin detection with AUG fallback for fourU-type thermometers
- Upstream sequence extractor (local files and NCBI fetch)
- Sequence Options dialog for appending sequences before analysis
- Partition function columns (ensemble energy, mean paired prob, RBS accessibility)
- Full-length RBS sequestering at each temperature with difference columns
- Output Columns presets (Hairpin, Full Sequence, Riboswitch, Full Export) and custom presets
- Excel export with Full Sequence and Hairpin Analysis tabs
- Tooltips throughout the GUI

### Changed
- CPU cores default to 1 (sequential) instead of auto
- Export flow uses Save As with timestamped filename suggestions

## [2.0.0] - 2024-12-18

### Added
- Original sequence quality scoring (0-6)
- Original sequence MFE and composition range filters
- Conditional calculation system (only computes enabled columns)

### Changed
- Analysis Settings includes original sequence ranges
- Quality score naming: Quality_Score to Quality_Score_Hairpin

### Fixed
- Fallback CSV headers include all original sequence columns
- Column mapping consistency in analysis_helpers.py

## [1.0.0] - 2024-11-10

### Added
- Initial release
- Terminal hairpin detection
- Temperature-dependent MFE analysis (25, 37, 42)
- Base pair composition analysis (AU%, GC%, GU%)
- RBS identification and quality scoring (0-6)
- GUI interface with CSV export
- macOS .app bundle distribution
