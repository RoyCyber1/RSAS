# Example data and a worked run

Sample files live here so you can see RSAS work before pointing it at your own data.

| File | What it is |
|---|---|
| `sample_dataset.fasta` | Six bacterial 5' leader sequences (sigma70, tetR, ibpA, oppF, dmsABC, ymcE/gnsA), each with a Shine-Dalgarno and a start codon. A quick set to load and run end to end. |
| `Test_Thermo_RV.fasta` | The first four of those leaders, used by the walkthrough below. |
| `Testing_structs_THERMO.fasta` | Two short RNA constructs for checking structure handling. |

Sequences are written as DNA (with T's); RSAS converts them to RNA on load.

**Quick test:** launch RSAS, drag in `Examples/sample_dataset.fasta` on the Analyze page, keep the defaults, and click Analyze. The six sequences finish in under a second and come back ranked by quality score.

The detailed walkthrough below uses `Test_Thermo_RV.fasta`.

---

## Run it

1. Launch RSAS (`python main.py`, or the pre-built app).
2. On the Analyze page, Browse to or drag in `Examples/Test_Thermo_RV.fasta`.
3. Leave the defaults (terminal hairpin detection, temperatures 25 / 37 / 42 °C).
4. Click **Analyze**. Four sequences finish in well under a second.

You'll see them ranked by quality score, best first.

---

## What you get, and how to read it

Here are the real numbers from that run (default settings).

**The ranking.** RSAS sorts by quality score:

| Sequence | RBS found | RBS paired% | Hairpin score |
|---|---|---|---|
| tetR | `UAGGAG` | 100% | 4/6 (67%) |
| oppF | `UGGAGG` | 100% | 3/6 (50%) |
| sigma70 | `GAGAGU` | 83% | 1/6 (17%) |
| ibpA | `GGAGCU` | 67% | 1/6 (17%) |

All four have a recognizable Shine-Dalgarno. tetR and oppF score higher because their hairpin's energy and composition land inside the default target ranges; sigma70 and ibpA fall outside them.

**The structure.** For tetR, the detected hairpin and its dot-bracket structure are:

```
AUCACUUAUUCUUUUGCGUUAAUAAAAUGUAGGAGAUGGGUCAUG
((.((((((.((((((((((.....)))))))))))))))).)).
```

That long stem buries the `UAGGAG` Shine-Dalgarno (paired 100% at the base temperature), which is exactly the arrangement a temperature-responsive leader uses to keep the ribosome off until conditions change.

**The temperature signal.** This is the point of the tool. By default RSAS folds the hairpin at every temperature, and you can watch its stability weaken as things heat up. For tetR:

| Temperature | Hairpin MFE |
|---|---|
| 25 °C | −16.77 kcal/mol |
| 42 °C | −10.07 kcal/mol |

The hairpin loses about 6.7 kcal/mol of stability between 25 and 42 °C. A structure that melts as it warms is the thermometer behavior you're screening for. The weaker the hairpin gets at high temperature, the more the ribosome binding site opens up.

To track the RBS opening at each temperature directly (rather than through hairpin stability), enable the per-temperature full-structure or partition-function columns in **Output Columns**. By default RSAS folds the full-length sequence only at the base temperature, so those per-temperature RBS columns read `N/A` until you turn them on.

---

## Doing the same thing from a script

The walkthrough above is also a few lines of Python, which is handy for batch work. See the "Scripting it without the GUI" section of the [usage guide](../docs/usage.md) for a complete example using `HairpinAnalysis.calculate_results_final`.
