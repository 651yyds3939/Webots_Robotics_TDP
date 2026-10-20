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
parser.add_argument('--side-transition', choices=('off', 'phase'), default='off', help='Opt-in dribble walk-to-side settling experiment; only --attack/--match with fresh --output')
parser.add_argument('--locomotion', choices=('legacy', 'guarded'), help='Execution scheduler; normal --attack defaults to guarded, other fixtures to legacy')
parser.add_argument('--finishing-aim', choices=('centre', 'nearest'), default='centre', help='Near-goal fallback aim experiment; nearest is opt-in, not validated multiplayer stability')
parser.add_argument('--require-no-fall', action='store_true', help='Attack acceptance: goal, no recovery, upright motion and stable stop after goal')
parser.add_argument('--attack-layout', choices=('standard', 'mirrored', 'offset'), default='standard', help='Unopposed fixture placement variation')
parser.add_argument('--transitions', action='store_true', help='Measure no-ball motion transitions, with diagnostics; requires fresh --output')
parser.add_argument('--transition-profile', choices=('isolated', 'replay'), default='isolated', help='Short no-ball sequences, or recorded pre-fall history with/without ball')
parser.add_argument('--transition-case', action='append', help='Run selected cases in the profile; may be repeated')
parser.add_argument('--transition-repeats', type=int, default=3, help='Per-case repeats in one world; use 1 with separate processes for fresh-world comparisons')
parser.add_argument("--output", type=Path, help="Directory for actual runtime evidence")
parser.add_argument("--seed", type=int, default=27)
parser.add_argument("--half-seconds", type=float, default=60, help="Match-test half duration; default 60 is only a smoke check")
parser.add_argument("--ready-seconds", type=float, default=2, help="Match-test READY duration; course default is 45")
parser.add_argument("--stuck-seconds", type=float, default=30, help="Match-test stationary-ball timeout; course default is 120")
parser.add_argument("--reset-formation", action="store_true", help="TEST FIXTURE ONLY: place legal formations before each half, excluding cross-pitch setup walking")
parser.add_argument("--visible", action="store_true", help="Keep the automatic Webots window visible")
parser.add_argument("--diagnostics", action="store_true", help="Record IMU, leg angles, foot forces and motion playback; requires --output")
parser.add_argument("--timeout", type=float, help="Maximum wall-clock seconds; by default scales with match duration")
args = parser.parse_args()
if args.locomotion is None:
    args.locomotion = 'guarded' if args.attack and args.side_transition == 'off' else 'legacy'
if args.attack and args.locomotion == 'guarded':
    args.require_no_fall = True
if args.attack_layout != 'standard' and not args.attack:
    parser.error('--attack-layout requires --attack')
if args.require_no_fall and (not args.attack or not args.output):
    parser.error('--require-no-fall requires --attack and a fresh --output directory')
if args.locomotion != 'legacy' and (not (args.attack or args.match) or not args.output):
    parser.error('--locomotion guarded requires --attack or --match and a fresh --output directory')
if args.finishing_aim != 'centre' and (not (args.attack or args.match) or not args.output):
    parser.error('--finishing-aim nearest requires --attack or --match and a fresh --output directory')
if args.locomotion != 'legacy' and args.side_transition != 'off':
    parser.error('Choose guarded locomotion or the rejected side-transition experiment separately')
if args.side_transition != 'off' and (not (args.attack or args.match) or not args.output):
    parser.error('--side-transition phase requires --attack or --match and a fresh --output directory')
if args.transition_profile != 'isolated' and not args.transitions:
    parser.error('--transition-profile requires --transitions')
if args.transition_case or args.transition_repeats != 3:
    if not args.transitions:
        parser.error('--transition-case and --transition-repeats require --transitions')
if args.transition_repeats <= 0:
    parser.error('--transition-repeats must be positive')
if args.transitions:
    from transition_cases import cases
    if args.transition_case and not set(args.transition_case) <= {case['name'] for case in cases(args.transition_profile)}:
        parser.error('Unknown case for the selected transition profile')
if args.transitions:
    if not args.output:
        parser.error('--transitions requires a fresh --output directory')
    args.diagnostics = True
if args.diagnostics and (not args.output or not (args.attack or args.match or args.transitions)):
    parser.error('--diagnostics requires --attack, --match or --transitions and a fresh --output directory')
