# Base composition analysis

RSAS reports AU%, GC%, and GU% for both the full-length sequence and the extracted hairpin, with optional "in range" flags so you can filter a candidate list on composition.

---

## Overview

Composition here is about which nucleotides a region is made of, not how it folds. For a sequence it answers three questions: how AU-rich is it, how GC-rich is it, and how much of it is G or U. Thymine (T) from a DNA-style input is treated as uracil (U) before anything is counted, so a DNA spelling and its RNA spelling give the same numbers.

There are two different composition flavors in RSAS, and they are not the same calculation:

- **Full-length / original-sequence composition** is a single-nucleotide frequency. It counts A, U, G, C across the whole sequence and divides by length. This is the textbook "AU content" notion.
- **Hairpin composition** is a base-pair-type breakdown. It looks only at the base pairs in the extracted hairpin's structure and asks what fraction of those pairs are A-U, G-C, or G-U. It is computed over paired positions, not over every nucleotide.

That distinction matters and is easy to miss because both sets of columns are labeled AU% / GC% / GU%. See [How it works](#how-it-works) for the exact formulas.

Why GU is called out at all: G-U is the wobble pair. It pairs, but it is weaker than a Watson-Crick G-C, so a stem carrying a lot of G-U pairs is less stable than its GC% alone would suggest. For a thermometer hairpin, that is exactly the kind of tunable, marginal stability you are hunting for, which is why GU% gets its own column instead of being folded into GC.

---

## When to use it

Use composition when you are narrowing a long candidate list before you commit to the slower, structure-level reading. Composition is cheap, it is temperature-independent, and it is a fast sanity filter:

- A thermometer leader that is extremely GC-rich is suspicious. A stem that GC-locked will not melt open in the physiological window.
- An AU-rich, GU-leaning stem is the kind of marginally stable element that can flip between paired and unpaired across a few degrees.
- If you already know the composition window your biology lives in, the in-range flags let you drop anything outside it in one pass.

Composition will not tell you a sequence is a thermometer. It tells you whether a candidate is plausible enough to be worth the structural analysis. Treat it as a pre-filter, not a verdict.

---

## Step by step

1. Enable the composition columns you want in the Output Columns dialog. The hairpin composition columns (`Hairpin_AU%`, `Hairpin_GC%`, `Hairpin_GU%`) are on by default. The full-sequence columns (`Original_AU%`, `Original_GC%`, `Original_GU%`) are off by default; turn them on if you want whole-sequence frequencies.
2. To get the full-sequence numbers actually computed, enable "calculate original composition" in the calculation settings. It is off by default because it is extra work the hairpin-focused pipeline does not need. Hairpin composition is always computed.
3. To filter on composition, set the target ranges. These live in the Quality Score Builder, not in a separate filter panel. Add an AU / GC / GU criterion with a min and a max to the active profile, and that min/max becomes the in-range window for the matching column.
4. Run the analysis. Read the composition columns directly, and read the matching `_InRange` column to see whether each value fell inside the window you set.
5. Export and sort or filter on the `_InRange` columns to drop candidates that miss your composition window.

---

## Options in detail

### The three metrics

For both the full sequence and the hairpin you get three numbers.

**Full sequence (single-nucleotide frequency, T treated as U):**

- `Original_AU%` = (A + U) / length x 100
- `Original_GC%` = (G + C) / length x 100
- `Original_GU%` = (G + U) / length x 100

All three are over the entire sequence and sum is not constrained to 100, because GU% overlaps AU% and GC% (U and G are each counted in two of the three metrics). Values are rounded to two decimals. A zero-length sequence returns 0.0 for all three.

**Hairpin (base-pair-type fraction, over paired positions only):**

- `Hairpin_AU%` = (A-U pairs + U-A pairs) / total pairs x 100
- `Hairpin_GC%` = (G-C pairs + C-G pairs) / total pairs x 100
- `Hairpin_GU%` = (G-U pairs + U-G pairs) / total pairs x 100

These are computed from the hairpin's dot-bracket structure: RSAS walks the brackets, collects every base pair, and asks what fraction of those pairs are each type. If the hairpin has no pairs, all three are 0. Because every counted pair is exactly one of AU / GC / GU, these three do sum to 100% (any non-canonical, non-GU pair is simply not counted).

### The in-range filters

Each composition metric has a companion in-range column that reports `In Range`, `Not in Range`, or `N/A`:

- Full sequence: `Original_AU%_InRange`, `Original_GC%_InRange`, `Original_GU%_InRange`
- Hairpin: `Hairpin_AU%_InRange`, `Hairpin_GC%_InRange`, `Hairpin_GU%_InRange`

The min/max bounds are not free-standing settings. They come from the criteria in the active scoring profile (the Quality Score Builder). When you add an AU / GC / GU criterion with a `min` and `max`, RSAS extracts that pair of numbers and uses them as the inclusive range: a value `v` is in range when `min <= v <= max`.

If the matching criterion is not in your profile, the in-range flag falls through to `N/A` for the hairpin. For the full sequence, a missing criterion defaults the window to 0-100, which means everything reads `In Range` (and if original composition was not computed, the flag is `N/A`).

### Defaults

The default scoring profiles ship with these composition criteria, applied to both the hairpin profile and the full-length profile (weight 1, no tolerance):

- AU%: 50 to 60
- GC%: 0 to 30
- GU%: 15 to 25

So out of the box, a hairpin with AU% between 50 and 60, GC% at or below 30, and GU% between 15 and 25 reads `In Range` on all three. These are a starting point tuned for one class of thermometer; edit them in the Quality Score Builder to match your biology.

Column defaults: hairpin composition and its in-range flags are enabled by default; full-sequence composition and its in-range flags are disabled by default.

---

## What you get

Composition columns, full sequence:

- `Original_AU%`, `Original_GC%`, `Original_GU%`
- `Original_AU%_InRange`, `Original_GC%_InRange`, `Original_GU%_InRange`

Composition columns, hairpin:

- `Hairpin_AU%`, `Hairpin_GC%`, `Hairpin_GU%`
- `Hairpin_AU%_InRange`, `Hairpin_GC%_InRange`, `Hairpin_GU%_InRange`

In the Excel export, the full-sequence columns appear on the Full Sequence tab and the hairpin columns on the Hairpin Analysis tab. For exact units and where each sits in the column order, see [../output-columns.md](../output-columns.md).

---

## How it works

Two functions do the work, and they compute different things.

The full-sequence numbers come from `calculate_composition` in `RnaThermofinder/utils/analysis_helpers.py`. It uppercases the sequence, replaces every `T` with `U`, counts A / U / G / C, and divides by length:

```
au_percent = ((a_count + u_count) / length) * 100
gc_percent = ((g_count + c_count) / length) * 100
gu_percent = ((g_count + u_count) / length) * 100
```

Results are rounded to two decimals, and a zero-length sequence short-circuits to 0.0 for all three.

The hairpin numbers come from `base_pair_percentages` in `RnaThermofinder/core/HairpinAnalysis.py`. It parses the hairpin's dot-bracket structure into a list of base pairs, tallies them into the six pair types (`AU`, `UA`, `GC`, `CG`, `GU`, `UG`), and divides each type's count by the total number of pairs. That is why a structure is required for the hairpin version and not for the full sequence: the hairpin metric is defined over the fold, the full-sequence metric over the raw sequence.

The in-range flags are computed by `base_pair_in_range`, which does an inclusive `min <= value <= max` comparison. The min/max values are pulled out of the active scoring profile by `extract_ranges_from_profile` (in `RnaThermofinder/utils/quality_scoring.py`), which maps each composition criterion to a `(min_key, max_key)` pair: hairpin composition maps to `au_min`/`au_max`, `gc_min`/`gc_max`, `gu_min`/`gu_max`, and full-sequence composition maps to `orig_au_min`/`orig_au_max` and so on.

For the broader pipeline context, see [../methods.md](../methods.md), whose Composition section covers both flavors: full-sequence nucleotide frequency and hairpin base-pair fractions.

---

## Worked example

Take a short toy sequence and compute the full-sequence numbers by hand. Use the input `GGCAUUGCT`, 9 characters.

First normalize: uppercase, and `T` becomes `U`. The sequence becomes `GGCAUUGCU`.

Count each base over the 9 positions:

- A: 1
- U: 3 (two from the original U's, one from the converted T)
- G: 3
- C: 2

Now apply the formulas:

- AU% = (A + U) / length x 100 = (1 + 3) / 9 x 100 = 4/9 x 100 = 44.44%
- GC% = (G + C) / length x 100 = (3 + 2) / 9 x 100 = 5/9 x 100 = 55.56%
- GU% = (G + U) / length x 100 = (3 + 3) / 9 x 100 = 6/9 x 100 = 66.67%

So `Original_AU%` = 44.44, `Original_GC%` = 55.56, `Original_GU%` = 66.67. Notice the three do not sum to 100: every U is counted in both AU% and GU%, and every G in both GC% and GU%, so the metrics deliberately overlap.

If your active profile carried the default GC criterion (0 to 30), this sequence's GC% of 55.56 would read `Not in Range` on `Original_GC%_InRange`.

The hairpin columns would not match this hand calculation, because they count base-pair types from the hairpin's folded structure, not nucleotide frequencies from the sequence.

---

## Tips

- If you only ever fold extracted hairpins, you can leave the full-sequence composition columns off and save the extra pass.
- Set your composition windows in the Quality Score Builder once and they drive both the quality score and the in-range flags, so the two always agree.
- GU% is the column to watch for tunability. A stem that is GC-poor but GU-rich is marginally stable by design, which is what you want in a thermometer.
- Sort your export on an `_InRange` column to push all the composition misses to one end of the file before you start reading structures.

---

## Limitations and gotchas

- **Two different definitions share the same label.** Full-sequence AU%/GC%/GU% are single-nucleotide frequencies; hairpin AU%/GC%/GU% are base-pair-type fractions over paired positions. Do not compare a `Hairpin_AU%` against an `Original_AU%` as if they measured the same thing.
- **Full-sequence composition is over the sequence, not the structure.** It does not know or care how the molecule folds. The hairpin version, by contrast, depends on the predicted structure, so it inherits any error in that fold.
- **It is temperature-independent.** Composition describes the bases present (full sequence) or the pairs in one structure (hairpin); the per-nucleotide numbers do not change with the folding temperature. If you see composition columns identical across temperatures, that is correct, not a bug.
- **The three metrics overlap and need not sum to 100 for the full sequence.** U is in both AU% and GU%, G is in both GC% and GU%. The hairpin pair-type metrics do sum to 100% across canonical and GU pairs.
- **T is silently converted to U.** A DNA-spelled input is folded into the same numbers as its RNA spelling. That is intended, but it means the columns never report a T count.
- **In-range bounds live in the scoring profile.** There is no separate composition-filter panel. If a composition criterion is absent from the active profile, its in-range flag is `N/A` (hairpin) or effectively always in range via a 0-100 default (full sequence).

---

## Troubleshooting

- **Composition columns are blank or read `N/A`.** For the full sequence, enable "calculate original composition" in the calculation settings; it is off by default, so the columns come through empty otherwise. Hairpin composition is always computed, so a blank hairpin value usually means the hairpin itself was not extracted.
- **An in-range flag reads `N/A` even though the number is present.** The matching criterion is missing from your active scoring profile. Add an AU / GC / GU criterion with a min and max in the Quality Score Builder, then re-run.
- **Everything reads `In Range` and nothing filters out.** Your full-sequence criterion is probably absent, so the window defaulted to 0-100 (which passes everything). Add an explicit criterion with the bounds you actually want.
- **The hairpin AU% does not match a by-hand nucleotide count.** Expected. The hairpin columns count base-pair types from the folded structure, not nucleotide frequencies. Use the full-sequence columns if you want a nucleotide-frequency number.
- **The numbers do not change when I change the temperature.** Also expected. Composition is temperature-independent. Look at the MFE, paired%, and partition-function columns for the temperature-dependent signal.
