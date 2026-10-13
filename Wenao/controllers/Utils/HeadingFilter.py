"""Circular smoothing of torso sway, preserving the +/-pi wrap boundary."""
import math


class HeadingFilter:
    def __init__(self, time_constant=.20):
        self.time_constant = time_constant
        self.angle = None
        self.time = None

    def update(self, angle, now):
        if self.angle is None:
            self.angle = angle
        else:
            elapsed = max(0, now-self.time)
            weight = 1-math.exp(-elapsed/self.time_constant)
            difference = (angle-self.angle+math.pi) % (2*math.pi)-math.pi
            self.angle = (self.angle+weight*difference+math.pi) % (2*math.pi)-math.pi
        self.time = now
        return self.angle


def turn_threshold(travelling, walking):
    # Hysteresis: torso sway must not interrupt walking every 40 ms.
    return (25 if walking else 18) if travelling else 12
