"""Execute fixture schedules only; no tactical decisions or automatic recovery."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import Robot
from Base.SoccerController import MotionLibrary
from Utils.MotionDiagnostics import MotionDiagnostics
from transition_cases import active_segment
import os

robot = Robot()
step = int(robot.getBasicTimeStep())
receiver = robot.getDevice('receiver')
receiver.enable(step)
# NaoV6's ordinary emitter/receiver share a PROTO channel field. Use the
# independent emitter so changing the acknowledgement channel cannot be saved
# into the command receiver's channel during a fixture state reset.
emitter = robot.getDevice('super_emitter')
emitter.setChannel(7)
imu = robot.getDevice('inertial unit')
imu.enable(step)
library = MotionLibrary(robot)
owner = SimpleNamespace(current=library.get('stand'), current_action='stand',
                        current_behaviour='TRANSITION_FIXTURE', navigation_stage='',
                        observation=SimpleNamespace(world=None), name=robot.getName())
owner.current.play()
logger = MotionDiagnostics(robot, library.devices, imu, Path(os.environ['TDP_RUN_DIR']), step)
plan = None
frame, index = 0, None


def acknowledge(state):
    emitter.send(json.dumps({'kind': 'transition_status', 'state': state,
                            'case': plan['case'], 'repeat': plan['repeat'],
                            'time': robot.getTime()}).encode())


def change(item, reason):
    logger.snapshot(owner, 'motion_transition_before', requested_action=item['action'],
                    case=plan['case'], repeat=plan['repeat'], reason=reason)
    owner.current.stop()
    owner.current = library.get(item['action'])
    owner.current_action = item['action']
    owner.current.setLoop(item['action'] == 'walk')
    if 'phase_ms' in item:
        owner.current.setTime(item['phase_ms'])
    owner.current.play()
    logger.snapshot(owner, 'motion_transition_after', case=plan['case'], repeat=plan['repeat'],
                    reason=reason, motion_preparation=library.audit[item['action']])


try:
    while robot.step(step) != -1:
        logger.ready = True
        while receiver.getQueueLength():
            packet = json.loads(receiver.getString())
            receiver.nextPacket()
            if packet.get('kind') == 'transition_plan':
                plan = packet
                frame, index = 0, None
                acknowledge('started')
            elif packet.get('version') == 2:
                owner.observation.world = packet
        if plan:
            upcoming = active_segment(plan['segments'], frame)
            if upcoming is None:
                logger.snapshot(owner, 'transition_fixture_complete', case=plan['case'], repeat=plan['repeat'])
                acknowledge('completed')
                plan = None
            else:
                item = plan['segments'][upcoming]
                if upcoming != index:
                    owner.navigation_stage = ''
                    if item['action'] == 'hold':
                        owner.current.stop()
                        owner.navigation_stage = 'HOLD_LAST_TARGET'
                    else:
                        change(item, 'scheduled')
                    index = upcoming
                elif item.get('repeat') and owner.current.isOver():
                    change(item, 'repeat_completed_motion')
                logger.snapshot(owner, case=plan['case'], repeat=plan['repeat'])
                frame += 1
finally:
    logger.close()
    library.directory.cleanup()
