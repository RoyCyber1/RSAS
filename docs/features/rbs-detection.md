# RBS Detection

RSAS finds the ribosome binding site (RBS / Shine-Dalgarno) by anchoring on a start codon and scanning a configurable upstream window for a G-rich 6-mer, then measures how paired that site is at each temperature.

## Overview

The ribosome binding site is the short sequence, just upstream of a start codon, that the ribosome recognizes to begin translation. In bacteria this is the Shine-Dalgarno sequence, a purine-rich stretch (canonically something like `AGGAGG`) that base-pairs with the 3' end of the 16S rRNA. If that site is buried inside a hairpin stem, the ribosome cannot reach it and translation is blocked.

That sequestering is the thermometer signal RSAS is built to find. An RNA thermometer keeps its RBS paired (sequestered) at low temperature and melts the stem open as the cell heats up, freeing the RBS for the ribosome. So the question RSAS asks at every temperature is: how much of the RBS is paired right now? A site that is paired when cold and unpaired when warm is the fingerprint of thermometer-like regulation. Everything downstream, the paired percentage, the temperature-difference columns, the partition-function accessibility, exists to quantify that one behavior.

To measure it, RSAS first has to locate the RBS. That is what this feature does.

## When to use it

RBS detection runs as part of every analysis; you do not turn it on. With all defaults, RSAS reproduces the historical hardcoded behavior exactly: it anchors on the **last** literal `AUG` in the sequence and scans the window **5 to 13 nt upstream** of it for a G-rich 6-mer. For the bacterial 5' leaders RSAS is built for, those defaults are usually right, and leaving the RBS Window tab untouched keeps your results comparable across versions.

Change the anchor or window when the defaults do not fit your system:

- **Alternative start codons.** Bacteria use `GUG` and `UUG` as start codons in addition to `AUG`. The anchor pattern is IUPAC-aware, so setting it to `DTG` matches all three start codons at once (`D` is `A`/`G`/`U`, giving AUG, GUG, UUG). Use `GUG` or `UUG` alone if you want only that one.
- **A different organism or leader layout.** If the Shine-Dalgarno in your system sits closer to or further from the start codon than the default 5 to 13 nt, widen or shift the spacing window so the scan covers the right region.
- **Picking a different anchor occurrence.** If the relevant start codon is the first one in the sequence rather than the last, switch the match side to first.

If your defaults already work, you do not need to open this tab at all.

## Step by step

The RBS search is configured in the **RBS Window** tab of **Analysis Settings**.

