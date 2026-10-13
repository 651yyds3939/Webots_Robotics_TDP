import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.CourseSpecs import TIME_STEP

s = SupervisorBase()
try:
    node = s.robots["RedForwardA"]
    node.getField("translation").setSFVec3f([0, 0, .334])
    node.getField("rotation").setSFRotation([0, 0, 1, 0])
    node.resetPhysics()
    s.setBallPosition([.65, 0, .07])
    for _ in range(650):
        s.step(TIME_STEP)
        s.sendSupervisorData()
        result_path = s.log_directory / "vision-result.json"
        if result_path.exists():
            result = json.loads(result_path.read_text())
            assert result["detected"], result
            print("VISION_CHECK_OK: actual camera and bundled detector; fixture accuracy recorded", flush=True)
            s.step(TIME_STEP)
            s.simulationQuit(0)
            break
    else:
        raise RuntimeError("Actual camera did not produce a ball detection in this fixture")
except Exception:
    import traceback
    traceback.print_exc()
    s.simulationQuit(1)
