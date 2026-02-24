# Changelog

All notable changes to RSAS (RNA Structure Analysis Suite) will be documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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

## [2.0.0] - 2025-12-18

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
