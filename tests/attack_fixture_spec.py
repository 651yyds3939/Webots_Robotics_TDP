"""Placement and acceptance for the unopposed physical attack fixture."""
import math


def layout(name):
    if name == 'standard':
        return [.5, -.15, .334], [1.2, 0, .07], 0.
    if name == 'mirrored':
        return [.5, .15, .334], [1.2, 0, .07], 0.
    if name == 'offset':
        return [.5, -.15, .334], [1.2, .25, .07], 0.
    raise ValueError('Unknown attack layout')


def no_fall_ok(minimum_up, minimum_height, recoveries):
    return (math.isfinite(minimum_up) and math.isfinite(minimum_height)
            and minimum_up >= math.cos(.8) and minimum_height >= .20 and recoveries == 0)
