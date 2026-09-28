"""Logical normal-scan relay mask, independent of the hardware relay byte."""

from enum import IntFlag
from numbers import Integral


class ScanRelayMask(IntFlag):
    K1 = 1
    K2 = 2
    K3 = 4
    K4 = 8
    ALL = K1 | K2 | K3 | K4


def validate_scan_relay_mask(mask):
    if isinstance(mask, bool) or not isinstance(mask, Integral) or not 1 <= mask <= 15:
        raise ValueError("Scan relay mask must be an integer in [1, 15] (bit0=K1 .. bit3=K4)")
    return int(mask)
