# Partition function (ensemble) analysis

Ensemble-level structure analysis that, instead of scoring one best fold, weighs every possible structure by its Boltzmann probability and reports ensemble free energy, mean pairing probability, and how accessible the RBS is across the whole ensemble.

## Overview

The minimum free energy (MFE) fold gives you a single answer: the one lowest-energy structure, written as a dot-bracket string where each base is either paired or not. It is fast and it drives most of RSAS, but it is a single best guess. When a sequence has several near-degenerate folds, that one structure can be misleading.

The partition function does not pick a structure. It considers the entire Boltzmann ensemble of possible structures, weighted by their energies, and summarizes that ensemble. So where MFE tells you "this base is paired," the partition function tells you "this base is paired with probability 0.7." That continuous, ensemble-level view is more honest when a sequence is poised between competing structures, which is exactly the situation an RNA thermometer is in.

In RSAS the partition function backs three families of output:

- **Ensemble free energy** (kcal/mol) for the full sequence and for the detected hairpin. It is always at or below the MFE, because the ensemble includes the MFE structure plus everything else.
- **Mean pairing probability** (0 to 1), the average over all positions of the probability that the position is paired.
- **RBS accessibility** (0 to 100, a percentage), how unpaired the ribosome binding site is across the ensemble, plus temperature-difference columns that express the thermometer signal at the ensemble level.

## When to use it

Turn the partition function on when you care about ensemble-level accessibility rather than a single-structure yes or no. Concretely:

- You are ranking candidate thermometers and you want a continuous accessibility signal for the RBS, not the binary paired/unpaired call that the MFE structure gives. `PF_RBS_Access_{T}C` and its difference columns are the ensemble version of the paired-percentage swing.
- A sequence has several competing folds and you do not trust any single MFE structure to represent it. Ensemble free energy and mean pairing probability tell you how committed the ensemble is.
- You are scoring with a Quality Score profile whose criteria reference a PF metric. Those criteria need PF data to evaluate.

Leave it off when speed matters more than ensemble detail. The partition function is the slowest computation in RSAS, so it is off by default. A run of a few dozen short leaders with MFE only is effectively instant; the same run with PF enabled across thousands of sequences is a coffee break. If you only need MFE structures, paired percentages, and composition, you gain nothing by turning PF on and you pay for it in wall-clock time.

## Step by step

The partition function is controlled entirely from the **Output Columns** dialog (Settings menu). RSAS only computes what you ask it to write, so enabling a PF column is what triggers the PF computation.

1. Open **Settings then Output Columns**.
2. Find the column groups. They are collapsible and collapsed by default, so expand the **Partition Function** groups or type into the search box. The relevant groups are:
   - **Partition Function, Full Sequence** (`PF_Full_Ensemble`, `PF_Full_MeanPaired`)
   - **Partition Function, Hairpin** (`PF_HP_Ensemble`, `PF_HP_MeanPaired`)
   - **Partition Function, RBS Accessibility** (`PF_RBS_Access`, `PF_RBS_Diff`)
   - **PF Ensemble Range Checks (Hairpin)** (`PF_HP_Ensemble_{T}C_InRange`)
3. Check the columns you want. RSAS decides which PF passes to run from the prefixes of the enabled columns: any enabled column starting with `PF_Full_` triggers the full-sequence partition function, and any column starting with `PF_HP_` or `PF_RBS_` triggers the hairpin and RBS-accessibility passes.
4. If you score with a Quality Score profile that references a PF metric, RSAS turns the hairpin PF pass on automatically even if you did not check a PF column, so the criterion can be evaluated.
5. Run the analysis. Only the enabled columns are computed and exported, so trimming PF columns you do not need keeps the run fast.

## Options in detail

The PF columns expand per configured temperature, so `{T}` becomes one column per temperature in your run (for example 25, 37, 42). All come from the same underlying per-temperature partition function computation.

**Full-sequence metrics.**

