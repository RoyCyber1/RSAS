from RnaThermofinder.core.HairpinAnalysis import find_rbs_in_hairpin
from RnaThermofinder.core.rbs_config import RbsConfig

# Index map of S:  0..2 "AAA" | 3..8 "GGAGGA" | 9..13 "AAAAA" | 14..16 "AUG" | 17..19 "AAA"
S = "AAAGGAGGAAAAAAAUGAAA"


def test_default_config_reproduces_5_13_window():
    r = find_rbs_in_hairpin(S)
    assert r["aug_index"] == 14
    # window = S[14-13 : 14-5] = S[1:9]
    assert r["rbs_region"] == "AAGGAGGA"
    assert r["found_rbs"] is True


def test_explicit_default_config_matches_no_config():
    assert find_rbs_in_hairpin(S) == find_rbs_in_hairpin(S, RbsConfig())


def test_wider_window_changes_region():
    cfg = RbsConfig(min_spacing=5, max_spacing=15)
    r = find_rbs_in_hairpin(S, cfg)
    # window = S[max(0,14-15) : 14-5] = S[0:9]
    assert r["rbs_region"] == "AAAGGAGGA"


def test_no_anchor_match_returns_not_found():
    cfg = RbsConfig()
    r = find_rbs_in_hairpin("CCCCCCCCCCCCCCCCCCCC", cfg)
    assert r["found_rbs"] is False
    assert r["aug_index"] is None


def test_iupac_anchor_finds_gug_start():
    # GUG start codon at index 15; no AUG present
    seq = "AAAGGAGGAAAAAAAGUGAAA"
    cfg = RbsConfig(anchor_pattern="DTG")
    r = find_rbs_in_hairpin(seq, cfg)
    assert r["aug_index"] == 15
    assert r["found_rbs"] is True
