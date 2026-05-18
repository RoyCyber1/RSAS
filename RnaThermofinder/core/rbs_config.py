"""
RbsConfig — configurable anchor and upstream window for RBS detection.

A frozen dataclass passed explicitly through the RBS detection functions and
the multiprocessing work-item tuple. RbsConfig() with all defaults reproduces
the historical hardcoded behavior (last "AUG", 5-13 nt upstream window).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from RnaThermofinder.utils.motif_finder import iupac_to_regex

_VALID_IUPAC = set("ACGUTRYSWKMBDHVN")
_MIN_WINDOW_WIDTH = 6  # window must hold at least one 6-mer


@dataclass(frozen=True)
class RbsConfig:
    anchor_pattern: str = "AUG"        # IUPAC pattern
    anchor_match_side: str = "last"    # "first" | "last"
    min_spacing: int = 5               # nt: anchor 5' end -> near window bound
    max_spacing: int = 13              # nt: anchor 5' end -> far window bound

    @classmethod
    def from_settings(cls, block: dict) -> "RbsConfig":
        """Build from a settings dict; missing keys fall back to defaults.

        Values are coerced to their expected types because the settings block
        comes from a JSON file that may be hand-edited.
        """
        block = block or {}
        d = cls()
        return cls(
            anchor_pattern=str(block.get("anchor_pattern", d.anchor_pattern)).strip(),
            anchor_match_side=str(block.get("anchor_match_side", d.anchor_match_side)),
            min_spacing=int(block.get("min_spacing", d.min_spacing)),
            max_spacing=int(block.get("max_spacing", d.max_spacing)),
        )

    def validate(self) -> None:
        """Raise ValueError if any parameter is invalid."""
        if not self.anchor_pattern:
            raise ValueError("Anchor pattern must not be empty.")
        bad = set(self.anchor_pattern.upper()) - _VALID_IUPAC
        if bad:
            raise ValueError(
                f"Anchor pattern has invalid IUPAC letters: {sorted(bad)}"
            )
        if self.anchor_match_side not in ("first", "last"):
            raise ValueError(
                f"anchor_match_side must be 'first' or 'last', "
                f"got {self.anchor_match_side!r}."
            )
        if self.min_spacing < 0:
            raise ValueError("min_spacing must be >= 0.")
        if self.max_spacing <= self.min_spacing:
            raise ValueError("max_spacing must be greater than min_spacing.")
        if self.max_spacing - self.min_spacing < _MIN_WINDOW_WIDTH:
            raise ValueError(
                f"Window (max_spacing - min_spacing) must be >= "
                f"{_MIN_WINDOW_WIDTH} nt to hold a 6-mer."
            )


def resolve_anchor(sequence: str, cfg: RbsConfig) -> Tuple[Optional[int], Optional[int]]:
    """Find the anchor match in `sequence`.

    Returns (start_index, matched_length) for the first or last match per
    cfg.anchor_match_side, or (None, None) if the anchor pattern does not match.
    T is normalized to U before matching.
    """
    norm = sequence.upper().replace("T", "U")
    regex = iupac_to_regex(cfg.anchor_pattern)
    matches = list(re.finditer(regex, norm))
    if not matches:
        return (None, None)
    m = matches[-1] if cfg.anchor_match_side == "last" else matches[0]
    return (m.start(), m.end() - m.start())
