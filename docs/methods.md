# How RSAS works

This is the methods document: what RSAS actually computes, the choices baked into those computations, and where the limits are. If the usage guide tells you which buttons to press, this tells you what the numbers mean when you press them. It's written for anyone deciding whether to trust an RSAS result in a paper.

The short version: RSAS is a thin, opinionated layer on top of [ViennaRNA](https://www.tbi.univie.ac.at/RNA/). ViennaRNA does the thermodynamics. RSAS decides what to fold, at which temperatures, which part of the structure to look at, and how to turn the result into a score you can rank on.

---

## The pipeline

For each input sequence, RSAS runs the same steps:

1. Fold the full-length sequence at every temperature you've configured.
2. Find the regulatory hairpin (terminal, or the one covering the RBS).
3. Fold that hairpin on its own at each temperature.
4. Measure base composition for the full sequence and the hairpin.
5. Locate the ribosome binding site and measure how paired it is at each temperature.
6. Optionally search for a motif and measure how sequestered each hit is.
7. Check every value against the ranges you set, and add up the quality scores.

Everything after step 1 is interpretation. Step 1 is where the physics lives.

---

## Folding

RSAS folds with ViennaRNA through its Python bindings (the `RNA` module). Every fold uses the same model settings, so results are comparable across sequences and temperatures:

- **Dangling ends**: `dangles = 2`. This is ViennaRNA's default and the most common choice in the literature; it lets dangling, unpaired bases at the ends of helices contribute stabilizing energy.
- **Lonely pairs**: `noLP = 1`. Isolated single base pairs (a helix of length one) are disallowed. Note this departs from ViennaRNA's default (`noLP = 0`); RSAS turns it on because suppressing lonely pairs keeps predicted structures closer to what forms in reality.
- **GU wobble**: `noGU = 0`. G-U wobble pairs are allowed, as they should be for RNA.
- **Temperature**: set per fold to whatever you configured. ViennaRNA rescales its energy parameters to that temperature using the same nearest-neighbor model it uses at 37 °C.

The energy model is ViennaRNA's, which means the Turner nearest-neighbor parameters. RSAS does not ship its own parameters or modify ViennaRNA's.

**Versions, for reproducibility.** Folding numbers depend on the ViennaRNA version, since its parameters and defaults have shifted across releases. The results reported here and in the worked example were produced with **ViennaRNA 2.7.2**. The bundled structural-search engines are **RNArobo 2.1.0** and **Knotty** (DP09 model). If you reproduce results, pin these versions; a different ViennaRNA release can give slightly different energies.

### MFE folding

The minimum free energy fold gives you a single structure: the one with the lowest predicted free energy, written as a dot-bracket string where each base is either paired or not. This is what feeds the hairpin detection, the composition numbers, and most of the columns. It's fast, and it's a single best guess.

### Partition function (optional)

The partition function doesn't pick one structure. It considers the whole Boltzmann ensemble of possible structures, weighted by their energies, and reports:

- **Ensemble free energy** (kcal/mol): the free energy of the entire ensemble, always at or below the MFE.
- **Mean pairing probability**: across all positions, the average probability of being paired.
- **Per-position unpaired probability**: for any region (the RBS, a motif), the probability that it's *not* sequestered.

This is more honest than MFE when a sequence has several competing structures, which is exactly the situation a thermometer is in. It's also the slowest computation in RSAS, so it's off by default and you turn it on when you want ensemble-level accessibility rather than a single-structure yes/no.

---

## Finding the hairpin

A regulatory leader often has one hairpin that matters: the stem-loop that buries the ribosome binding site at low temperature. RSAS offers two ways to find it, and the right one depends on where that hairpin sits.

### Terminal detection (default)

Take the rightmost stem-loop in the MFE structure, plus any trailing unpaired bases. This works when the regulatory element is at the 3' end of the leader, which is the common arrangement for 5' UTR thermometers feeding into a downstream start codon. It's simple and it's right most of the time.

It gets things wrong when the regulatory hairpin isn't the last one, for example in nested or multi-branch structures where a more 5' hairpin is the one doing the regulating. That's what the other mode is for.

### RBS-based detection

Instead of "the last hairpin," find the hairpin that actually sequesters the Shine-Dalgarno sequence. RSAS locates the RBS first (next section), then walks outward from it to the smallest enclosing stem-loop, crossing small unpaired gaps (bulges and internal loops) as it goes. For fourU-type thermometers, where the RBS overlaps the start codon and there's no clean separate Shine-Dalgarno, it falls back to anchoring on the start codon directly. There's also a window-cut step that keeps very large or multi-branch structures tractable.

Use this when the terminal hairpin isn't the regulatory one. It costs a little more bookkeeping but it targets the structure you actually care about.

---

## Finding the ribosome binding site

This is the most heuristic part of RSAS, so it's worth being precise about what it does.

RSAS anchors on a start codon and scans a window upstream of it for a G-rich stretch, the Shine-Dalgarno signal. The algorithm:

1. **Resolve the anchor.** Find the anchor pattern in the sequence. By default that's the literal `AUG`, taking the *last* match. The pattern is IUPAC-aware, so you can set it to `DTG` to match all three bacterial start codons (AUG, GUG, UUG), and you can choose the first match instead of the last. All of this lives in the RBS Window settings tab.
2. **Define the window.** Look at the region from `min_spacing` to `max_spacing` nucleotides upstream of the anchor. The defaults are 5 and 13, so the classic "5 to 13 nt upstream of the last AUG."
3. **Slide a 6-nucleotide window** across that region from the 5' side.
4. **Take the first 6-mer with at least 3 G's** as the RBS. The "≥3 G" rule is a deliberately loose Shine-Dalgarno detector; it catches canonical `AGGAGG`-style sites and weaker variants without requiring an exact consensus.

Two things to keep in mind. First, this is a sequence heuristic, not a validated RBS predictor; it's a reasonable rule that works well for the bacterial leaders RSAS is built for, and you can tune the anchor and window when it doesn't fit your organism. Second, with the defaults RSAS reproduces the behavior of older versions exactly, so results stay comparable across versions unless you deliberately change the settings.

Once the RBS is located, its **paired percentage** at a given temperature is just the fraction of RBS positions that are paired in that temperature's structure, times 100. That single number, tracked across temperatures, is the core thermometer signal.

---

## Composition

RSAS reports composition two different ways, and the difference matters.

For the **full sequence**, the columns are single-nucleotide frequencies: AU% is (A + U) / length × 100, GC% is (G + C) / length, GU% is (G + U) / length, with T treated as U. These describe the sequence and are temperature-independent.

For the **hairpin**, the columns mean something else: the fraction of the hairpin's base *pairs* of each type. Hairpin AU% is the share of pairs that are A-U, GC% the share that are G-C, GU% the share that are G-U wobble, computed over the pairs in the hairpin's folded structure (`base_pair_percentages` in `HairpinAnalysis.py`). Because every pair falls into one of these classes, the three hairpin percentages sum to 100. So a hairpin GU% of 30 means 30% of the hairpin's pairs are wobble pairs, not that 30% of its bases are G or U. Don't compare hairpin composition columns to full-sequence ones directly; they measure different things.

---

## Quality scoring

The quality score turns a pile of numbers into something you can sort a candidate list on. You define a profile: a set of criteria, each with a metric, a target range, a weight, and an optional tolerance. With the default three temperatures you get six criteria: one MFE check per temperature (target −17 to −2 kcal/mol) plus three composition checks (AU 50–60%, GC 0–30%, GU 15–25%), every weight 1, no tolerance. The MFE criteria scale with however many temperatures you configure, so a five-temperature run starts from eight default criteria, not six.

For each criterion, RSAS scores the value:

- Inside the range: score 1.0.
- Outside the range with a tolerance set: linear partial credit, `1 − distance / tolerance`, fading to 0 at the edge of the tolerance band. This avoids a hard cliff where a value one unit out of range scores the same as one wildly out.
- Outside, no tolerance: score 0.
- Missing data (a column that wasn't computed): scored 0, but it still counts in the denominator, so a partial run can't inflate its own score by leaving criteria out.

From the per-criterion scores you get three numbers:

- **Raw score**, written `passed/evaluated`, for example `5/6`. "Passed" means a criterion scored a full 1.0.
- **Weighted score**, a percentage: the weight-weighted average of the criterion scores, ×100.
- **Class**, a tier from the weighted percentage: Tier 1 at ≥83%, Tier 2 ≥67%, Tier 3 ≥50%, Tier 4 ≥33%, Tier 5 below that. The thresholds map onto the old 0-to-6 system (6/6 = 100%, 5/6 ≈ 83%, and so on), so a Tier 1 today is a 5/6-or-better candidate.

There's also a breakdown string listing each criterion's score, so you can see *why* a sequence landed where it did rather than just trusting the total. Results come out sorted by score, best first.

The whole profile is editable in the Quality Score Builder. The defaults are a starting point tuned for one kind of thermometer; if your biology wants different ranges, change them.

---

## Reading the thermometer signal

None of the individual columns is the answer on its own. The signal RSAS is built to surface is a *change*: an RBS (or a motif) that's paired at low temperature and unpaired at high temperature. That's what an RNA thermometer does, melt open its own ribosome binding site as the cell heats up.

So the columns to watch are the temperature-difference columns: RBS paired% at the high temperature minus paired% at the base temperature, and the same for any motif. A large negative swing (very paired when cold, much less paired when warm) is the fingerprint of thermometer-like behavior. Everything else in the output exists to give that swing context: is the hairpin stable enough to be real, is the composition plausible, does the structure hold together across the ensemble.

If you only export one set of numbers, export those diffs.

---

## The two structural-search tools

RSAS bundles two external engines for jobs ViennaRNA's standard folding can't do. They're separate from the main pipeline; they run on their own pages and produce their own output.

- **RNArobo** (Rampášek et al.) searches for *structural* motifs described by helices and loops rather than a flat sequence pattern. RSAS builds the descriptor and parses the results; the search itself is RNArobo's.
- **Knotty** (Jabbari et al. 2018, *Bioinformatics* 34(22):3849-3856) predicts secondary structures that include pseudoknots, the crossing base pairs that standard MFE folding can't represent, using the DP09 energy model. RSAS calls it per sequence and reports whether a pseudoknot is present, the structure, and the free energy. Because the algorithm scales with the fourth power of length, RSAS skips sequences over a length cap (500 nt by default) rather than folding them.

Both ship as macOS binaries; on other platforms you supply the binary.

---

## Limitations, stated plainly

- **It's secondary structure only.** RSAS predicts 2D base-pairing, not 3D structure. The main pipeline also doesn't model pseudoknots (that's what the separate Knotty tool is for).
- **The RBS detector is a heuristic.** The G-rich-6-mer rule and the default window are sensible for bacterial leaders, not a validated, organism-general RBS predictor. Check that the anchor and window fit your system.
- **Folding is only as good as the energy model.** RSAS inherits ViennaRNA's Turner parameters and their assumptions, which are calibrated for standard RNA under standard conditions. Modified nucleotides, unusual ions, and crowded cellular environments are not modeled.
- **MFE is one structure.** When a sequence has several near-degenerate folds, the single MFE structure can be misleading. Turn on the partition function to see the ensemble.
- **Scores are relative, not absolute.** A high quality score means "matches your criteria," not "is a confirmed thermometer." It's a ranking aid for prioritizing experiments, not a substitute for them.

---

## References

- Lorenz, R. et al. (2011). ViennaRNA Package 2.0. *Algorithms for Molecular Biology* 6:26.
- Jabbari, H. et al. (2018). Knotty: efficient and accurate prediction of complex RNA pseudoknot structures. *Bioinformatics* 34(22):3849-3856.
- Rampášek, L. et al. RNArobo, structural RNA motif search. https://github.com/rampasek/RNArobo
