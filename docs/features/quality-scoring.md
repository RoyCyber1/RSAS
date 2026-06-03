# Quality scoring and the Quality Score Builder

Quality scoring collapses the many numbers RSAS computes for each candidate into one weighted percentage and a tier label you can sort on, using criteria and ranges you control in the Quality Score Builder.

## Overview

A single RSAS run produces a wall of numbers per sequence: MFE at every folding temperature, AU/GC/GU composition, partition-function ensemble energies, RBS sequestration. Useful, but you cannot eyeball a thousand rows and pick winners.

Quality scoring turns that pile into one sortable value. You define a profile: a list of criteria, each with a metric, a target range, an importance weight, and an optional grace zone. RSAS checks each candidate's value against every criterion, scores it from 0 to 1, takes a weighted average, and turns the result into a percentage and a tier label (Tier 1 down to Tier 5). Results come out sorted best-first, so your strongest candidates are already at the top of the export.

There are two parallel score sets. The `HP_` set scores the terminal hairpin, the `FL_` set scores the full-length sequence. Each has its own profile and its own metric registry, so you can demand different things of the hairpin than of the whole construct.

## When to use it

Use the default profile when you are screening for the kind of bacterial-leader thermometer RSAS was tuned for. The defaults are a sensible starting point: they ask for a moderately stable hairpin and plausible composition, with every criterion weighted equally.

Customize a profile when your biology differs from that default, for example:

- Your thermometers run at different temperatures, so the MFE window or the composition targets should move.
- One signal matters more than the others (say, hairpin stability), so it should carry more weight.
- You want partial credit for near-misses instead of a hard pass/fail cliff, so you add a grace zone.
- You want to score partition-function ensemble energies or RBS sequestration, which are not in the default profile.

You do not have to pick one profile forever. Build several named profiles (strict screen, loose screen, PF-focused) and switch the active one between runs.

## Step by step

Everything happens in the Quality Score Builder dialog. It opens in one of two modes, hairpin or full-length, depending on which one you launch, and each mode shows only the metrics that apply to it.

1. **Pick or create a profile.** The Profile dropdown at the top lists every saved profile. Use **New** for a blank profile, **Duplicate** to copy the current one as a starting point, or **Delete** to remove one. The built-in default profile cannot be deleted.
2. **Add and edit criteria.** Each criterion is one row under Scoring Criteria. Set the metric from the dropdown, type a **Min** and **Max** for the target range, drag the **Wt** slider (1 to 5) for importance, and set **Grace** (the tolerance zone) if you want partial credit for near-misses. Use **+ Add Criterion** to add a row; the remove button (the X) drops one. Each metric can appear only once per profile, so Add Criterion stops once every metric is in use.
3. **Watch the formula preview.** Below the criteria, a live formula line shows exactly how the weighted score is built, for example `Score = (HP_MFE25 + 2xHP_AU + ...) / total_weight x 100%`, plus a list of any grace zones. It updates as you edit.
4. **Set the classification tiers.** Under Classification Tiers, each row is a label, a minimum percentage, and a description. A candidate is classified into the highest tier whose minimum percentage it meets. Use **+ Add Tier**, the remove button, or **Reset to Defaults** to restore the standard five tiers.
5. **Save.** Click **Save Profile**. RSAS validates the profile first (see below) and refuses to save if something is off. Switching profiles with unsaved edits prompts you to save first.

The next analysis run uses the active profile to fill in the `HP_` (or `FL_`) score columns.

## Options in detail

### Criteria

Each criterion has five settings.

**Metric.** What to score. The dropdown is mode-specific. The hairpin registry exposes per-temperature hairpin MFE (`HP_MFE25`, `HP_MFE37`, ...), hairpin AU/GC/GU percent, per-temperature PF ensemble energy (`HP_PF25`, ...), and RBS sequestered percent. The full-length registry exposes the same shape against the full sequence: per-temperature full-length MFE (`FL_MFE25`, ...), full-length AU/GC/GU percent, and per-temperature PF ensemble (`FL_PF25`, ...). The temperature-dependent metrics are generated from your configured folding temperatures, so a five-temperature run shows five MFE metrics, not three.

**Min and Max.** The target range. A value inside `[Min, Max]` scores a full 1.0. Validation requires Min to be strictly less than Max.

**Weight (Wt).** Importance, an integer 1 to 5, set with the slider. A weight-3 criterion pulls three times as hard on the weighted average as a weight-1 criterion. In the scoring math, weight is floored at 1, so a missing or zero weight still counts as 1.

