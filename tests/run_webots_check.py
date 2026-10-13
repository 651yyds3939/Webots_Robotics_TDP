"""Run the Webots checks in an isolated, disposable project."""
from pathlib import Path
import os
import shutil
import signal
import subprocess
import tempfile
import argparse
import threading
import hashlib
import json
import sys
import math

parser = argparse.ArgumentParser()
parser.add_argument("--match", action="store_true", help="Run two configurable halves with all eight controllers")
parser.add_argument("--skills", action="store_true", help="Measure physical shoot/dribble/pass fixtures")
parser.add_argument("--vision", action="store_true", help="Actual camera and bundled detector probe; requires --output")
parser.add_argument("--motions", action="store_true", help="Measure locomotion and turn assets in an isolated scene")
parser.add_argument("--attack", action="store_true", help="Unopposed approach/dribble/shoot sequence; one real player")
parser.add_argument("--output", type=Path, help="Directory for actual runtime evidence")
parser.add_argument("--seed", type=int, default=27)
parser.add_argument("--half-seconds", type=float, default=60, help="Match-test half duration; default 60 is only a smoke check")
parser.add_argument("--ready-seconds", type=float, default=2, help="Match-test READY duration; course default is 45")
parser.add_argument("--stuck-seconds", type=float, default=30, help="Match-test stationary-ball timeout; course default is 120")
parser.add_argument("--reset-formation", action="store_true", help="TEST FIXTURE ONLY: place legal formations before each half, excluding cross-pitch setup walking")
parser.add_argument("--visible", action="store_true", help="Keep the automatic Webots window visible")
parser.add_argument("--timeout", type=float, help="Maximum wall-clock seconds; by default scales with match duration")
args = parser.parse_args()
if sum((args.match, args.skills, args.vision, args.motions, args.attack)) > 1:
    parser.error("Choose one verification mode")
for name in ("half_seconds", "ready_seconds", "stuck_seconds", "timeout"):
    value = getattr(args, name)
    if value is not None and (not math.isfinite(value) or value <= 0):
        parser.error(f"--{name.replace('_', '-')} must be finite and positive")
if args.reset_formation and not args.match:
    parser.error("--reset-formation requires --match")
if args.match and args.half_seconds <= args.ready_seconds+1:
    parser.error("A half must be longer than READY plus the 1-second SET")
if args.vision and not args.output:
    parser.error("--vision requires a fresh --output directory")
if args.vision and (args.output / "vision-result.json").exists():
    parser.error("Use a fresh output directory for the vision experiment")
if args.output and any(args.output.glob("*.jsonl")):
    parser.error("Use a fresh output directory to keep runs independent")

