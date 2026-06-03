# Output column reference

Every column RSAS can write, what it means, and its units. You won't see all of these in one file; only the columns you enable in the Output Columns dialog get computed and exported. This is the reference for when you're staring at a header and need to know exactly what the number under it represents.

A few conventions used throughout:

- **`{T}`** stands for a configured temperature in °C. If your run uses 25, 37, and 42, then `Original_MFE_{T}C` expands to three columns: `Original_MFE_25C`, `Original_MFE_37C`, `Original_MFE_42C`.
- **base temperature** is the lowest temperature in your run. It's the reference for hairpin detection and for every difference column.
- **Paired%** always means the percentage of a region's positions that are base-paired in that temperature's MFE structure.
- Composition (AU/GC/GU) is over the *sequence*; pairing and structure columns are over the *fold*.

The columns below are listed in the order RSAS writes them.

---

## Sequence identity

| Column | Meaning |
|---|---|
| `Name` | The sequence name from your input file. |
| `Sequence` | The input RNA sequence (T converted to U). |
| `Structure` | MFE dot-bracket structure at the base temperature. |
| `Full_Structure_{T}C` | MFE dot-bracket at each non-base temperature. The base temperature's structure is the `Structure` column above, so it isn't repeated here. |

---

## Full-length energy and composition

| Column | Meaning | Units |
|---|---|---|
| `Original_MFE_{T}C` | Minimum free energy of the full-length fold at each temperature. More negative = more stable. | kcal/mol |
| `Original_AU%` | (A + U) / length × 100 for the full sequence. | % |
| `Original_GC%` | (G + C) / length × 100. | % |
| `Original_GU%` | (G + U) / length × 100. | % |

### Range checks

These flag whether the value above falls inside the range you configured. Useful for filtering.

| Column | Meaning |
|---|---|
| `Original_MFE_{T}C_InRange` | "In Range" / "Not in Range" for the full-length MFE at each temperature. |
| `Original_AU%_InRange` | Same, for full-length AU%. |
| `Original_GC%_InRange` | Same, for full-length GC%. |
| `Original_GU%_InRange` | Same, for full-length GU%. |

---

## RBS sequestering in the full-length fold

How buried the ribosome binding site is when the whole sequence folds, measured at each temperature.

| Column | Meaning | Units |
|---|---|---|
| `Full_RBS_{T}C_Seq` | The RBS subsequence as identified at each temperature. | — |
| `Full_RBS_{T}C_Struct` | The RBS region's dot-bracket at each temperature. | — |
| `Full_RBS_{T}C_Paired%` | Percentage of the RBS that is paired at each temperature. This is the core thermometer reading. | % |
| `RBS_Seq_Diff_{hi}-{base}` | Difference in RBS paired% between the highest temperature and the base temperature. A large negative value (paired when cold, open when warm) is the thermometer fingerprint. | percentage points |
| `RBS_Seq_Diff_{mid}-{base}` | Same difference for the middle temperature versus base (only when you have 3+ temperatures). | percentage points |

---

## Hairpin analysis

The extracted regulatory hairpin: how it was found, its sequence and structure, and its own energy and composition.

| Column | Meaning | Units |
|---|---|---|
| `Hairpin_Detection_Method` | Which method found this hairpin (terminal or RBS-based). | — |
| `RBS_Detection_Params` | The anchor / side / window used for RBS detection this run, e.g. `AUG/last/5-13`. Records your settings alongside the result. | — |
| `Hairpin_Sequence` | The extracted hairpin subsequence. | — |
| `Hairpin_Structure` | The hairpin's dot-bracket structure. | — |
| `Hairpin_AU%` / `Hairpin_GC%` / `Hairpin_GU%` | Base-**pair** composition of the hairpin: the fraction of its folded base pairs that are A-U, G-C, and G-U wobble. These are over pairs, not bases, so they sum to 100. (Unlike the `Original_*` columns above, which are single-nucleotide frequencies.) | % of pairs |
| `Hairpin_MFE_{T}C` | MFE of the hairpin folded on its own at each temperature. | kcal/mol |

### Hairpin range checks

| Column | Meaning |
|---|---|
| `Hairpin_MFE_{T}C_InRange` | Whether the hairpin MFE is in range, per temperature. |
| `Hairpin_AU%_InRange` / `Hairpin_GC%_InRange` / `Hairpin_GU%_InRange` | Whether hairpin composition is in range. |