1. Open **Analysis Settings** from the Analyze page.
2. Click the **RBS Window** tab. It is labeled "RBS Anchor & Window" and explains that the RBS is found by scanning a window upstream of an anchor codon, with defaults anchor `AUG`, 5 to 13 nt.
3. Set the four controls: **Anchor (IUPAC)**, **Match side**, **Min spacing (nt)**, and **Max spacing (nt)**.
4. If you only want these settings for the current run, tick **Apply to this run only (don't save as default)**.
5. Click **Save**. Invalid entries (empty pattern, bad IUPAC letters, non-integer spacing, or a window too narrow to hold a 6-mer) are flagged inline in red and the dialog stays open until they are fixed.

**Reset Defaults** in the dialog restores anchor `AUG`, match side `last`, min spacing `5`, max spacing `13`, and unchecks the run-only box.

## Options in detail

### Anchor (IUPAC)

What RSAS anchors the RBS search on. This is an IUPAC nucleotide pattern, so `AUG` is a literal match while degenerate codes expand to character classes (`R` = `[AG]`, `Y` = `[CU]`, `D` = `[AGU]`, `N` = `[ACGU]`, and so on). `T` is treated as `U`, so you can type `DTG` and it matches RNA. The anchor is matched against the sequence to find where the upstream window sits.

- **Default:** `AUG`.
- **Effect:** Determines which codon RSAS treats as the translation start, which in turn fixes where the upstream window is placed. Setting it to `DTG` lets RSAS find leaders that use GUG or UUG start codons, not just AUG.

### Match side

Which occurrence of the anchor pattern to use when the pattern matches more than once.

- **Last (3'-most):** use the rightmost match.
- **First (5'-most):** use the leftmost match.
- **Default:** `last`.
- **Effect:** In a leader with several in-frame or out-of-frame `AUG`s, this picks which one defines the window. The historical behavior is the last match, on the assumption that the true start codon is near the 3' end of the leader.

### Min spacing (nt)

The near edge of the upstream search window, measured in nucleotides from the anchor.

- **Default:** `5`.
- **Effect:** Positions where the scanned region stops, just upstream of the anchor. The window runs from `min_spacing` to `max_spacing` nt upstream, so a larger min spacing pushes the window further from the start codon.

### Max spacing (nt)

The far edge of the upstream search window.

- **Default:** `13`.
- **Effect:** Positions where the scanned region begins, further upstream of the anchor. With the defaults, RSAS scans the classic 5-to-13-nt-upstream region. The window (`max_spacing` minus `min_spacing`) must be at least 6 nt wide so it can hold a 6-mer; the dialog rejects narrower windows.

### Apply to this run only (don't save as default)

A checkbox to try settings for a single run without overwriting your saved default.

- **Default:** unchecked.
- **Effect:** When checked, RSAS uses the entered RBS config for the next run but does not persist it; your saved default in `~/.rsas/csv_output_settings.json` is untouched. When unchecked, Save writes the config as the new default.

When an override is live, the **Analyze screen shows a banner** so you do not forget it is on. The banner reads, for example:

```
RBS window override active: DTG / last / 5-13
```

A **Clear RBS override** button appears next to the banner; clicking it drops back to your saved default. Saving a new default (with the box unchecked) also clears any active override. The override does not survive an app restart.

## What you get

RBS detection feeds several output columns. The sequestering reading is the point of the feature; the rest record context and the settings used.

| Column | Meaning |
| --- | --- |
| `RBS_Sequence` | The identified Shine-Dalgarno / RBS 6-mer, or `Not Found`. |
| `RBS_Structure` | The RBS region's dot-bracket, or `N/A`. |
| `RBS_Paired%` | Percentage of the RBS that is paired. |
| `RBS_Paired%_InRange` | Whether RBS paired% falls in your configured range. |
| `Full_RBS_{T}C_Seq` / `_Struct` / `_Paired%` | The RBS sequence, structure, and paired percentage in the full-length fold at each temperature. The paired% across temperatures is the core thermometer reading. |
| `RBS_Seq_Diff_{hi}-{base}` (and `{mid}-{base}`) | Difference in RBS paired% between temperatures. A large negative value (paired when cold, open when warm) is the thermometer fingerprint. |
| `RBS_Detection_Params` | The anchor / side / window used for this run, formatted `anchor/side/min-max`, e.g. `AUG/last/5-13`. Records your settings alongside the result. |

The partition-function side adds `PF_RBS_Access_{T}C` and `PF_RBS_Diff_*`, the ensemble-level version of the same signal.

For the full column reference, see [../output-columns.md](../output-columns.md).

## How it works

RBS detection lives in `RnaThermofinder/core/HairpinAnalysis.py`, driven by the config in `RnaThermofinder/core/rbs_config.py`. The window and anchor are carried in an `RbsConfig` dataclass (`anchor_pattern`, `anchor_match_side`, `min_spacing`, `max_spacing`); `RbsConfig()` with all defaults reproduces the historical "last AUG, 5-13 nt upstream" behavior.

The core search is `find_rbs_in_hairpin`:

1. **Resolve the anchor.** `resolve_anchor` normalizes `T` to `U`, converts the IUPAC anchor pattern to a regex, and finds every match. It returns the last match when `anchor_match_side` is `last`, otherwise the first match. If the anchor pattern does not match anywhere, no RBS is reported.
2. **Define the window.** From the anchor start position, RSAS takes the region from `max_spacing` to `min_spacing` nucleotides upstream (`search_start = anchor_pos - max_spacing`, `search_end = anchor_pos - min_spacing`, both clamped at 0). That slice is the region scanned.
3. **Find the first G-rich 6-mer.** RSAS slides a 6-nt window across the region and takes the **first** 6-mer that contains **at least 3 G's** (`window.count("G") >= 3`) as the RBS. The "3 or more G" rule is a deliberately loose Shine-Dalgarno detector: it catches canonical `AGGAGG`-style sites and weaker variants without demanding an exact consensus.

Once the RBS sequence is located, its structure is sliced out of the hairpin's dot-bracket and `calc_rbs_paired_percent` counts paired positions (`(` or `)`) over the RBS length, times 100, to give the paired percentage. The full-length variant, `find_rbs_in_full_sequence`, runs the same search against the full sequence and folds, and the RBS-based hairpin detector uses the same resolved anchor and RBS to walk outward to the enclosing stem-loop.

For the broader pipeline context, see [../methods.md](../methods.md).

## Worked example

Suppose a leader ends with a Shine-Dalgarno just upstream of the start codon:

```
...CAUUAGGAGGUAUAACUAUG...
              ^^^^^^      ^^^
              RBS         AUG anchor
```

With the defaults (anchor `AUG`, side `last`, window 5 to 13):

1. `resolve_anchor` finds the last `AUG` and returns its start position.
2. RSAS slices the region from 13 nt upstream of that `AUG` down to 5 nt upstream.
3. Sliding a 6-nt window across that slice, the first 6-mer with 3 or more G's is `AGGAGG` (4 G's), so that becomes the RBS.
4. In the cold fold, those 6 positions sit inside a stem and read as paired, so `RBS_Paired%` is high (toward 100). In the warm fold the stem melts, the positions go unpaired, and `RBS_Paired%` drops. The negative `RBS_Seq_Diff_{hi}-{base}` is the thermometer signal.

`RBS_Detection_Params` for this run records `AUG/last/5-13`.

## Tips

- Use `DTG` as the anchor when your organism uses GUG or UUG starts; it covers all three start codons in one pattern without separate runs.
- Use **Apply to this run only** to A/B different windows quickly. The banner keeps you honest about which settings produced a given output, and `RBS_Detection_Params` is written into every row so the parameters travel with the results.
- If the relevant start codon is near the 5' end of your leader rather than the 3' end, switch **Match side** to first rather than fighting a window that lands on the wrong `AUG`.
- The thermometer signal is the *change* in `Full_RBS_{T}C_Paired%` across temperatures, not any single value. Watch the `RBS_Seq_Diff` columns for a large negative swing.

## Limitations and gotchas

- **The RBS detector is a heuristic, not a validated predictor.** The "first 6-mer with 3 or more G's" rule plus the default upstream window are sensible for bacterial leaders, but they are not an organism-general, experimentally validated RBS finder. Always sanity-check that the anchor and window fit your system.
- **It takes the first qualifying 6-mer, not the best one.** Within the window, RSAS stops at the first 6-mer reaching the 3-G threshold; it does not score candidates or prefer a stronger Shine-Dalgarno further along.
- **No anchor means no RBS.** If the anchor pattern does not match anywhere in the sequence, RSAS reports no RBS (`Not Found`). For fourU-type thermometers where the RBS overlaps the start codon and there is no clean separate Shine-Dalgarno, the RBS-based hairpin detector falls back to anchoring on the start codon directly.
- **The window must be wide enough.** `max_spacing - min_spacing` must be at least 6 nt to hold a 6-mer; the settings dialog rejects narrower windows.
- **Overrides are not persistent.** An "Apply to this run only" override clears on app restart, when you save a new default, or when you click Clear RBS override.

## Troubleshooting

- **`RBS_Sequence` is `Not Found`.** Either the anchor pattern did not match the sequence, or no 6-mer in the window reached 3 G's. Check that your anchor (for example `AUG` vs `DTG`) actually appears, and consider widening the spacing window so the scan covers the real Shine-Dalgarno region.
- **RSAS anchored on the wrong codon.** With several `AUG`s in the leader, the default last-match may pick an internal codon. Switch **Match side** to first, or narrow the anchor pattern to something more specific to the true start.
- **The dialog will not save.** RBS settings are validated on Save. An empty anchor, invalid IUPAC letters, non-integer spacing, a max spacing not greater than min, or a window narrower than 6 nt are each flagged in red; fix the flagged field and Save again.
- **You forgot which settings produced a run.** Read `RBS_Detection_Params` in the output (formatted `anchor/side/min-max`), and watch the Analyze-screen banner, which shows any active per-run override.
- **An override is stuck on.** Click **Clear RBS override** next to the banner to return to your saved default, or restart the app.
