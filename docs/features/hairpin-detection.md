# Hairpin detection

How RSAS finds the regulatory stem-loop in a leader sequence, using either the rightmost hairpin (terminal) or the hairpin that buries the ribosome binding site (RBS-based), with an AUG fallback for fourU-type thermometers.

## Overview

An RNA thermometer works by folding one regulatory hairpin over its own ribosome binding site at low temperature, then melting that hairpin open as the cell warms up. To analyze a thermometer, RSAS first has to decide which hairpin in the predicted structure is the regulatory one. That is what hairpin detection does.

After RSAS folds the full-length sequence at the base (lowest) temperature, it picks out a single stem-loop and hands it to the rest of the pipeline. Everything downstream (the hairpin MFE at each temperature, the hairpin composition, the hairpin quality score) operates on that extracted piece, not on the whole sequence. So the choice of hairpin determines what most of the hairpin columns mean.

RSAS gives you two ways to pick the hairpin. The default, terminal detection, takes the rightmost stem-loop. The alternative, RBS-based detection, finds the RBS first and then extracts the stem-loop that encloses it. The right choice depends on where the regulatory hairpin sits in your leader.

## When to use it

**Terminal hairpin (default).** Picks the rightmost (3'-most) stem-loop in the full structure, plus any trailing unpaired bases. Use it when the regulatory element is at the 3' end of the leader, feeding into a downstream start codon. That is the common arrangement for 5' UTR thermometers, and terminal detection is simple and correct most of the time.

Where it fails: when the regulatory hairpin is not the last one in the structure. In nested or multi-branch folds, a more 5' hairpin can be the one doing the regulating, and terminal detection will hand you the wrong stem-loop.

**RBS-based hairpin.** Finds the hairpin that actually sequesters the Shine-Dalgarno sequence. It locates the RBS first, confirms the RBS is paired (sequestered), then walks outward to the smallest enclosing stem-loop. Use it when the regulatory hairpin is not the terminal one, or when you specifically want the structure built around the RBS.

Where it fails: it depends on the RBS being found and being paired. If no G-rich RBS is detected in the configured window, it falls back to anchoring on the start codon (the AUG fallback, below). If neither the RBS nor the anchor codon is sequestered, RBS-based detection reports no hairpin found, and that sequence is dropped from the output (the analysis returns nothing for it).

## Step by step

1. Open the **Settings** page.
2. Open **Analysis Settings**.
3. Go to the **Hairpin Detection** tab.
4. Choose one of two radio buttons:
   - **Terminal Hairpin (original method)** finds the rightmost stem-loop in the full structure. This is the original RSAS algorithm and the default.
   - **RBS-Containing Hairpin (new method)** finds the hairpin that sequesters the RBS, falls back to an AUG-containing hairpin for fourU-type thermometers, and cuts a window around the RBS if the hairpin exceeds 80 nt. Typical thermometer hairpin: 20 to 80 nt.
5. Save.

The RBS-based method depends on the RBS search settings. Those live on the separate **RBS Window** tab of the same Analysis Settings dialog (anchor pattern, match side, and the upstream spacing window). Tuning them changes which RBS and therefore which hairpin RBS-based detection extracts.

`Reset Defaults` on this dialog sets the method back to terminal.

## Options in detail

### Detection method

| Name | What it does | Default | Effect |
|---|---|---|---|
| Terminal Hairpin | Extracts the rightmost stem-loop in the MFE structure plus trailing unpaired bases. | Selected (default) | Right when the regulatory hairpin is at the 3' end; wrong for nested or non-terminal hairpins. |
| RBS-Containing Hairpin | Finds the RBS, confirms it is sequestered, extracts the enclosing stem-loop. Falls back to AUG anchoring; window-cuts large structures. | Not selected | Targets the hairpin around the RBS; can return "no hairpin" and drop a sequence if nothing is sequestered. |

Internally the stored value is `terminal` or `rbs_based`. RBS-based detection routes through `find_thermometer_hairpin`, which tries `find_rbs_containing_hairpin` first and falls back to `find_aug_containing_hairpin`.

### RBS sequestering threshold (RBS-based method)

Not a GUI control. RBS-based detection only treats the RBS as sequestered when at least **3 of the 6** RBS nucleotides are base-paired in the full-length structure. If fewer than 3 are paired, the RBS is judged accessible (probably not a thermometer) and the method reports no hairpin. This is fixed in code (`find_rbs_containing_hairpin`).

### AUG fallback (RBS-based method)

Not a GUI control. When no G-rich RBS is found in the upstream window, RBS-based detection falls back to anchoring on the start codon directly (`find_aug_containing_hairpin`). This catches fourU-type thermometers, where a run of U bases pairs directly with the AUG to block ribosome binding and there is no clean separate Shine-Dalgarno.

- The anchor defaults to the last `AUG`, but it follows whatever you set on the RBS Window tab (anchor pattern, match side).
- The anchor is treated as sequestered when at least `ceil(2/3 x L)` of its `L` positions are paired (`_anchor_pairing_threshold`). For a 3-nt AUG that is 2 of 3. For anchors shorter than 3 nt it becomes a 100% requirement; those are degenerate and not expected in practice.
- If the anchor is not sequestered, the method reports no hairpin for that sequence.

### Window-cut for large structures (RBS-based method)

Not a GUI control. After the enclosing stem-loop is extracted, if it comes out **larger than 80 nt** (or could not be found at all), RBS-based detection switches to a window-cut heuristic (`_cut_window_as_hairpin`): it cuts roughly an **80-nt window** centered on the target (RBS or AUG), biased upstream (about 52 nt upstream, 28 nt downstream of the target), trims leading and trailing unpaired bases, and uses that slice as the hairpin. The cut slice is not refolded here; the downstream pipeline folds it. If the cut window comes out shorter than 8 nt it is rejected, and the method falls back to the oversized full-structure hairpin if one exists, otherwise reports no hairpin. When the cut is used, the detection method recorded is `rbs_hairpin_cut` or `aug_hairpin_cut`.

### Gap crossing during stem-loop extraction (both RBS and AUG methods)

Not a GUI control. When walking outward from the sequestered region to the enclosing stem-loop (`_extract_stemloop_around_positions`), RSAS only counts pairs whose partner is within `max_local_distance` (50 nt) as "local", and it crosses unpaired gaps (bulges and internal loops) up to `max_gap` (20 nt) wide on each side. This lets the extracted hairpin include bulged, elongated stems that belong to the same structure while stopping at multi-branch junctions and large single-stranded regions.

### Composition and MFE filter ranges

These are **not** on the Hairpin Detection tab. The tab itself carries a note: "MFE/composition ranges are now configured in the Terminal Hairpin Quality Score Builder." Hairpin AU/GC/GU and per-temperature MFE ranges are applied later, as quality-score criteria and range checks, not as part of hairpin detection. (The usage guide's claim that this tab holds those ranges does not match the current dialog code.)

## What you get

Hairpin detection feeds the hairpin columns in the output. The ones most directly produced by detection:

| Column | What it holds |
|---|---|
| `Hairpin_Detection_Method` | Which method found this hairpin: `terminal`, `rbs_hairpin`, `rbs_hairpin_cut`, `aug_hairpin`, or `aug_hairpin_cut`. |
| `Hairpin_Sequence` | The extracted hairpin subsequence. |
| `Hairpin_Structure` | The hairpin's dot-bracket structure. |
| `RBS_Detection_Params` | The anchor / side / window used this run, e.g. `AUG/last/5-13`. |

The extracted hairpin then drives `Hairpin_MFE_{T}C`, `Hairpin_AU%` / `Hairpin_GC%` / `Hairpin_GU%`, the hairpin partition-function columns, the `RBS_*` columns, and the `HP_` quality scores. For the full column list and units, see [../output-columns.md](../output-columns.md).

Note that the detection method string is the raw internal label (`rbs_hairpin_cut` and so on), so an RBS-based run can show different labels per sequence depending on which path was taken.

## How it works

Hairpin detection runs on the structure folded at the base (lowest) temperature.

**Terminal path.** `get_terminal_hairpin_with_tail` finds the rightmost `)` in the structure, walks backward to its matching `(`, and includes any trailing unpaired dots after the close. The slice between those positions is the hairpin. The result is then trimmed of trailing unpaired bases (`trim_trailing_unpaired`) before folding.

**RBS-based path.** `find_thermometer_hairpin` is the entry point. It calls `find_rbs_containing_hairpin` first:

1. Find the RBS via `find_rbs_in_hairpin` (the same anchor-and-upstream-window scan described in [../methods.md](../methods.md), looking for the first 6-mer with at least 3 G's upstream of the anchor).
2. Build a position-to-partner map of the structure (`_build_pair_map`) and count how many of the 6 RBS nucleotides are paired.
3. If fewer than 3 are paired, the RBS is accessible: report no hairpin.
4. If at least 3 are paired, extract the enclosing stem-loop with `_extract_stemloop_around_positions` (local pairs only, crossing small bulges and internal loops).
5. If that stem-loop is missing or larger than 80 nt, fall back to the window-cut (`_cut_window_as_hairpin`).
6. Trim leading and trailing unpaired bases.

If `find_rbs_containing_hairpin` returns nothing found, `find_thermometer_hairpin` falls back to `find_aug_containing_hairpin`, which does the same dance but anchored on the start codon and using the `_anchor_pairing_threshold` (ceil(2/3 x L)) test instead of the fixed 3-of-6 RBS test.

When the extracted hairpin has no structure attached (the window-cut path leaves it unfolded), the pipeline folds the hairpin on its own at the base temperature before continuing. For the full thermodynamic treatment (folding model, energy parameters, the RBS search rule), see [../methods.md](../methods.md).

## Worked example

Suppose a 5' UTR leader folds at 25 C into a structure with one nested regulatory hairpin in the middle and a second, larger terminal hairpin at the 3' end.

With **terminal detection**, RSAS takes the rightmost stem-loop, the large 3' hairpin. If the regulatory element is actually the nested middle hairpin, the `Hairpin_*` columns now describe the wrong structure, even though they are computed correctly.

Switch to **RBS-based detection**. RSAS scans 5 to 13 nt upstream of the last AUG, finds a G-rich 6-mer (say `AGGAGG`), and checks its pairing in the 25 C structure. Four of its six bases are paired, above the 3-of-6 threshold, so the RBS is sequestered. RSAS walks outward from those paired positions, crosses a 4-nt bulge (within the 20-nt gap limit), and lands on the enclosing stem-loop, the nested middle hairpin. That stem-loop is 48 nt, under the 80-nt cap, so no window-cut is needed. The result:

- `Hairpin_Detection_Method` = `rbs_hairpin`
- `Hairpin_Sequence` / `Hairpin_Structure` = the 48-nt middle stem-loop
- `RBS_Detection_Params` = `AUG/last/5-13`

Now the hairpin columns describe the structure that actually regulates the ribosome binding site.

If instead this had been a fourU-type leader with no G-rich Shine-Dalgarno, the RBS scan would find nothing, RBS-based detection would fall back to `find_aug_containing_hairpin`, check whether at least 2 of the 3 AUG bases are paired, and on success report `Hairpin_Detection_Method` = `aug_hairpin`.

## Tips

- Start with terminal detection. It is the default, it is fast, and for typical 3'-end thermometer leaders it is correct.
- Switch to RBS-based when you suspect the regulatory hairpin is nested or not the last one in the structure, or when the terminal hairpin obviously does not cover the RBS.
- The RBS-based method is only as good as the RBS search. If it is dropping sequences or extracting the wrong hairpin, tune the **RBS Window** tab (anchor pattern, match side, spacing) before giving up on the method.
- For non-standard start codons, set the anchor pattern to an IUPAC code like `DTG` to match AUG, GUG, and UUG. The AUG fallback then anchors on whichever start codon it finds.
- Watch `Hairpin_Detection_Method` in the output. A run set to RBS-based that shows `rbs_hairpin_cut` or `aug_hairpin_cut` tells you the window-cut heuristic kicked in, which means the clean stem-loop extraction did not apply for that sequence.

## Limitations and gotchas

- **RBS-based detection can silently drop a sequence.** If the RBS is not found or not sequestered (and the AUG fallback also fails), the analysis returns nothing for that sequence and it is absent from the output. Terminal detection only drops a sequence when there is no paired region at all.
- **The 80-nt cap and window-cut are heuristics.** A genuinely large regulatory hairpin gets cut down to an ~80-nt window centered (upstream-biased) on the RBS or AUG. The cut is by position, not by structure, so the boundaries are approximate.
- **Stem-loop extraction stops at junctions.** Gaps wider than 20 nt or branches larger than 20 nt are treated as multi-branch siblings and end the outward walk. A regulatory hairpin separated from the RBS by a large loop may not be captured whole.
- **Detection uses the base-temperature structure only.** The hairpin is chosen from the single MFE structure at the lowest configured temperature. A different base temperature can yield a different hairpin.
- **The detection-method label is the raw internal string.** Expect `rbs_hairpin`, `rbs_hairpin_cut`, `aug_hairpin`, `aug_hairpin_cut`, or `terminal`, not a polished display name.
- **Composition and MFE ranges are not set here.** Despite an older note in the usage guide, the Hairpin Detection tab does not configure filter ranges; those live in the Quality Score Builder.

## Troubleshooting

**A sequence disappeared from the output under RBS-based detection.** The RBS was not found or not sequestered and the AUG fallback also failed, so the sequence was dropped. Check the leader actually has a G-rich RBS in the configured upstream window, or loosen the RBS Window settings. Terminal detection will keep the sequence as long as it has any paired region.

**The extracted hairpin looks too big or oddly placed.** Check `Hairpin_Detection_Method`. A `*_cut` label means the window-cut ran because the stem-loop exceeded 80 nt; the hairpin is an ~80-nt slice around the target, not a clean stem-loop. If you wanted the terminal hairpin, switch methods.

**Terminal detection grabbed the wrong hairpin.** Your regulatory hairpin is probably not the 3'-most one. Switch to RBS-based detection so RSAS anchors on the RBS instead of position.

**RBS-based detection picks a hairpin around the wrong RBS.** The anchor or window is matching the wrong start codon. On the RBS Window tab, set the anchor match side (first vs last) or narrow the spacing window so the search lands on the intended RBS.

**Everything reports `terminal` even though you chose RBS-based.** Confirm the setting saved (re-open Analysis Settings). If you used "Apply to this run only" on the RBS tab, that affects only the RBS config, not the detection method; the method itself is saved with Save.