---

## RBS (standalone)

The RBS as a region in its own right, separate from the full-length sequestering columns above.

| Column | Meaning | Units |
|---|---|---|
| `RBS_Sequence` | The identified Shine-Dalgarno / RBS subsequence. | — |
| `RBS_Structure` | Its dot-bracket. | — |
| `RBS_Paired%` | Percentage of the RBS that is paired. | % |
| `RBS_Paired%_InRange` | Whether RBS paired% is in your configured range. | — |

---

## Partition function

Ensemble-level numbers, only present when you enable PF (it's the slow part of a run). Unlike the MFE columns, these account for all competing structures, not just the single best one.

| Column | Meaning | Units |
|---|---|---|
| `PF_Full_Ensemble_{T}C` | Ensemble free energy of the full-length sequence at each temperature. At or below the MFE. | kcal/mol |
| `PF_Full_MeanPaired_{T}C` | Mean pairing probability across the full sequence. | probability (0–1) |
| `PF_HP_Ensemble_{T}C` | Ensemble free energy of the hairpin. | kcal/mol |
| `PF_HP_MeanPaired_{T}C` | Mean pairing probability across the hairpin. | probability (0–1) |
| `PF_RBS_Access_{T}C` | RBS accessibility: mean probability that the RBS positions are unpaired across the ensemble, as a percentage. Higher = more accessible to the ribosome. | % (0–100) |
| `PF_RBS_Diff_{hi}-{base}` | Change in RBS accessibility from base to highest temperature. The ensemble-level version of the thermometer signal. | percentage points |
| `PF_RBS_Diff_{mid}-{base}` | Same for the middle temperature (3+ temperatures only). | percentage points |
| `PF_HP_Ensemble_{T}C_InRange` | Whether the hairpin ensemble energy is in range, per temperature. | — |

---

## Motif / sequence finder

Present only when motif search is enabled. When a sequence has several matches, the multi-value fields are semicolon-separated in the CSV, and the Excel file gets a dedicated Motif Matches tab with one row per hit.

| Column | Meaning | Units |
|---|---|---|
| `Motif_Pattern` | The IUPAC pattern you searched for. | — |
| `Motif_Count` | Number of matches found in the sequence. | count |
| `Motif_Match_Seq` | The matched subsequences. | — |
| `Motif_Match_Pos` | Match positions, 0-based and half-open. | — |
| `Motif_Paired%_{T}C` | Paired percentage of each match at each temperature. | % |
| `Motif_Struct_{T}C` | Each match's dot-bracket at each temperature. | — |
| `Motif_PF_Access_{T}C` | Partition-function accessibility of each match: mean unpaired probability over the match, as a percentage (needs PF on). | % (0–100) |
| `Motif_Paired_Diff_{hi}-{base}` | Change in motif paired% from base to highest temperature. | percentage points |
| `Motif_PF_Diff_{hi}-{base}` | Change in motif PF accessibility, base to highest. | probability points |
| `Motif_Paired_Diff_{mid}-{base}` / `Motif_PF_Diff_{mid}-{base}` | Same differences for the middle temperature (3+ temperatures). | — |

---

## Quality scores

Two parallel sets: `HP_` scores the hairpin, `FL_` scores the full-length sequence. Both are driven by the profile you set in the Quality Score Builder. See [methods.md](methods.md#quality-scoring) for exactly how they're computed.

| Column | Meaning |
|---|---|
| `HP_Quality_Score` / `FL_Quality_Score` | Raw score as `passed/evaluated`, e.g. `5/6`. "Passed" means a criterion scored a full 1.0. |
| `HP_Quality_Score_Weighted` / `FL_Quality_Score_Weighted` | Weight-weighted average of the criterion scores, as a percentage (0–100). |
| `HP_Quality_Score_Class` / `FL_Quality_Score_Class` | Tier from the weighted percentage: Tier 1 (≥83%), Tier 2 (≥67%), Tier 3 (≥50%), Tier 4 (≥33%), Tier 5 (below). |
| `HP_Quality_Score_Breakdown` / `FL_Quality_Score_Breakdown` | Per-criterion scores, semicolon-separated, so you can see which criteria carried or sank the total. |

Results are sorted by quality score, best first, so your strongest candidates are already at the top of the export.
