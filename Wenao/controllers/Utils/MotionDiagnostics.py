"""Optional measurements; never issue motor commands or choose actions."""
import json
import math
import os


LEG_JOINTS = tuple(side + joint for side in ('L', 'R') for joint in
                   ('HipYawPitch', 'HipRoll', 'HipPitch', 'KneePitch', 'AnklePitch', 'AnkleRoll'))


def finite(value):
    if isinstance(value, dict):
        return {key: finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class MotionDiagnostics:
    def __init__(self, robot, devices, imu, directory, time_step):
        self.robot, self.imu = robot, imu
        self.joints = {name: (devices[name], devices[name + 'S']) for name in LEG_JOINTS
                       if name in devices and name + 'S' in devices}
        self.feet = {name: devices[name] for name in ('LFsr', 'RFsr') if name in devices}
        for _, sensor in self.joints.values():
            sensor.enable(time_step)
        for sensor in self.feet.values():
            sensor.enable(time_step)
        self.ready = False
        self.log = (directory / f'motion-{robot.getName()}-{os.getpid()}.jsonl').open('w', buffering=1)
        self.write({'event': 'motion_diagnostics_config', 'schema_version': 1,
                    'sample_period_ms': time_step, 'joints': list(self.joints),
                    'foot_sensors': list(self.feet), 'force_frame': 'sensor_local_xyz'})

    def write(self, row):
        self.log.write(json.dumps(finite({'robot': self.robot.getName(),
                                         'time': self.robot.getTime(), **row}), allow_nan=False) + '\n')

    def snapshot(self, owner, event='motion_sample', **extra):
        motion = owner.current
        row = {'event': event, 'action': owner.current_action,
               'behaviour': owner.current_behaviour, 'navigation_stage': owner.navigation_stage,
               'motion_time_ms': motion.getTime() if motion else None,
               'motion_duration_ms': motion.getDuration() if motion else None,
               'motion_over': motion.isOver() if motion else None, **extra}
        if self.ready:
            row['imu_rpy'] = list(self.imu.getRollPitchYaw())
            # R2023b returns a ctypes pointer, so iteration without a bound is unsafe.
            row['foot_force_local'] = {name: list(sensor.getValues()[:3]) for name, sensor in self.feet.items()}
            row['joints'] = {name: {'target': motor.getTargetPosition(), 'actual': sensor.getValue(),
                                    'error': motor.getTargetPosition() - sensor.getValue()}
                             for name, (motor, sensor) in self.joints.items()}
            world = owner.observation.world
            if world and owner.name in world['robots']:
                row['reference_position'] = world['robots'][owner.name]['position']
        self.write(row)

    def close(self):
        self.log.close()
