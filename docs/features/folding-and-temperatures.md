# Folding and temperatures

MFE folding is the core calculation in RSAS. The configurable folding temperatures are how you aim it at the biology you care about.

---

## Overview

Every RSAS analysis starts the same way: fold the sequence and read off its structure. RSAS does this with [ViennaRNA](https://www.tbi.univie.ac.at/RNA/) through the `RNA` Python module, using minimum-free-energy (MFE) folding. The MFE fold returns a single structure, the one with the lowest predicted free energy, written as a dot-bracket string with a free energy in kcal/mol.

RNA thermometers are temperature-dependent, so a single fold at one temperature does not tell you much. RSAS folds each sequence at a list of temperatures you configure, between 1 and 5 of them. The lowest temperature in that list is the base temperature, and it does double duty: it is the reference fold used for hairpin detection, and it anchors every difference column in the output. The other temperatures exist to show you what changes as the cell heats up.

The thermometer signal you are hunting for is a change across those temperatures: a region (the ribosome binding site, or a motif) that is paired when cold and opens up when warm. RSAS computes the same set of columns at each temperature, so when you add or remove a temperature, the temperature-dependent columns and quality-score criteria re-derive automatically to match.

This page covers the model settings RSAS hands to ViennaRNA, MFE folding itself, the 1-to-5 temperature list, the base-temperature concept, and how the output columns scale with the temperatures you choose.

---

## When to use it

You always fold. The only real decision is which temperatures to fold at, and that depends on the biology of the thermometer you expect.

A thermometer is defined by a transition: the structure holds at one temperature and melts at another. To see that transition you need at least two temperatures, one on each side of where you think the melt happens. Three is the common choice, and it is the RSAS default (25, 37, 42 °C), because it gives you a cold reference, body temperature, and a heat-shock point in one run.

- **Heat-shock / virulence thermometers.** These genes are off at low temperature and switch on around 37 °C or above (the classic FourU and ROSE-element leaders). Put your base temperature well below the expected melt (25 °C or lower as a cold reference) and add a temperature at or above the induction point (37 °C, 42 °C). The signal you want is the RBS paired at the base temperature and open at the high one.

- **Cold-shock thermometers.** These respond to a drop in temperature rather than a rise. The logic is the same but inverted: you want a cold point and a warm point bracketing the transition. Set a low base temperature (for example 10 or 15 °C) and a warmer comparison temperature, and read the difference columns the same way.

- **Body-temperature regulation.** If the relevant switch sits near 37 °C, bracket it tightly, for example 30, 37, 42 °C, so the difference columns resolve a transition that happens over a narrow band.

A practical rule: the base temperature should be a temperature where you expect the structure to be intact, because everything (hairpin detection, the reference structure, the diff baselines) is computed from it. The remaining temperatures are the comparison points where you expect melting.

---

## Step by step: configuring temperatures

1. Open **Settings** and go to **Analysis Settings**.
2. Click the **Folding Temperatures** tab.
3. You see one row per temperature, labelled `T1`, `T2`, `T3`, each with a numeric entry and a `°C` label. The defaults are 25, 37, and 42.
4. Edit any value by typing a new whole number into its entry box.
5. Click **+ Add Temperature** to add a row (it appears with a default of 37, which you then edit). The button disables once you reach 5 temperatures, and a counter shows `N/5 temperatures`.
6. Click the **✕** next to a row to remove it. You cannot remove the last remaining row; RSAS keeps at least one temperature. Rows renumber themselves after a removal.
7. Click **Save**. On save, RSAS validates the list (see below), sorts it ascending, merges any duplicates, and persists it.

If anything is wrong with the list, the status line turns red and reads `Invalid: enter 1-5 unique positive numbers`, and nothing is saved until you fix it.

**Reset Defaults** restores the temperature list to 25, 37, 42 (along with the other Analysis Settings tabs).

---

## Options in detail

### The temperature list (1 to 5 values)

RSAS accepts between 1 and 5 temperatures. The maximum of 5 is fixed (`MAX_TEMPS = 5` in the dialog). The list is the single source of truth for everything temperature-dependent downstream.

What the dialog enforces on save:

- **Whole numbers only.** Fractional temperatures are rejected. If you type `37.5`, the save fails. Internally each value is parsed as a float and rejected unless it equals its integer truncation.
- **Positive only.** Zero or negative values are rejected.
- **Deduplicated and sorted.** The accepted values are passed through `sorted(set(...))`, so duplicates collapse to one entry and the final list is always ascending. This is why `T1` is always the lowest temperature after a save.
- **Between 1 and 5 entries** after deduplication. An empty list, or more than 5 unique values, is rejected.

The same 1-to-5 and dedup-and-sort rules are enforced again in the settings layer (`SettingsManager.set_temperatures`), which raises `ValueError("Must provide 1-5 unique temperatures")` if a list ever reaches it out of bounds.

### The base temperature

The base temperature is not a separate setting you toggle. It is, by definition, the first (lowest) temperature in the sorted list, `temps[0]`. Because the list is always sorted ascending on save, the base temperature is always the coldest one.

It carries special meaning throughout the pipeline:

- **Hairpin detection runs on the base-temperature structure.** The terminal hairpin, the RBS-containing hairpin, and the AUG fallback are all extracted from the fold computed at the base temperature.
- **The reference structure is the base-temperature fold.** When original-MFE-at-all-temps is turned off, RSAS still always folds at the base temperature, because the rest of the pipeline needs that structure. The `Structure` output column is the base-temperature dot-bracket.
- **Difference columns subtract the base.** RBS paired-percent differences and PF accessibility differences are all measured against the base temperature (for example `RBS_Seq_Diff_42-25` is the 42 °C value minus the 25 °C base value).

In short: choose your base temperature deliberately, because it is both the structural reference and the zero point for every thermometer reading.

### The fold model settings

Every fold in RSAS, full sequence or extracted hairpin, MFE or partition function, uses the same ViennaRNA model details so that results are comparable across sequences and temperatures. These settings are applied in `fold_at_temp`, `hairpin_mfe_at_temps`, and the related functions in `HairpinAnalysis.py`:

- **`temperature`** is set per fold to the value being processed. ViennaRNA rescales its nearest-neighbor energy parameters to that temperature using the same model it uses at 37 °C.

- **`dangles = 2`.** Dangling-end treatment. This is ViennaRNA's default and the most common choice in the literature. It lets unpaired bases dangling off the ends of helices contribute stabilizing energy.

- **`noLP = 1`.** Lonely (isolated) base pairs are disallowed: a helix of length one is not permitted. Note this departs from ViennaRNA's own default of `noLP = 0`. RSAS turns it on because suppressing lonely pairs keeps the predicted structures closer to what actually forms.

- **`noGU = 0`.** G-U wobble pairs are allowed, which is the correct choice for RNA and is ViennaRNA's default.

RSAS does not ship or modify any energy parameters; the thermodynamics is entirely ViennaRNA's Turner nearest-neighbor model. The reference results were produced with **ViennaRNA 2.7.2**; pin that version if you need to reproduce folding numbers exactly, because parameters and defaults have shifted across ViennaRNA releases.

---

## What you get

For each temperature in your list, RSAS produces a fold and the columns derived from it. As you change the temperature list, the temperature-dependent columns scale with it: each `{T}` placeholder expands to one column per temperature.

The folding-related columns that scale with temperature:

| Column pattern | What it is |
|---|---|
| `Structure` | MFE dot-bracket at the base temperature (the one base-temperature structure, not repeated per temperature). |
| `Full_Structure_{T}C` | MFE dot-bracket at each non-base temperature. The base temperature's structure is the `Structure` column, so it is omitted here. |
| `Original_MFE_{T}C` | Minimum free energy of the full-length fold at each temperature, in kcal/mol. More negative means more stable. |
| `Hairpin_MFE_{T}C` | MFE of the extracted hairpin folded on its own at each temperature, in kcal/mol. |
| `Original_MFE_{T}C_InRange` / `Hairpin_MFE_{T}C_InRange` | Whether each MFE value falls inside the range you set in the Quality Score Builder. |

A concrete example of the scaling: with the default temperatures 25, 37, 42, the pattern `Original_MFE_{T}C` becomes three columns, `Original_MFE_25C`, `Original_MFE_37C`, `Original_MFE_42C`. Add a fourth temperature and you get a fourth column for free; the keys are regenerated, not hand-edited.

`Full_Structure_{T}C` is the one exception that does not produce a base-temperature variant: the base structure already lives in `Structure`, so RSAS skips `Full_Structure_25C` (when 25 is the base) to avoid duplicating it.

The temperature-difference columns scale by count, not by per-temperature expansion. With 2 or more temperatures you get the `highest minus base` difference (for example `RBS_Seq_Diff_42-25`). With 3 or more you additionally get the `second-highest minus base` difference. Those diffs are the thermometer fingerprint.

The full list, including the partition-function, RBS, and motif columns that also scale with temperature, is in [`../output-columns.md`](../output-columns.md).

---

## How it works

Folding lives in `RnaThermofinder/core/HairpinAnalysis.py`. The core helper is `fold_at_temp(seq, temp)`: it builds an `RNA.md()` model details object, sets `temperature`, `dangles = 2`, `noLP = 1`, and `noGU = 0`, builds an `RNA.fold_compound(seq, md)`, and returns `fc.mfe()`, which is the `(structure, mfe)` pair.

The per-temperature folding of an extracted hairpin runs through `hairpin_mfe_at_temps(hairpin_seq, temps=(25, 37, 42))`, which loops over the temperature list and applies the identical model settings at each one, returning a `temp -> (structure, mfe)` mapping. The same model details appear in `base_pairs_at_temps_struct` and in the partition-function path (`pf_fold_at_temp`), so the model is consistent regardless of which calculation you run.

Inside the per-sequence worker (`_analyze_single_sequence`), the temperature list arrives as `temps`, and the base temperature is read as `temps[0]`. The full-length original-sequence MFE loop is conditional: if "calculate original MFE at temps" is enabled it folds at every temperature, otherwise it folds only at the base temperature and fills the rest with placeholders. Hairpin detection always uses the base-temperature structure.

The column scaling is driven by `_generate_temp_columns(temps)` in `settings_manager.py`. This function takes the temperature list and emits the temperature-dependent column keys: it loops over `temps` to build `original_mfe_{t}`, `mfe_{t}c_hairpin`, `full_structure_{t}` (skipping the base), the per-temperature range-check keys, and the partition-function and motif keys. The difference keys are emitted by count: `rbs_seq_diff_{temps[-1]}_{t_first}` only when `len(temps) >= 2`, and `rbs_seq_diff_{temps[-2]}_{t_first}` only when `len(temps) >= 3`. When you save a new temperature list, `set_temperatures` calls `_generate_temp_columns` again and merges any newly required keys into your saved column selection, so the output schema follows the temperatures automatically. The display order is built in parallel by `_generate_column_order(temps)`.

For the energy model, the partition function, the hairpin and RBS detection that consume these folds, and the version caveats, see [`../methods.md`](../methods.md).

---

## Worked example

Suppose you are screening for heat-shock thermometers and want a cold reference, body temperature, and a heat-shock point.

1. Open **Settings -> Analysis Settings -> Folding Temperatures**.
2. Leave `T1` at `25`, `T2` at `37`, and `T3` at `42`. (These are the defaults, so a fresh install is already set up this way.)
3. Click **Save**.

Now run an analysis. For each sequence, RSAS folds the full length at 25, 37, and 42 °C, and folds the extracted hairpin at the same three temperatures. The base temperature is 25 °C, so:

- Hairpin detection uses the 25 °C structure.
- The `Structure` column holds the 25 °C dot-bracket; `Full_Structure_37C` and `Full_Structure_42C` hold the warmer ones.
- `Original_MFE_25C`, `Original_MFE_37C`, `Original_MFE_42C` give the full-length stability at each point.
- `Hairpin_MFE_25C`, `Hairpin_MFE_37C`, `Hairpin_MFE_42C` give the hairpin's stability.
- `RBS_Seq_Diff_42-25` is the headline number: RBS paired-percent at 42 °C minus at 25 °C. A large negative value (paired when cold, open when warm) is the thermometer fingerprint. `RBS_Seq_Diff_37-25` gives the intermediate.

If you later decide a single transition near 37 °C matters most, you might switch the list to `30, 37, 42`. After saving, the base temperature becomes 30 °C, the difference columns become `RBS_Seq_Diff_42-30` and `RBS_Seq_Diff_37-30`, and every `{T}C` column re-derives to the new set. You do not touch the output-column configuration by hand; it follows.

---

## Tips

- **Keep the base temperature where you expect intact structure.** It is the reference for hairpin detection and the zero point for every diff, so a base temperature in the middle of a melt produces confusing differences.
- **Two temperatures is the minimum for a signal.** A single temperature gives you stability numbers but no thermometer reading, because all the diff columns need a base and a comparison.
- **Bracket the transition you expect.** The difference columns resolve best when one temperature sits clearly below the melt and one clearly above it.
- **Add temperatures only when they earn their place.** Each one multiplies the per-temperature columns and slows the run, especially with the partition function on. Three is usually enough.
- **The defaults are a starting point, not a law.** 25/37/42 suits bacterial heat-shock leaders. Cold-shock and non-standard organisms want different brackets.
- **Use whole numbers.** The dialog rejects fractions, so plan your brackets in integer degrees.

---

## Limitations and gotchas

- **Whole-number temperatures only.** You cannot fold at 37.5 °C; the dialog rejects fractional values on save. If you need fine-grained brackets, choose nearby integers.
- **Maximum of 5 temperatures.** This is a hard cap. A finer temperature sweep is not possible through the GUI.
- **The list is always sorted ascending, and duplicates merge.** Whatever order you type rows in, the saved list comes out sorted, and the base temperature is whichever value ends up lowest. Two identical values collapse to one, so you cannot fold the same temperature twice.
- **You cannot remove the last temperature.** RSAS always keeps at least one, because folding needs a temperature.
- **Changing temperatures changes your column set.** Adding or removing a temperature regenerates the temperature-dependent column keys. New keys are merged in with their defaults; keys for temperatures you removed simply stop being emitted. This is intended, but it means two runs at different temperature lists are not column-for-column comparable.
- **`noLP = 1` departs from ViennaRNA's default.** RSAS disallows lonely pairs (ViennaRNA defaults to allowing them). If you compare RSAS folds against a plain ViennaRNA run left at defaults, structures and energies can differ for this reason.
- **Folding is only as good as the energy model.** Temperatures are fed to ViennaRNA's temperature rescaling of the Turner parameters. Modified nucleotides, unusual ions, and crowded cellular conditions are not modeled. See [`../methods.md`](../methods.md).
- **Numbers depend on the ViennaRNA version.** Reference results used ViennaRNA 2.7.2; a different release can give slightly different energies at the same temperature.

---

## Troubleshooting

**The Save button does nothing and the status line is red.** The status reads `Invalid: enter 1-5 unique positive numbers`. One of your entries is empty, fractional, zero, negative, non-numeric, or you have more than 5 unique values. Fix the offending row and save again.

**I typed 37.5 and it would not save.** Fractional temperatures are not supported. Use a whole number.

**My temperatures came back in a different order than I typed them.** Expected. The list is sorted ascending on save, so the lowest value becomes `T1` (the base temperature) regardless of input order.

**I added the same temperature twice and now there is only one row's worth.** Duplicates are merged on save. Each temperature can appear only once.

**The + Add Temperature button is greyed out.** You already have 5 temperatures, which is the maximum. Remove one before adding another.

**The ✕ button on my only temperature row does nothing.** RSAS will not let you remove the last temperature. Edit its value instead, or add another row first.

**A column I expected (like `Original_MFE_50C`) is missing.** Temperature-dependent columns only exist for temperatures in your current list. Add 50 to the Folding Temperatures tab and save, then the `50C` columns are generated.

**My RBS diff columns disappeared after I dropped to one temperature.** Difference columns need at least two temperatures (the `highest minus base` diff) or three (to also get the `second-highest minus base` diff). With a single temperature there is no base-versus-comparison to subtract, so those columns are not emitted.
