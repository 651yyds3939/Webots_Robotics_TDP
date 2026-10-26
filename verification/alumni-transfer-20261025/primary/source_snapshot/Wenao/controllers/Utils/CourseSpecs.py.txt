"""Development profile dimensions in metres; pitch lines lie inside its boundary.

Source: local geometry profile; see IMPLEMENTATION_NOTES.md.
The supplied approximate 14 cm ball diameter is used consistently.
"""

PITCH_LENGTH = 9.0
PITCH_WIDTH = 6.0
GOAL_WIDTH = 2.6  # clear distance between the inner faces of the posts
GOAL_HEIGHT = 1.2  # ground to underside of crossbar
GOAL_DEPTH = 0.6
GOAL_AREA_LENGTH = 1.0
GOAL_AREA_WIDTH = 3.0
PENALTY_AREA_LENGTH = 2.0
PENALTY_AREA_WIDTH = 5.0
PENALTY_MARK_DISTANCE = 1.5
CENTRE_CIRCLE_DIAMETER = 1.5
BORDER_WIDTH = 1.0
LINE_WIDTH = 0.05  # modelling choice, not specified in the course dimension table
BALL_DIAMETER = 0.14
BALL_RADIUS = BALL_DIAMETER / 2
TIME_STEP = 40
GRID_RESOLUTION = 0.1


def goal_crossing(previous, current):
    """Return the scoring team for a whole-ball crossing of a goal line.

    Linear interpolation checks the aperture at the crossing, rather than at
    a later sample. It is a geometric scorer, not a complete football referee.
    """
    if previous is None:
        return None
    for direction, team in ((1, "RED"), (-1, "BLUE")):
        threshold = PITCH_LENGTH / 2 + BALL_RADIUS
        before, after = direction * previous[0], direction * current[0]
        if before <= threshold < after:
            fraction = (threshold - before) / (after - before)
            y = previous[1] + fraction * (current[1] - previous[1])
            z = previous[2] + fraction * (current[2] - previous[2])
            if (abs(y) + BALL_RADIUS < GOAL_WIDTH / 2
                    and z + BALL_RADIUS < GOAL_HEIGHT
                    and z >= BALL_RADIUS - 0.005):
                return team
    return None
