# Features and tools, in depth

One page per feature and tool, each grounded in the code: what it does, every option, what it produces, how it works, a worked example, and the gotchas. These are the canonical reference. The [usage guide](../usage.md) is the short overview that links here; [methods](../methods.md) covers the underlying algorithms; [output columns](../output-columns.md) defines every result column.

## Core analysis

- **[Folding and temperatures](folding-and-temperatures.md)**: MFE folding, the ViennaRNA model settings, and the 1-to-5 configurable temperatures.
- **[Partition function](partition-function.md)**: ensemble energy, pairing probabilities, and RBS accessibility (the optional, slower path).
- **[Hairpin detection](hairpin-detection.md)**: terminal vs RBS-based detection and the stem-loop extraction.
- **[RBS detection](rbs-detection.md)**: the configurable anchor and window, and RBS sequestering.
- **[Composition](composition.md)**: full-sequence nucleotide frequencies and hairpin base-pair fractions.
- **[Quality scoring](quality-scoring.md)**: criteria, weights, grace zones, tiers, and the Quality Score Builder.

## Tools

- **[Motif / Sequence Finder](motif-finder.md)**: search every sequence for an IUPAC pattern and measure its sequestering.
- **[Synthetic Pool Generator](synthetic-pool.md)**: build random RNA pools from a segment template.
- **[Sequence Extractor](sequence-extractor.md)**: pull upstream/downstream regions from local files or NCBI.
- **[RNArobo Search](rnarobo-search.md)**: structural motif search (helices and loops).
- **[Pseudoknot Finder](pseudoknot-finder.md)**: pseudoknot prediction with Knotty.
