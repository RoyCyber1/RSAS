"""When the RBS motif occurs more than once in the window, a substring search
lands on the first copy and measures accessibility at the wrong site. Passing
the start-codon-anchored position must measure the real RBS instead.
"""
from RnaThermofinder.core.HairpinAnalysis import calc_rbs_pf_accessibility


def _pf(unpaired):
    return {"unpaired_probs": unpaired}


def test_anchored_position_scores_the_intended_site():
    rbs = "GGAGGU"
    #        0123456789...                      real RBS here (pos 20)
    seq = "GGAGGU" + "A" * 14 + "GGAGGU" + "A" * 10  # decoy at 0, real at 20
    assert seq.index(rbs) == 0 and seq.index(rbs, 1) == 20
    # decoy fully paired (0.0), real RBS fully unpaired (1.0)
    unpaired = [0.0] * len(seq)
    for i in range(20, 26):
        unpaired[i] = 1.0
    pf = _pf(unpaired)

    anchored = calc_rbs_pf_accessibility(seq, rbs, pf, rbs_start=20)
    assert anchored["rbs_pf_accessibility_pct"] == 100.0  # scored the real site

    # the un-anchored fallback lands on the decoy and reports the WRONG value
    unanchored = calc_rbs_pf_accessibility(seq, rbs, pf)
    assert unanchored["rbs_pf_accessibility_pct"] == 0.0
    assert anchored["rbs_pf_accessibility_pct"] != unanchored["rbs_pf_accessibility_pct"]


def test_explicit_position_used_verbatim():
    rbs = "AUGGGA"
    seq = "CCCC" + rbs + "CCCC"
    unpaired = [0.2] * len(seq)
    for i in range(4, 10):
        unpaired[i] = 0.8
    res = calc_rbs_pf_accessibility(seq, rbs, _pf(unpaired), rbs_start=4)
    assert round(res["rbs_pf_accessibility_pct"], 1) == 80.0


def test_none_inputs_return_none():
    assert calc_rbs_pf_accessibility("", "GGAGG", _pf([1.0]))["rbs_pf_accessibility_pct"] is None
    assert calc_rbs_pf_accessibility("ACGU", "GGAGG", None)["rbs_pf_accessibility_pct"] is None


def test_missing_substring_falls_back_to_none():
    # rbs not present and no explicit position -> find() fails -> None
    res = calc_rbs_pf_accessibility("ACGUACGU", "GGGGGG", _pf([1.0] * 8))
    assert res["rbs_pf_accessibility_pct"] is None
