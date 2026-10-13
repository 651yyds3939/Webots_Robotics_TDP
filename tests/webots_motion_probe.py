"""Joint motion measurement probe; all placement belongs to the test referee."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import Robot
from Base.SoccerController import MotionLibrary

robot = Robot()
library = MotionLibrary(robot)
receiver = robot.getDevice('receiver')
receiver.enable(int(robot.getBasicTimeStep()))
action = 'stand'
motion = library.get(action)
motion.play()
while robot.step(int(robot.getBasicTimeStep())) != -1:
    while receiver.getQueueLength():
        packet = json.loads(receiver.getString())
        receiver.nextPacket()
        if packet.get('kind') == 'motion_probe':
            motion.stop()
            action = packet['action']
            motion = library.get(action)
            motion.setLoop(action == 'walk')
            motion.play()
    if motion.isOver() and action in ('sprint', 'dribble', 'back', 'step_left', 'step_right'):
        motion.play()
