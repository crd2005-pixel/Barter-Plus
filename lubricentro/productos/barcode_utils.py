# -*- coding: utf-8 -*-

"""
Minimal Code128 Encoder for drawing barcodes with QPainter.
Supported characters: ASCII 32-126.
Uses Code Set B by default (switches to C for numbers if efficient - not implemented here for simplicity,
we stick to Set B which covers all ASCII).
"""

# Full table for encoding by value (0-105)
# Values 0-94 map to ASCII 32-126
# Value 104 is Start B
# Value 106 is Stop (but usually Stop is separate pattern)
_PATTERNS = [
    '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213', # 0-9
    '221312', '231212', '112232', '122132', '122231', '113222', '123122', '123221', '223211', '221132', # 10-19
    '221231', '213212', '223112', '312131', '311222', '321122', '321221', '312212', '322112', '322211', # 20-29
    '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313', # 30-39
    '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331', # 40-49
    '231131', '213113', '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111', # 50-59
    '314111', '221411', '431111', '111224', '111422', '121124', '121421', '141122', '141221', '112214', # 60-69
    '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111', # 70-79
    '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141', # 80-89
    '214121', '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141', # 90-99
    '114131', '311141', '411131', '211412', '211214', '211232' # 100-105 (Start A, B, C, Stop, etc)
]
# Start B is index 104 ('211214')
STOP_PATTERN = '2331112'

def get_code128_pattern(data: str) -> str:
    """
    Returns a string of digits representing bar widths (1-4) for Code128-B.
    E.g. "211214..."
    Alternates Bar-Space-Bar-Space...
    """
    if not data:
        return ""

    # Always use Set B for simplicity
    sum_val = 104
    pattern = _PATTERNS[104] # Start B

    for i, char in enumerate(data):
        val = ord(char) - 32
        if val < 0 or val > 94:
            val = 0 # Space fallback
        sum_val += (val * (i + 1))
        pattern += _PATTERNS[val]

    checksum = sum_val % 103
    pattern += _PATTERNS[checksum]
    pattern += STOP_PATTERN # Stop pattern

    return pattern