**Grace (tolerance).** How far outside the range a value can stray and still earn partial credit. With `Grace = 0` (the default) the criterion is strict pass/fail: in range scores 1.0, out of range scores 0. With `Grace = 2`, a value up to 2 units outside the range scores linearly from 1.0 at the range edge down to 0 at the edge of the grace band. This softens the cliff so a value one unit out of range does not score the same as one wildly out. Grace must be 0 or greater.

The defaults, generated for your configured temperatures, are: one MFE criterion per temperature with range −17 to −2 kcal/mol, plus AU 50 to 60%, GC 0 to 30%, and GU 15 to 25%. Every default weight is 1 and every default grace is 0. With the standard three temperatures that is six criteria; with five temperatures it is eight. The hairpin and full-length defaults use the same ranges against their respective metrics.

PF ensemble metrics are marked with an orange **PF** flag in their row. They only score if the partition function was computed for that run; otherwise RSAS skips them (see Limitations).

### Tiers

Tiers turn the weighted percentage into a label. Each tier is a label, a minimum percentage, and a description. A candidate is assigned the highest tier whose minimum percentage it reaches, so tiers are checked from the top down.

The default five tiers are:

| Label | Min % | Description |
|---|---|---|
| Tier 1 | 83 | Best candidates |
| Tier 2 | 67 | Good candidates |
| Tier 3 | 50 | Moderate |
| Tier 4 | 33 | Weak |
| Tier 5 | 0 | Poor |

These thresholds map onto the legacy 0-to-6 scoring system: 6/6 = 100%, 5/6 is about 83%, 4/6 about 67%, 3/6 = 50%, 2/6 about 33%. So a Tier 1 today is a 5-of-6-or-better candidate. You can rename tiers, change thresholds, add tiers, or remove them; Reset to Defaults restores the five above.

### Profiles

A profile bundles a set of criteria and a set of tiers under a name. Profiles are saved per mode (hairpin profiles and full-length profiles are separate lists), and one profile in each list is the active one used at scoring time.

- **New** creates an empty profile (no criteria, default tiers). You then add criteria.
- **Duplicate** deep-copies the current profile under a new name, a fast way to make a variant.
- **Delete** removes a profile. The built-in default profile is protected and cannot be deleted.

Profile names must be unique within the mode. On save, RSAS validates the whole profile: every metric must be known, every Min must be less than its Max, every weight must be 1 to 5, and every grace must be 0 or greater. A failing profile is rejected with a message naming the offending criterion.

## What you get

Scoring writes four columns per mode, an `HP_` set for the hairpin and an `FL_` set for the full-length sequence:

- `HP_Quality_Score` / `FL_Quality_Score`, the raw score as `passed/evaluated`, for example `5/6`. "Passed" means a criterion scored a full 1.0.
- `HP_Quality_Score_Weighted` / `FL_Quality_Score_Weighted`, the weight-weighted average of the criterion scores, as a percentage from 0 to 100, rounded to one decimal.
- `HP_Quality_Score_Class` / `FL_Quality_Score_Class`, the tier label derived from the weighted percentage.
- `HP_Quality_Score_Breakdown` / `FL_Quality_Score_Breakdown`, a semicolon-separated list of each criterion's score, so you can see which criteria carried or sank the total. Unavailable criteria appear as `N/A` here.

