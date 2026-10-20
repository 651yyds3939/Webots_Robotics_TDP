"""Opt-in experiment for late-phase dribble walk-to-side transitions."""


class SideTransition:
    SETTLE_SECONDS = 1.2
    PHASE_FRACTION = .75

    def __init__(self, mode='off'):
        if mode not in ('off', 'phase'):
            raise ValueError('Side transition mode must be off or phase')
        self.mode = mode
        self.started = None

    def cancel(self):
        self.started = None

    def request(self, now, action, behaviour, current_action, phase_ms, duration_ms, motion_over):
        if self.mode == 'off':
            return None
        if self.started is not None:
            if current_action != 'stand':
                self.cancel()
                return None
            if motion_over and now - self.started >= self.SETTLE_SECONDS - 1e-9:
                self.cancel()
                return 'release'
            return 'wait'
        if (behaviour == 'DRIBBLE' and current_action == 'walk'
                and action in ('step_left', 'step_right') and duration_ms > 0
                and self.PHASE_FRACTION <= phase_ms / duration_ms <= 1):
            self.started = now
            return 'begin'
        return None
