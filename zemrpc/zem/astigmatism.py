"""Stigmator A/B (image X/Y) values exchanged with the instrument.

Raw values are signed DAC codes written to AstigBiasA/B; the instrument's
configured Min/Max bias limits are not reported over the protocol. Percent
values are relative to MaxAstigBiasA/B on both signs.
"""

import math
from numbers import Integral, Real

AST_RAW_LIMIT = 65535
STIG_PCT_LIMIT = 100.0


def validate_ast_raw(value):
    if isinstance(value, bool) or not isinstance(value, Integral) or not -AST_RAW_LIMIT <= value <= AST_RAW_LIMIT:
        raise ValueError(f"Stigmator DAC value must be an integer in [-{AST_RAW_LIMIT}, {AST_RAW_LIMIT}]")
    return int(value)


def validate_stig_pct(value):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not -STIG_PCT_LIMIT <= value <= STIG_PCT_LIMIT:
        raise ValueError("Stigmator percentage must be a finite number in [-100, 100]")
    return float(value)
