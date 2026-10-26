# Third-party sources and notices

## Upstream project

The Webots simulation is derived from [RajasJoshi/UoG_Robotics_TDP4](https://github.com/RajasJoshi/UoG_Robotics_TDP4), baseline commit `8a0949302aac5d610339fa02f3e4cfc437abb17d`.

Recorded upstream commit authors include Rajas Joshi, Jamie Milsom, Wan NurSabrina, and the display name `rajas`. Commit authorship is not a complete statement of copyright ownership or contribution size. The root [LICENSE](LICENSE) contains Apache-2.0; the upstream README contained a conflicting MIT description. Original copyright and file-specific notices remain in the source.

The upstream README listed the following reference projects:

- [UofG-RoboticsTeam9/RoboCupSoccer](https://github.com/UofG-RoboticsTeam9/RoboCupSoccer)
- [Bembelbots/WebotsLoLaController](https://github.com/Bembelbots/WebotsLoLaController)
- [amirhnourian/WebotsNaoWresteling](https://github.com/amirhnourian/WebotsNaoWresteling)

These links document third-party provenance. They do not state an affiliation of the current repository maintainer.

## Models and assets

`Wenao/protos/Nao.proto` and `NaoV6.proto` retain Cyberbotics copyright and the file-specific restriction for use with Webots. Other model files, meshes, textures, and vendored workspaces retain their existing notices. The root license does not replace independent asset terms.

`Wenao/controllers/Utils/Heuristics.py` retains author notices for Atsushi Sakai and Nikos Kanargias.

The optional `nao_ws/` workspace contains vendored ROS/Gazebo packages, public upstream maintainer contacts, and their existing license files. Those contacts are third-party attribution, not local account metadata.

## Development modifications

Development modifications cover scene geometry, referee phases, shared role policy, navigation, camera-ball experiments, motion loading, tests, and publication documentation. Details are recorded in [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) and [PROJECT_HISTORY.md](PROJECT_HISTORY.md).

The publication snapshot uses fresh local Git history. The original upstream commit identity is retained above, rather than presenting inherited code as newly authored work.

## Alumni design references, 2026-10-25

- [mushyalpha/robotics-tdp-team1](https://github.com/mushyalpha/robotics-tdp-team1), commit `4df4e64d6bf5798752e15b8c6745f7f78765f285`: `Pyrus2D/simple_soccer_sim3.py` illustrates fast 2D role experiments. The new adapter instead calls this repository's existing policy, navigation and referee. No alumni simulator source is vendored.
- [Team 14's project](https://github.com/ENG5325-Robotics-TDP-M-Team-14/Cyberphysical-RoboCup-Soccer-Teams), commit `bbf0df8ce9142f66a64a53c7768e48b3e2a90c7d`: `environment/3d-environment/FCPCodebase/agent/Agent.py`, especially its non-active player's possession-dependent support line, is the design reference for the optional support experiment. Its code, coordinates and motion implementation are not copied or imported. The upstream FCP subdirectory has its own GPL-3.0 license, separate from the outer repository's Apache-2.0 license.

Experiment scope and limitations are recorded in [ALUMNI_TRANSFER_EXPERIMENTS.md](docs/ALUMNI_TRANSFER_EXPERIMENTS.md). Assisted development is not evidence of independently completed student contributions.
