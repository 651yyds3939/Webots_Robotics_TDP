"""Actual bottom-camera / bundled-YOLO diagnostic on a stationary ball."""
import json
import math
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import Robot
from Base.SoccerController import MotionLibrary
from Utils.ProcessSupervisor import SupervisorData
from Utils.ImageServer import ImageServer
from Utils.VisionGeometry import ball_world_position

r = Robot()
step = int(r.getBasicTimeStep())
receiver = r.getDevice("receiver")
receiver.enable(step)
reader = SupervisorData(r.getName())
camera = r.getDevice("CameraBottom")
camera.enable(4*step)
yaw = r.getDevice("HeadYawS")
pitch = r.getDevice("HeadPitchS")
yaw.enable(step)
pitch.enable(step)
motions = MotionLibrary(r)
motion = motions.get("stand")
motion.play()
server = ImageServer(camera.getWidth(), camera.getHeight(), camera, r.getName(), "Bottom")
output = Path(os.environ["TDP_RUN_DIR"])
try:
    for index in range(600):
        if r.step(step) == -1:
            break
        while receiver.getQueueLength():
            reader.updateData(receiver)
        if r.getTime() < 2 or reader.world is None:
            continue
        capture = {"time": r.getTime(), "pose": reader.world["robots"][r.getName()],
                   "head_yaw": yaw.getValue(), "head_pitch": pitch.getValue()}
        if index%4 == 0:
            server.send(camera.getImage(), capture)
        detection = server.latest()
        if detection:
            estimate = ball_world_position(detection)
            reference = reader.world["ball"]["position"]
            result = {"detected": True, "confidence": detection["confidence"], "estimated_ball": estimate,
                      "reference_ball": reference, "planar_error_metres": math.dist(estimate[:2], reference[:2]),
                      "fixture_only": True, "calibration_validated": False}
            camera.saveImage(str(output / "bottom-camera.png"), 100)
            (output / "vision-result.json").write_text(json.dumps(result, indent=2))
            print("VISION_DETECTION_OK", json.dumps(result), flush=True)
            break
    else:
        (output / "vision-result.json").write_text(json.dumps({"detected": False, "fixture_only": True}))
finally:
    server.stop()
    # Keep the synchronous controller alive until the supervising test acknowledges
    # the result and terminates Webots; a player exit is not a passed integration test.
    while r.step(step) != -1:
        pass
