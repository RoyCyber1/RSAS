"""A full-length scoring criterion on an original-composition or per-temperature
MFE metric must trigger that calculation; otherwise the metric stays a
placeholder 0 and is scored as a failed criterion.
"""
import pytest

from RnaThermofinder.core.HairpinAnalysis import needs_original_calcs_for_profile


def _profile(*metrics):
    return {"criteria": [{"metric": m, "min": 0, "max": 1, "weight": 1} for m in metrics]}


def test_none_profile_needs_nothing():
    assert needs_original_calcs_for_profile(None) == (False, False)


def test_empty_profile_needs_nothing():
    assert needs_original_calcs_for_profile({"criteria": []}) == (False, False)


@pytest.mark.parametrize("metric", ["original_au_percent",
                                    "original_gc_percent",
                                    "original_gu_percent"])
def test_composition_metric_enables_composition_only(metric):
    assert needs_original_calcs_for_profile(_profile(metric)) == (True, False)


@pytest.mark.parametrize("metric", ["original_mfe_25", "original_mfe_37", "original_mfe_42"])
def test_original_mfe_metric_enables_mfe_temps_only(metric):
    assert needs_original_calcs_for_profile(_profile(metric)) == (False, True)


def test_both_kinds_enable_both():
    assert needs_original_calcs_for_profile(
        _profile("original_au_percent", "original_mfe_25")) == (True, True)


def test_hairpin_metric_does_not_enable_original_calcs():
    # hairpin MFE / composition are computed unconditionally; must NOT trip these
    assert needs_original_calcs_for_profile(
        _profile("mfe_37c_hairpin", "hairpin_au_percent")) == (False, False)


def test_pf_metric_handled_separately_not_here():
    assert needs_original_calcs_for_profile(
        _profile("pf_full_ensemble_37")) == (False, False)