- `PF_Full_Ensemble_{T}C`, Ensemble free energy of the full-length sequence, in kcal/mol. This is the free energy of the whole Boltzmann ensemble at that temperature, always at or below the corresponding MFE.
- `PF_Full_MeanPaired_{T}C`, Mean pairing probability across the full sequence, a value from 0 to 1. It is the average, over every position, of the probability that the position is base-paired somewhere in the ensemble.

**Hairpin metrics.** Same two quantities computed on the trimmed detected hairpin rather than the whole sequence.

- `PF_HP_Ensemble_{T}C`, Ensemble free energy of the hairpin, in kcal/mol.
- `PF_HP_MeanPaired_{T}C`, Mean pairing probability across the hairpin, 0 to 1.

**RBS accessibility.** This is the ensemble answer to "is the ribosome binding site exposed?"

- `PF_RBS_Access_{T}C`, RBS accessibility as a percentage. It is the mean unpaired probability over the RBS positions, expressed on a 0 to 100 scale. Higher means more accessible to the ribosome. Internally it is the probability of being unpaired (1 minus paired), averaged across the RBS nucleotides, so it is a continuous 0 to 1 measure scaled to a percent.
- `PF_RBS_Diff_{hi}-{base}`, The change in RBS accessibility from the base temperature to the highest temperature. This is the ensemble-level version of the thermometer signal: a thermometer that melts open on heating should show the RBS becoming more accessible as temperature rises. Present when you have two or more temperatures.
- `PF_RBS_Diff_{mid}-{base}`, The same difference for the middle temperature. Present only with three or more temperatures.

**Range checks.**

- `PF_HP_Ensemble_{T}C_InRange`, Whether the hairpin ensemble energy falls inside the range you configured, per temperature, for filtering. It reports `In Range`, `Not in Range`, or `N/A`. It returns `N/A` when PF was not computed, when the value is 0.0, or when no range bounds are set.

## What you get

The complete column reference, with units and the exact order RSAS writes them, lives in [output-columns.md](../output-columns.md). See its **Partition function** section for the canonical table.

## How it works

The PF metrics are produced by `pf_fold_at_temp` in `RnaThermofinder/core/HairpinAnalysis.py`, which wraps ViennaRNA. For a given sequence and temperature it sets up a fold compound (dangles 2, no lonely pairs, GU pairs allowed), computes the MFE, rescales the Boltzmann factors against that MFE for numerical stability, and then calls the partition function to get the ensemble free energy and the base pair probability (BPP) matrix.

From the BPP matrix the function derives per-position quantities. The BPP entry for positions i and j is the probability that those two bases pair across the ensemble. Summing a position's row and column of that matrix gives its total **paired probability**: the probability it is paired with anything. The **unpaired probability** is simply `1 - paired`. The **mean pairing probability** reported per sequence is the sum of all per-position paired probabilities divided by the sequence length.

RBS accessibility is computed by `calc_rbs_pf_accessibility`. It locates the RBS within the folded sequence, takes the unpaired probabilities at exactly those positions, averages them, and multiplies by 100. So RBS accessibility is literally the mean per-position unpaired probability over the RBS, on a percent scale. The difference columns subtract the base-temperature accessibility from the higher-temperature values.

Multiple temperatures are handled by `pf_fold_at_temps_batch`, which calls `pf_fold_at_temp` once per configured temperature. For long inputs (default cutoff 500 nt) it does not fold the whole sequence: it windows down to a region around the last AUG start codon, because thermometer structures are local to the start codon and folding a multi-kilobase leader adds no thermometer information while costing roughly cubic time. The same windowed sequence is reused for the RBS lookup so positions line up.

For the conceptual background, see the **Partition function** section of [methods.md](../methods.md).

## Worked example

Suppose you run three temperatures, 25, 37, and 42, on a candidate fourU-type thermometer and you enable the full PF, hairpin PF, and RBS accessibility columns. A thermometer that does its job might look like this:

