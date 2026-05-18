import pytest
from RnaThermofinder.core.rbs_config import RbsConfig


def test_defaults_match_current_behavior():
    cfg = RbsConfig()
    assert cfg.anchor_pattern == "AUG"
    assert cfg.anchor_match_side == "last"
    assert cfg.min_spacing == 5
    assert cfg.max_spacing == 13


def test_from_settings_partial_block_falls_back():
    cfg = RbsConfig.from_settings({"max_spacing": 14})
    assert cfg.max_spacing == 14
    assert cfg.min_spacing == 5
    assert cfg.anchor_pattern == "AUG"
    assert cfg.anchor_match_side == "last"


def test_from_settings_empty_block_is_all_defaults():
    assert RbsConfig.from_settings({}) == RbsConfig()


def test_validate_accepts_defaults():
    RbsConfig().validate()  # must not raise


def test_validate_rejects_max_le_min():
    with pytest.raises(ValueError):
        RbsConfig(min_spacing=10, max_spacing=10).validate()


def test_validate_rejects_negative_spacing():
    with pytest.raises(ValueError):
        RbsConfig(min_spacing=-1, max_spacing=8).validate()


def test_validate_rejects_window_narrower_than_six():
    # window width = max - min must be >= 6 to hold a 6-mer
    with pytest.raises(ValueError):
        RbsConfig(min_spacing=5, max_spacing=10).validate()


def test_validate_rejects_empty_anchor():
    with pytest.raises(ValueError):
        RbsConfig(anchor_pattern="").validate()


def test_validate_rejects_bad_iupac_letter():
    with pytest.raises(ValueError):
        RbsConfig(anchor_pattern="AXG").validate()


def test_validate_rejects_bad_match_side():
    with pytest.raises(ValueError):
        RbsConfig(anchor_match_side="middle").validate()


def test_from_settings_coerces_string_numbers():
    cfg = RbsConfig.from_settings({"min_spacing": "5", "max_spacing": "14"})
    assert cfg.min_spacing == 5
    assert cfg.max_spacing == 14
    assert isinstance(cfg.min_spacing, int)
    assert isinstance(cfg.max_spacing, int)
    cfg.validate()  # must not raise


def test_from_settings_none_is_all_defaults():
    assert RbsConfig.from_settings(None) == RbsConfig()


from RnaThermofinder.core.rbs_config import resolve_anchor


def test_resolve_anchor_last_match():
    # two AUGs: at index 2 and index 11
    seq = "CCAUGCCCCCCAUGCC"
    cfg = RbsConfig(anchor_match_side="last")
    pos, length = resolve_anchor(seq, cfg)
    assert pos == 11
    assert length == 3


def test_resolve_anchor_first_match():
    seq = "CCAUGCCCCCCAUGCC"
    cfg = RbsConfig(anchor_match_side="first")
    pos, length = resolve_anchor(seq, cfg)
    assert pos == 2
    assert length == 3


def test_resolve_anchor_iupac_matches_alt_start_codon():
    # DTG = [AGU]UG ; sequence has GUG, no AUG
    seq = "CCCCCGUGCCCCC"
    cfg = RbsConfig(anchor_pattern="DTG")
    pos, length = resolve_anchor(seq, cfg)
    assert pos == 5
    assert length == 3


def test_resolve_anchor_no_match_returns_none():
    cfg = RbsConfig()
    assert resolve_anchor("CCCCCCCCCC", cfg) == (None, None)


def test_resolve_anchor_handles_dna_t():
    # DNA input: T must be matched as U
    cfg = RbsConfig()
    pos, length = resolve_anchor("CCATGCC", cfg)
    assert pos == 2
    assert length == 3