Results are sorted by quality score, best first. For the full column reference, see [../output-columns.md](../output-columns.md#quality-scores).

## How it works

The math is small and worth knowing.

**Per-criterion score.** For one criterion with range `[min, max]` and grace `tol`, RSAS scores the candidate's value `v`:

- If the value is missing (None, blank, or `N/A`), the score is undefined (treated specially below).
- If `min <= v <= max`, the score is `1.0`.
- Otherwise, if `tol > 0` and `v` is within `tol` of the nearer edge, the score is the linear falloff `1.0 - (dist / tol)`, where `dist` is how far `v` sits past the edge. At the edge `dist = 0` gives 1.0; at the far end of the grace band `dist = tol` gives 0.
- Otherwise the score is `0.0`.

**Aggregation.** RSAS walks every criterion, skipping any PF metric when the partition function was not run. For each remaining criterion it accumulates `score x weight` into a weighted sum and `weight` into a weight total. A criterion that scores a full 1.0 increments the "passed" count; every criterion that was looked at increments the "evaluated" count.

A criterion whose data is missing still counts: it is recorded as `N/A` in the breakdown, contributes 0 to the weighted sum, and still adds its weight to the denominator. That is the key behavior that stops a partial run from inflating its own score by quietly leaving criteria out.

The weighted percentage is `(weighted_sum / weight_total) x 100`. The raw score is `passed/evaluated`. The tier label comes from classifying that percentage against the profile's tiers, highest tier first.

This matches the account in [../methods.md](../methods.md#quality-scoring).

## Worked example

Take the default three-temperature hairpin profile: six criteria, all weight 1, all grace 0. MFE at 25/37/42 °C each target −17 to −2; AU 50 to 60%; GC 0 to 30%; GU 15 to 25%.

Suppose a candidate gives:

| Criterion | Value | In range? | Score |
|---|---|---|---|
| HP MFE 25 °C | −12.0 | yes (−17..−2) | 1.0 |
| HP MFE 37 °C | −9.0 | yes | 1.0 |
| HP MFE 42 °C | −1.0 | no (above −2) | 0.0 |
| HP AU% | 55 | yes (50..60) | 1.0 |
| HP GC% | 20 | yes (0..30) | 1.0 |
| HP GU% | 30 | no (above 25) | 0.0 |

Four criteria score 1.0, two score 0.0. With all weights equal to 1:

- Weighted sum = 4 x 1 = 4. Weight total = 6.
- Raw score = `4/6`.
- Weighted percentage = (4 / 6) x 100 = 66.7%.
- Tier: 66.7% is below the Tier 2 threshold of 67%, so this lands in Tier 3 (≥50%).

Now add a grace of 1.0 to the GU criterion. GU = 30 is 5 units past the max of 25, well outside a grace band of 1, so it still scores 0 and nothing changes. But if GU had been 25.5, with grace 1.0 it would score `1.0 - (0.5 / 1.0) = 0.5`. The weighted sum becomes 4.5, the percentage becomes 75%, and the candidate moves up to Tier 2. The raw `passed/evaluated` stays `4/6`, because a 0.5 is not a full pass.

## Tips

- Use the formula preview as your sanity check. If the denominator or a weight multiplier is not what you expected, fix it before saving.
- Reach for grace instead of widening the range when you want to rank near-misses below clean passes rather than treating them as equal. A wide range scores everything inside it 1.0; a grace zone gives a sliding score.
- Duplicate the default before experimenting. It keeps a known-good baseline you can return to.
- Lean on the breakdown column to debug surprising tiers. It tells you exactly which criterion dragged a candidate down.
- Build separate strict and loose profiles and switch between them rather than constantly re-editing one profile.
- Weight reflects importance, not difficulty. Give your most decisive signal the higher weight.

## Limitations and gotchas

- **A high score means "matches your criteria," not "confirmed thermometer."** The score is a ranking aid for prioritizing experiments. It does not validate that a sequence behaves as a thermometer; that takes the bench.
- **Missing data counts as 0 in the denominator.** If a criterion's value is `N/A`, it scores 0 but still adds its weight to the total. This is deliberate, so a partial run cannot inflate its score by dropping criteria, but it means a candidate missing several values will look worse than one that was fully evaluated. Read the breakdown to tell a real low score from a data-coverage gap.
- **PF metrics need the partition function enabled.** Any criterion on a PF ensemble metric (the orange PF rows) is silently skipped if the partition function was not computed for that run. It does not count against the score, but it also contributes nothing, so a PF-heavy profile run without PF may score on very few criteria.
- **The score is only as good as your ranges.** Defaults are tuned for one kind of thermometer. If your biology differs, the numbers are meaningful only after you set ranges that match it.
- **Hairpin and full-length are independent.** A great `HP_` score and a poor `FL_` score (or the reverse) are both possible and both informative; do not assume one stands in for the other.

## Troubleshooting

- **Save is rejected with a validation error.** The message names the criterion. Common causes: Min is not less than Max, a weight outside 1 to 5, or a negative grace. Fix that criterion and save again.
- **A PF criterion never seems to count.** The partition function was not run for that analysis. Enable PF output before the run, or remove the PF criterion from the profile.
- **A candidate is in a lower tier than expected.** Open the breakdown column. An `N/A` entry means missing data scored 0; a low decimal means a near-miss inside a grace zone. The breakdown shows which criterion is responsible.
- **The weighted percentage looks too high for the number passed.** Grace zones produce partial scores between 0 and 1 that lift the weighted average without counting as passes, so `passed/evaluated` and the percentage can diverge. That is expected.
- **Switching profiles asks about unsaved changes.** You edited the current profile without saving. Save if you want to keep the edits, or discard to load the new profile clean.
- **A profile cannot be deleted.** It is the built-in default for that mode, which is protected. Duplicate it and edit the copy instead.
