"""The CSV header and data rows are built from two separate ordered key lists
(_generate_column_order and _build_column_map), both filtered by the same
enabled-column set. If their key orders diverge, columns shift under the wrong
header. These tests keep the four ordered lists in sync.
"""
import pytest

from settings_manager import _generate_column_order
from RnaThermofinder.utils.analysis_helpers import _build_column_map
from RnaThermofinder.core.HairpinAnalysis import (
    _build_fallback_data_keys,
    _build_fallback_headers,
)

TEMP_SETS = [[37], [25, 37, 42], [25, 30, 37, 42, 50]]


def _header_keys(temps):
    return [key for key, _display in _generate_column_order(temps)]


def _row_keys(temps):
    return [setting_key for setting_key, _data_key in _build_column_map(temps)]


@pytest.mark.parametrize("temps", TEMP_SETS)
def test_header_and_row_key_order_identical(temps):
    """get_enabled_columns order must equal build_csv_row order, key-for-key."""
    header = _header_keys(temps)
    row = _row_keys(temps)
    assert header == row, (
        f"CSV header/row key order diverged for temps={temps}. "
        f"in header not row: {set(header) - set(row)}; "
        f"in row not header: {set(row) - set(header)}"
    )


@pytest.mark.parametrize("temps", TEMP_SETS)
def test_fallback_keys_match_column_map(temps):
    """No-settings fallback row keys must match the build_csv_row order."""
    assert _build_fallback_data_keys(temps) == _row_keys(temps)


@pytest.mark.parametrize("temps", TEMP_SETS)
def test_fallback_headers_align_with_keys(temps):
    """Fallback header count must equal fallback data-key count (1:1 columns)."""
    assert len(_build_fallback_headers(temps)) == len(_build_fallback_data_keys(temps))


@pytest.mark.parametrize("temps", TEMP_SETS)
def test_column_map_data_keys_match_setting_keys(temps):
    """In _build_column_map every (setting_key, data_key) pair is consistent
    (no typo that would read the wrong result_data field)."""
    for setting_key, data_key in _build_column_map(temps):
        assert setting_key == data_key, (
            f"setting_key/data_key mismatch: {setting_key!r} != {data_key!r}"
        )
