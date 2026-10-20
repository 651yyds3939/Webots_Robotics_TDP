"""Stop, observe and move using motion phase and measured standing stability."""
import math


class GuardedLocomotion:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.stop_requested = False
        self.stable_since = None
        self.previous = None
        self.angular_rate = None
        self.ready_reported = False

    def reset(self):
        self.stop_requested = False
        self.stable_since = None
        self.ready_reported = False

    def observe(self, now, roll, pitch):
        self.angular_rate = None
        if self.previous and now > self.previous[0]:
            self.angular_rate = max(abs(roll-self.previous[1]), abs(pitch-self.previous[2])) / (now-self.previous[0])
        self.previous = (now, roll, pitch)

    def before_decision(self, now, action, over, phase_ms, duration_ms, roll, pitch, foot_z):
        self.observe(now, roll, pitch)
        if action == 'stand':
            stable = (over and max(abs(roll), abs(pitch)) < .12
                      and self.angular_rate is not None and self.angular_rate < .35
                      and len(foot_z) == 2 and all(math.isfinite(f) and f > 5 for f in foot_z))
            if not stable:
                self.stable_since = None
                return 'wait'
            if self.stable_since is None:
                self.stable_since = now
            return 'ready' if now-self.stable_since >= .16-1e-9 else 'wait'
        self.stable_since = None
        self.ready_reported = False
        if action == 'walk':
            if not self.stop_requested:
                return 'ready'
            if phase_ms >= duration_ms:
                self.stop_requested = False
                return 'settle'
            return 'wait'
        return 'settle' if over else 'wait'