- `PF_Full_Ensemble_25C` is more negative than `PF_Full_Ensemble_42C`, and every ensemble energy sits at or below the matching `Original_MFE` value. The ensemble is most stable when cold.
- `PF_HP_MeanPaired_25C` is high (say around 0.7) and `PF_HP_MeanPaired_42C` is lower. The hairpin is mostly paired when cold and loosens when warm.
- `PF_RBS_Access_25C` is low (the RBS is sequestered when cold) and `PF_RBS_Access_42C` is high (the RBS is exposed when warm).
- `PF_RBS_Diff_42-25` is a large positive number, because accessibility climbed from base to high temperature.

That positive `PF_RBS_Diff_42-25`, paired with a hairpin that is stable enough to be real, is the ensemble fingerprint of thermometer-like behavior. A non-thermometer whose RBS is open at every temperature would show high `PF_RBS_Access` everywhere and a `PF_RBS_Diff` near zero.

## Tips

- **The speed tradeoff is the main thing.** PF is the slowest part of a run, off by default, and it is gated on enabled columns. Enable only the PF columns you will actually read. If you are exploring a large library, do a first MFE-only pass to triage, then enable PF on the short list.
- **CPU cores earn their keep here.** PF-heavy runs over many sequences are where the cores setting in Performance matters most, since each sequence is folded independently.
- **Long sequences are windowed automatically.** Above 500 nt, RSAS folds a window around the last AUG rather than the entire leader. This is intentional and keeps PF tractable, but it means the full-sequence PF columns for very long inputs describe the window, not the literal whole sequence.
- **Read the difference columns, not the absolutes.** As with the MFE paired-percentage swing, the thermometer signal lives in `PF_RBS_Diff`, not in any single absolute accessibility value.

## Limitations and gotchas

- **Cost scales steeply with length.** The partition function is roughly cubic in sequence length. That is why there is a 500 nt window cutoff at all and why this is the slow path.
- **Windowing changes what "full sequence" means.** For inputs longer than the cutoff, `PF_Full_*` columns are computed on an AUG-anchored window, so they are not strictly full-length for those sequences. If no AUG is found, the window falls back to the last 500 nt.
- **An ensemble energy of 0.0 means not computed.** RSAS initializes the ensemble values to 0.0 and only overwrites them when PF actually runs and succeeds. The `_InRange` check treats a 0.0 value as `N/A` rather than as a real energy, so a literal 0.0 in a PF energy column should be read as "no PF result," not "zero kcal/mol."
- **RBS accessibility depends on finding the RBS.** If the RBS is not located in the (possibly windowed) sequence, `PF_RBS_Access` and its differences come out `N/A`. The RBS used for PF accessibility is the one found at the base temperature.
- **Mean pairing probability is an average.** A moderate `MeanPaired` value can hide a structure that is firmly paired in one region and open in another. For region-specific questions, prefer the RBS accessibility columns or a motif's PF accessibility.

## Troubleshooting

- **All PF columns are missing from the output.** They are not enabled. RSAS only computes what you select in Output Columns. Enable the relevant `PF_Full_`, `PF_HP_`, or `PF_RBS_` columns and rerun.
- **PF columns are present but every value is 0.0 or N/A.** PF was requested but did not produce results. Check stderr for a `[RSAS] Warning: partition function ... failed` message; on failure RSAS leaves the initialized 0.0 values and the in-range checks report `N/A`.
- **`PF_RBS_Access` is N/A even though PF energies are filled in.** The RBS could not be located in the folded sequence, so there were no positions to average. Confirm your RBS anchor settings find a site, and remember the search runs on the windowed sequence for long inputs.
- **A PF range check reads N/A unexpectedly.** `PF_HP_Ensemble_{T}C_InRange` returns `N/A` when PF was not computed for that temperature, when the energy is 0.0, or when you have not configured min and max bounds for that temperature.
- **Runs got much slower after a settings change.** You likely enabled a PF column, or turned on a Quality Score profile whose criteria reference a PF metric (which silently enables the hairpin PF pass). Disable the PF columns or PF-dependent criteria if you do not need them.
