"""Installer safety and launch isolation checks; no system packages are installed."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def shell(self, body, *args):
        return subprocess.run(
            ["bash", "-c", 'source "$1"; shift\n' + body,
             "installer-test", str(ROOT / "install.sh"), *map(str, args)],
            text=True, capture_output=True, timeout=20,
        )

    def test_only_supported_os_architecture_and_native_kernel_pass(self):
        cases = [
            ("ubuntu", "20.04", "x86_64", "5.15.0-generic", True),
            ("ubuntu", "22.04", "x86_64", "6.8.0-generic", True),
            ("ubuntu", "18.04", "x86_64", "generic", False),
            ("ubuntu", "24.04", "x86_64", "generic", False),
            ("debian", "22.04", "x86_64", "generic", False),
            ("darwin", "12", "x86_64", "darwin", False),
            ("ubuntu", "22.04", "aarch64", "generic", False),
            ("ubuntu", "20.04", "i686", "generic", False),
            ("ubuntu", "22.04", "x86_64", "5.15-microsoft-standard-WSL2", False),
        ]
        for os_name, version, arch, kernel, allowed in cases:
            with self.subTest(os=os_name, version=version, arch=arch, kernel=kernel):
                result = self.shell('validate_platform "$@"', os_name, version, arch, kernel)
                self.assertEqual(result.returncode == 0, allowed, result.stderr)

    def test_base_and_path_like_environment_names_are_rejected(self):
        for name in ("base", "../base", "/tmp/other-env", "two words", "-option"):
            with self.subTest(name=name):
                result = self.shell('main --dry-run --env-name "$1"', name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("环境名", result.stderr)

    def test_help_and_conflicting_modes(self):
        result = self.shell("main --help")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.shell("main --check --dry-run")
        self.assertNotEqual(result.returncode, 0)

    def test_preview_does_not_create_state_or_download(self):
        with tempfile.TemporaryDirectory(prefix="installer-preview-") as directory:
            project = Path(directory) / "project with spaces"
            (project / "Wenao/worlds").mkdir(parents=True)
            (project / "Wenao/controllers/Utils").mkdir(parents=True)
            for name in ("requirements-tested.txt", "Wenao/worlds/naotdp.wbt",
                         "Wenao/controllers/Utils/best.pt"):
                (project / name).write_bytes(b"fixture")
            result = self.shell(r'''
PROJECT_DIR=$1
check_platform() { :; }
find_conda() { CONDA_BIN=; }
find_environment() { ENV_PREFIX=; }
find_webots() { WEBOTS_BIN=; }
download_verified() { exit 91; }
sudo() { exit 92; }
main --dry-run
''', project)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((project / ".setup").exists())
            self.assertEqual((project / "Wenao/worlds/naotdp.wbt").read_bytes(), b"fixture")

    def test_valid_download_is_verified_then_reused(self):
        with tempfile.TemporaryDirectory(prefix="installer-cache-") as directory:
            source = Path(directory) / "source.bin"
            target = Path(directory) / "cached asset.bin"
            source.write_bytes(b"verified installer fixture")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            result = self.shell(r'''
fixture_source=$1
fixture_target=$2
fixture_sha=$3
curl() { cp -- "$fixture_source" "${@: -1}"; }
download_verified https://example.invalid/asset "$fixture_sha" "$fixture_target"
curl() { exit 93; }
download_verified https://example.invalid/asset "$fixture_sha" "$fixture_target"
''', source, target, digest)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), source.read_bytes())

    def test_bad_checksum_cannot_replace_cached_file(self):
        with tempfile.TemporaryDirectory(prefix="installer-tamper-") as directory:
            source = Path(directory) / "tampered.bin"
            target = Path(directory) / "cached.bin"
            source.write_bytes(b"tampered payload")
            target.write_bytes(b"old file remains")
            result = self.shell(r'''
fixture_source=$1
fixture_target=$2
curl() { cp -- "$fixture_source" "${@: -1}"; }
download_verified https://example.invalid/asset "$3" "$fixture_target"
''', source, target, "0" * 64)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), b"old file remains")

    def test_existing_other_webots_version_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="installer-webots-") as directory:
            executable = Path(directory) / "webots"
            data = b'#!/bin/bash\nprintf "Webots version: R2025a\\n"\n'
            executable.write_bytes(data)
            executable.chmod(0o755)
            result = self.shell('WEBOTS_BIN=$1; find_webots', executable)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("其他 Webots 版本", result.stderr)
            self.assertEqual(executable.read_bytes(), data)

    def test_launch_quotes_paths_and_clears_conflicting_environment(self):
        with tempfile.TemporaryDirectory(prefix="installer-launch-") as directory:
            project = Path(directory) / "project with spaces"
            state = project / ".setup"
            state.mkdir(parents=True)
            shutil.copyfile(ROOT / "launch.sh", project / "launch.sh")
            # Isolate desktop detection from the launch argument/environment test.
            (project / "install.sh").write_text(
                (ROOT / "install.sh").read_text() + '\ncheck_platform() { :; }\n'
            )
            bin_dir = Path(directory) / "env with spaces/bin"
            bin_dir.mkdir(parents=True)
            for name in ("python", "python3"):
                (bin_dir / name).symlink_to(sys.executable)
            webots = Path(directory) / "webots fixture"
            webots.write_text('''#!/usr/bin/env python3
import json, os, shutil, sys
print(json.dumps({"args": sys.argv[1:], "python": shutil.which("python"),
 "conflicts": {k: os.environ.get(k) for k in
 ("PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH")}}))
''')
            webots.chmod(0o755)
            (state / "python-path").write_text(str(bin_dir / "python") + "\n")
            (state / "webots-path").write_text(str(webots) + "\n")
            environment = os.environ.copy()
            for name in ("PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH",
                         "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
                environment[name] = "/invalid/conflicting/path"
            environment["DISPLAY"] = ":fixture"
            result = subprocess.run(
                ["bash", str(project / "launch.sh"), "--stdout"], env=environment,
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout.splitlines()[-1])
            self.assertEqual(payload["args"], ["--stdout", str(project / "Wenao/worlds/naotdp.wbt")])
            self.assertEqual(payload["python"], str(bin_dir / "python"))
            self.assertTrue(all(value is None for value in payload["conflicts"].values()))


if __name__ == "__main__":
    unittest.main()