if sum((args.match, args.skills, args.vision, args.motions, args.attack, args.transitions)) > 1:
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
    fixture = "webots_transition_check.py" if args.transitions else "webots_attack_check.py" if args.attack else "webots_motion_check.py" if args.motions else "webots_vision_check.py" if args.vision else "webots_skill_check.py" if args.skills else "webots_match_check.py" if args.match else "webots_course_check.py"
    shutil.copyfile(Path(__file__).with_name(fixture), controller / "CourseCheck.py")
    if args.attack:
        shutil.copyfile(Path(__file__).with_name('attack_fixture_spec.py'), controller / 'attack_fixture_spec.py')
    world = project / "worlds/check.wbt"
    contents = (root / "worlds/naotdp.wbt").read_text().replace(
        'controller "Supervisor"', 'controller "CourseCheck"'
    )
    if args.transitions:
        contents = contents.replace('DEF SUPERVISOR Robot {\n  children [',
                                    'DEF SUPERVISOR Robot {\n  children [\n    Receiver { name "transition_receiver" channel 7 }')
        player = project / 'controllers/TransitionProbe'
        player.mkdir()
        shutil.copyfile(Path(__file__).with_name('webots_transition_probe.py'), player / 'TransitionProbe.py')
        for target in (player, controller):
            shutil.copyfile(Path(__file__).with_name('transition_cases.py'), target / 'transition_cases.py')
            shutil.copyfile(Path(__file__).with_name('transition_replay.json'), target / 'transition_replay.json')
        contents = contents.replace('controller "RedForwardA"', 'controller "TransitionProbe"')
    if args.vision:
        player = project / "controllers/VisionProbe"
        player.mkdir()
        shutil.copyfile(Path(__file__).with_name("webots_vision_player.py"), player / "VisionProbe.py")
        contents = contents.replace('controller "RedForwardA"', 'controller "VisionProbe"')
    if args.motions or args.attack or args.transitions:
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
    environment['TDP_MOTION_DIAGNOSTICS'] = '1' if args.diagnostics else '0'
    environment['TDP_SIDE_TRANSITION'] = args.side_transition
    environment['TDP_LOCOMOTION'] = args.locomotion
    environment['TDP_FINISHING_AIM'] = args.finishing_aim
    environment['TDP_ATTACK_NO_FALL'] = '1' if args.require_no_fall else '0'
    environment['TDP_ATTACK_LAYOUT'] = args.attack_layout
    if args.transitions:
        environment['TDP_TRANSITION_PROFILE'] = args.transition_profile
        environment['TDP_TRANSITION_REPEATS'] = str(args.transition_repeats)
        if args.transition_case:
            environment['TDP_TRANSITION_CASES'] = json.dumps(args.transition_case)
        else:
            environment.pop('TDP_TRANSITION_CASES', None)
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
        fixture_files = [Path(__file__), Path(__file__).with_name(fixture)]
        if args.attack:
            fixture_files.append(Path(__file__).with_name('attack_fixture_spec.py'))
        if args.transitions:
            fixture_files += [Path(__file__).with_name(name) for name in ('transition_cases.py', 'transition_replay.json', 'webots_transition_probe.py', 'webots_motion_probe.py')]
        manifest = {"mode": "transitions" if args.transitions else "attack" if args.attack else "motions" if args.motions else "vision" if args.vision else "skills" if args.skills else "match_test" if args.match else "geometry",
                    "seed": args.seed, "python": sys.version, "python_executable": sys.executable,
                    "webots_executable": command[0], "source_sha256": hashes,
                    "motion_diagnostics": args.diagnostics,
                    'side_transition_mode': args.side_transition,
                    'locomotion_mode': args.locomotion,
                    'finishing_aim': args.finishing_aim,
                    'require_no_fall': args.require_no_fall,
                    'attack_layout': args.attack_layout if args.attack else None,
                    'transition_profile': args.transition_profile if args.transitions else None,
                    'transition_case': args.transition_case if args.transitions else None,
                    'transition_repeats': args.transition_repeats if args.transitions else None,
                    'fixture_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture_files},
                    'motion_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / 'motions').glob('*.motion'))},
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
                                  else 600 if args.transitions else 300 if args.attack else 240 if args.skills or args.vision or args.motions else 60)
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
    marker = "TRANSITION_CHECK_OK" if args.transitions else "ATTACK_CHECK_OK" if args.attack else "MOTION_CHECK_OK" if args.motions else "VISION_CHECK_OK" if args.vision else "SKILL_CHECK_OK" if args.skills else "MATCH_CHECK_OK" if args.match else "COURSE_CHECK_OK"
    if status != 0 or marker not in output or "Traceback" in output or "ERROR:" in output or 'controller crashed' in output:
        raise SystemExit(f"Webots verification failed (status {status}, completion marker {marker in output})")
    raise SystemExit(0)
