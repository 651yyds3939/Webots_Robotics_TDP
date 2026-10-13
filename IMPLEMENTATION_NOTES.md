# Geometry and implementation changes

Source: the local 9 x 6 metre development profile and preserved implementation records.
The upstream baseline is recorded in THIRD_PARTY_NOTICES.md; this publication uses fresh Git history.

## Geometry and conventions

`Wenao/worlds/naotdp.wbt` now loads the local `CourseSoccerField.proto`
and `CourseGoal.proto`. No cached or installed Webots assets were modified.

| Quantity | Metres |
| --- | ---: |
| Pitch, outside edges of boundary lines | 9 x 6 |
| Clear goal opening, between posts / below crossbar | 2.6 x 1.2 |
| Goal depth, goal-line plane to inner rear net face | 0.6 |
| Goal area, outside edges of its lines | 1 x 3 |
| Penalty area, outside edges of its lines | 2 x 5 |
| Penalty mark distance from goal line | 1.5 |
| Centre circle, outside diameter of line | 1.5 |
| Border strip | 1 |
| Ball diameter | 0.14 |

The configured approximate 14 cm ball diameter is used, rather than converting
45 cm circumference to 14.32 cm. Default size-1 ball mass remains 0.205 kg;
the geometry profile does not specify mass. Boundary lines are inside
the pitch; their 5 cm width, 5 cm post radius, plain green surface, net
appearance, and initial team formation are modelling choices.

The 11 x 8 ground has an open border. The old perimeter collision walls are
removed. Ball centre starts at z=0.07; robots start upright inside the pitch.
Simulation timestep is explicitly 40 ms, matching the Supervisor.
Local geometry and `Utils/CourseSpecs.py` carry the same dimensions; change
both and re-run the checks if dimensions change later.

## Initial geometry, scoring and navigation changes

The scorer detects an outward whole-ball crossing at x=+/-4.57 and checks
the interpolated crossing location against the clear width and height.
The ball must fit inside the opening. It cannot score merely by being
outside, moving back into the pitch, partially crossing, or passing above
the bar. This conservative geometry check is not a complete referee.

After a goal, score and match time persist, saved initial node states are
restored, physics is reset, and player controllers restart. Supervisor yaw
uses the correct orientation matrix column and wraps angle differences.

Red A* controllers use a consistent 0.1 m grid over the 9 x 6 pitch.
Coordinates are (x,y), array indexing is [y,x], and paths are returned in
start-to-goal order. Invalid/unreachable goals return no path.

## Initial vision changes

Ball diameter is 0.14 m. Focal length is derived from each actual camera's
FOV and image width. Reported distance is an approximate optical-axis depth,
not a validated robot-relative ground distance; heading is camera-relative
and positive to the image right. The old 4.5 m clipping is removed.

Weights resolve relative to `ImageServer.py`; image conversion matches the
BGRA Webots buffer; both cameras can be processed. Worker initialization,
full queues, mixed CSV fields and log filenames are handled. Generated logs
are ignored by Git. `BlueForwardA` now honours the configured vision flag.

At this stage, both legacy teams defaulted to `Vision=False` and used
Supervisor ground truth. The later shared-controller implementation below
added optional camera-ball decisions; real-robot calibration remains unverified.

## Verification and remaining work

Run boundary, asymmetric-grid, and camera/CSV tests using the configured env:

```bash
python -B -m unittest discover -s tests -v
python -B tests/run_webots_check.py
```

The automated Webots check uses a temporary copy of the world and a temporary
Supervisor, leaving the actual entry controller unchanged. It checks model
loading, clear goal dimensions, partial/full crossings, score preservation,
kickoff reset, and a short run with the eight existing player controllers.

Full out-of-play/free-kick/foul rules, vision-based decisions, long-run
behaviour success rates, NAO6 dynamics validation and hardware migration
remain to be implemented or assessed. Initial LHand/RHand warnings were later addressed by removing missing motion
channels, as described below; no unverified hand-joint mapping was introduced.

Camera overlay settings are local UI preferences. The ignored
`.naotdp.wbproj` file is excluded from the publication.

## Match and shared-role implementation (2026-10-12)

Eight entry points now use Base/SoccerController; previous player code is retained
in controllers/legacy. MatchEngine supplies typed referee phases, clock, ends,
whole-ball exits, restart awards and restart scoring restrictions. Timing defaults
follow the configured 2025 virtual rules. TeamPolicy implements fixed roles,
one deterministic chaser per team, bounded velocity prediction, support/pass
selection, dribbling, goal-aperture shot selection and goalkeeper line prediction.

NaoV6's legacy IMU rotation was inconsistent with the current ENU world and
disabled pitch. It is now torso-aligned with pitch enabled. Motion loading removes
missing hand channels and clips angles to the model's actual motor limits, recording
the changes. This does not establish physical NAO6 compatibility or recovery success.

Vision mode connects timestamped estimates to ball decisions, with stop on ball
loss and explicit referee localization. It assumes an upright torso and needs
camera calibration and detector accuracy tests. No NAOqi version or hardware
adapter has been invented.

See docs/VALIDATION.md for remaining rules, behavior-performance and
hardware gaps. Automated checks and integration completion are not overall validation.

Pass-intent messages now coordinate the receiver and sender with an expiry and
team/name validation. Kick alignment accounts for the assets' left striking foot.
Referee tests also cover illegal kickoff placement and restart-distance removal.
A real bottom-camera / bundled-YOLO stationary-ball probe detected the ball and
recorded about 1 cm planar error in that one fixture; this is not a calibrated
accuracy claim.

## Publication portability (2026-10-13)

The project directory is named `Webots_Robotics_TDP`. Documentation uses relative
paths, saved evidence replaces local account paths with placeholders, and Notebook
outputs are cleared. Original Git metadata, runtime outputs, and caches remain
outside the published tree. Required third-party attribution remains intact.

The optional Gazebo world `nao_ws/src/nao/nao_gazebo/worlds/nao_new.sdf`
replaces a machine-specific cached Fuel URI with `model://nao`. This ROS/Gazebo
workspace is outside the validated Webots execution path; model lookup must be
configured separately before using that world.
