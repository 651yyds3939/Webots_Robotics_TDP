"""Pinhole projection for the hybrid bottom-camera experiment (metres).

Robot pose is externally supplied, not inferred by this function. Upright torso
and negligible camera roll are assumptions, not a calibrated NAO6 model.
"""
import math


def ball_world_position(detection):
    capture = detection["capture"]
    # Optical ray expressed in NAO forward/left/up axes.
    depth = detection["depth"]
    left = -math.tan(detection["bearing"])*depth
    up = -math.tan(detection["elevation_down"])*depth
    pitch = .692901+capture["head_pitch"]
    forward = math.cos(pitch)*depth+math.sin(pitch)*up+.05071
    yaw = capture["pose"]["yaw"]+capture["head_yaw"]
    position = capture["pose"]["position"]
    return [position[0]+math.cos(yaw)*forward-math.sin(yaw)*left,
            position[1]+math.sin(yaw)*forward+math.cos(yaw)*left, .07]