root = Path(__file__).resolve().parents[1] / "Wenao"
with tempfile.TemporaryDirectory(prefix="tdp-course-check-") as directory:
    project = Path(directory)
    (project / "worlds").mkdir()
    (project / "controllers").mkdir()
    for name in ("protos", "motions"):
        (project / name).symlink_to(root / name, target_is_directory=True)
    for source in (root / "controllers").iterdir():
        if source.is_dir():
            (project / "controllers" / source.name).symlink_to(source, target_is_directory=True)
    controller = project / "controllers/CourseCheck"
    controller.mkdir()
    fixture = "webots_attack_check.py" if args.attack else "webots_motion_check.py" if args.motions else "webots_vision_check.py" if args.vision else "webots_skill_check.py" if args.skills else "webots_match_check.py" if args.match else "webots_course_check.py"
    shutil.copyfile(Path(__file__).with_name(fixture), controller / "CourseCheck.py")
    world = project / "worlds/check.wbt"
    contents = (root / "worlds/naotdp.wbt").read_text().replace(
        'controller "Supervisor"', 'controller "CourseCheck"'
    )
    if args.vision:
        player = project / "controllers/VisionProbe"
        player.mkdir()
        shutil.copyfile(Path(__file__).with_name("webots_vision_player.py"), player / "VisionProbe.py")
        contents = contents.replace('controller "RedForwardA"', 'controller "VisionProbe"')
    if args.motions or args.attack:
        player = project / "controllers/MotionProbe"
        player.mkdir()
        shutil.copyfile(Path(__file__).with_name("webots_motion_probe.py"), player / "MotionProbe.py")
        if args.motions:
            contents = contents.replace('controller "RedForwardA"', 'controller "MotionProbe"')
        else:
            for name in ('RedGoalkeeper', 'RedDefender', 'RedForwardB', 'BlueGoalkeeper', 'BlueDefender', 'BlueForwardB', 'BlueForwardA'):
                contents = contents.replace(f'controller "{name}"', 'controller "MotionProbe"')
    world.write_text(contents)
    preferences = root / "worlds/.naotdp.wbproj"
    if preferences.exists():
        shutil.copyfile(preferences, project / "worlds/.check.wbproj")
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["TDP_MATCH_SEED"] = str(args.seed)
    test_options = {"half_seconds": args.half_seconds, "ready_seconds": args.ready_seconds,
                    "stuck_seconds": args.stuck_seconds, "reset_formation": args.reset_formation}
    if args.match:
        environment["TDP_MATCH_TEST_OPTIONS"] = json.dumps(test_options)
        print("MATCH TEST SETTINGS", json.dumps(test_options), flush=True)
        if args.half_seconds < 180:
            print("NOTE: short halves check integration; allow several minutes per half for behaviour observation.", flush=True)
    if args.output:
        args.output.resolve().mkdir(parents=True, exist_ok=True)
        environment["TDP_RUN_DIR"] = str(args.output.resolve())
    command = [shutil.which("webots") or "/usr/local/webots/webots", "--batch",
               *([] if args.visible else ["--minimize"]), "--mode=fast", "--stdout", "--stderr", str(world)]
    if args.output:
        files = sorted(p for base in (root / "controllers", root / "protos", root / "worlds")
                       for p in base.rglob("*") if p.is_file() and p.suffix in (".py", ".ini", ".proto", ".wbt"))
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        manifest = {"mode": "attack" if args.attack else "motions" if args.motions else "vision" if args.vision else "skills" if args.skills else "match_test" if args.match else "geometry",
                    "seed": args.seed, "python": sys.version, "python_executable": sys.executable,
                    "webots_executable": command[0], "source_sha256": hashes,
                    "match_test_options": test_options if args.match else None}
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    process = subprocess.Popen(command, env=environment, start_new_session=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    captured = []
    def collect():
        for line in process.stdout:
            captured.append(line)
            print(line, end="", flush=True)
    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    try:
        timeout = args.timeout or (max(240, 3*(2*args.half_seconds+2)) if args.match
                                  else 300 if args.attack else 240 if args.skills or args.vision or args.motions else 60)
        status = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        reader.join(timeout=5)
        if args.output:
            (args.output / "webots.log").write_text("".join(captured))
        raise SystemExit("Webots check exceeded its wall-clock limit")
    except KeyboardInterrupt:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        reader.join(timeout=5)
        if args.output:
            (args.output / "webots.log").write_text("".join(captured))
        raise SystemExit("Test interrupted; Webots stopped and available console output saved")
    reader.join(timeout=5)
    output = "".join(captured)
    if args.output:
        (args.output / "webots.log").write_text(output)
    marker = "ATTACK_CHECK_OK" if args.attack else "MOTION_CHECK_OK" if args.motions else "VISION_CHECK_OK" if args.vision else "SKILL_CHECK_OK" if args.skills else "MATCH_CHECK_OK" if args.match else "COURSE_CHECK_OK"
    if status != 0 or marker not in output or "Traceback" in output or "ERROR:" in output:
        raise SystemExit(f"Webots verification failed (status {status}, completion marker {marker in output})")
    raise SystemExit(0)
