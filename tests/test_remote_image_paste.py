import contextlib
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from remote_image_paste import cli, config, service, upload  # noqa: E402


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "config.json"
        self.values = {"ssh_host": "devbox",
                       "terminal_title_contains": "devbox-work | ",
                       "remote_directory": "/tmp/remote-image-paste"}
        self.write(self.values)

    def write(self, values):
        self.path.write_text(json.dumps(values))

    def test_load_returns_validated_values(self):
        self.assertEqual(config.load(self.path),
                         ("devbox", "/tmp/remote-image-paste", "devbox-work | "))

    def test_rejects_shell_syntax_and_traversal(self):
        rejected = [
            {"ssh_host": "-oProxyCommand=evil"},
            {"ssh_host": "host; rm -rf /"},
            {"remote_directory": "/tmp/a;touch-pwned"},
            {"remote_directory": "/tmp/../root"},
            {"remote_directory": "/tmp/dir with space"},
            {"remote_directory": "/"},
            {"remote_directory": "/tmp/dir/"},
            {"remote_directory": "relative/path"},
            {"terminal_title_contains": ""},
            {"terminal_title_contains": "   "},
        ]
        for override in rejected:
            with self.subTest(override=override):
                self.write(dict(self.values, **override))
                with self.assertRaises(ValueError):
                    config.load(self.path)

    def test_missing_directory_key_falls_back_to_default(self):
        self.write({"ssh_host": "devbox", "terminal_title_contains": "m | "})
        self.assertEqual(config.load(self.path)[1], config.DEFAULT_DIRECTORY)

    def test_missing_required_key_is_an_error(self):
        self.write({"ssh_host": "devbox"})
        with self.assertRaises(KeyError):
            config.load(self.path)

    def test_env_override_selects_config_path(self):
        other = Path(self.temporary.name) / "other.json"
        other.write_text(json.dumps(dict(self.values, ssh_host="otherbox")))
        with patch.dict(os.environ, {config.CONFIG_ENV: str(other)}):
            self.assertEqual(config.load()[0], "otherbox")


class UploadTests(unittest.TestCase):
    def test_clipboard_upload_uses_unique_names_and_cleans_up(self):
        commands, temporaries = [], []

        def run(command, **kwargs):
            commands.append(command)
            if command[0] == "pngpaste":
                Path(command[1]).write_bytes(b"png")
                temporaries.append(Path(command[1]))
            return subprocess.CompletedProcess(command, 0)

        with patch("subprocess.run", side_effect=run):
            first = upload.upload("devbox", "/tmp/remote-image-paste")
            second = upload.upload("devbox", "/tmp/remote-image-paste")
        self.assertNotEqual(first, second)
        for remote in (first, second):
            self.assertTrue(remote.startswith("/tmp/remote-image-paste/clip-"))
            self.assertTrue(remote.endswith(".png"))
        self.assertTrue(all(not path.exists() for path in temporaries))
        self.assertEqual([c[0] for c in commands], ["pngpaste", "ssh", "scp"] * 2)

    def test_scoped_permissions_and_noninteractive_ssh(self):
        seen = {}

        def run(command, **kwargs):
            if command[0] == "pngpaste":
                Path(command[1]).write_bytes(b"png")
            if command[0] == "scp":
                seen["scp"] = command
                # The temporary file is gone once upload returns, so record
                # its mode while scp would still be reading it.
                seen["mode"] = Path(command[-2]).stat().st_mode & 0o777
            return subprocess.CompletedProcess(command, 0)

        with patch("subprocess.run", side_effect=run):
            upload.upload("devbox", "/tmp/remote-image-paste")
        scp = seen["scp"]
        self.assertIn("-p", scp)
        self.assertIn("BatchMode=yes", scp)
        self.assertEqual(seen["mode"], 0o600)

    def test_no_image_returns_none_without_touching_ssh(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertIsNone(upload.upload("devbox", "/tmp/remote-image-paste"))
            self.assertEqual(run.call_count, 1)

    def test_missing_pngpaste_raises_actionable_error(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("pngpaste")):
            with self.assertRaisesRegex(ValueError, "brew install pngpaste"):
                upload.upload("devbox", "/tmp/remote-image-paste")

    def test_remote_directory_is_quoted_in_mkdir(self):
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if command[0] == "pngpaste":
                Path(command[1]).write_bytes(b"png")
            return subprocess.CompletedProcess(command, 0)

        with patch("subprocess.run", side_effect=run):
            upload.upload("devbox", "/tmp/remote-image-paste")
        mkdir = next(c for c in commands if c[0] == "ssh")
        self.assertIn("mkdir -p '/tmp/remote-image-paste'", mkdir[-1])
        self.assertIn("umask 077", mkdir[-1])

    def test_file_upload_converts_to_png(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "image with spaces.jpg"
            source.write_bytes(b"fixture")
            commands = []

            def run(command, **kwargs):
                commands.append(command)
                if command[0] == "sips":
                    Path(command[-1]).write_bytes(b"png")
                return subprocess.CompletedProcess(command, 0)

            with patch("subprocess.run", side_effect=run):
                upload.upload("devbox", "/tmp/remote-image-paste", str(source))
        self.assertEqual([c[0] for c in commands], ["sips", "ssh", "scp"])
        self.assertEqual(commands[0][4], str(source.resolve()))

    def test_missing_file_is_reported(self):
        with self.assertRaisesRegex(ValueError, "no such image file"):
            upload.upload("devbox", "/tmp/remote-image-paste", "/nonexistent/file.png")

    def test_ssh_failure_cleans_up_and_does_not_fall_back(self):
        temporaries = []

        def run(command, **kwargs):
            if command[0] == "pngpaste":
                Path(command[1]).write_bytes(b"png")
                temporaries.append(Path(command[1]))
                return subprocess.CompletedProcess(command, 0)
            raise subprocess.CalledProcessError(255, command)

        with patch("subprocess.run", side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError):
                upload.upload("devbox", "/tmp/remote-image-paste")
        self.assertTrue(all(not path.exists() for path in temporaries))


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)

    def test_install_writes_launcher_service_and_config(self):
        with patch.object(service, "_launcher", return_value="#!/bin/sh\nexec true\n"):
            with contextlib.redirect_stdout(io.StringIO()):
                result = service.install(self.home, "devbox", "devbox-work | ")
        support, service_path, config_path = service.locations(self.home)
        launcher = support / "remote-image-paste"
        self.assertTrue(os.access(launcher, os.X_OK))
        self.assertIn("exec", launcher.read_text())
        self.assertTrue((support / "remote-image-paste.applescript").is_file())
        for name in ("Info.plist", "document.wflow"):
            with (service_path / "Contents" / name).open("rb") as handle:
                self.assertIsInstance(plistlib.load(handle), dict)
        self.assertEqual(json.loads(config_path.read_text()),
                         {"ssh_host": "devbox", "terminal_title_contains": "devbox-work | ",
                          "remote_directory": config.DEFAULT_DIRECTORY})
        self.assertEqual(result["config"], config_path)

    def test_install_never_overwrites_existing_installation(self):
        with patch.object(service, "_launcher", return_value="#!/bin/sh\nexit 0\n"):
            with contextlib.redirect_stdout(io.StringIO()):
                service.install(self.home, "devbox", "devbox-work | ")
        support, _service, config_path = service.locations(self.home)
        marker = support / "user-edited.txt"
        marker.write_text("keep me")
        with patch.object(service, "_launcher", return_value="#!/bin/sh\nexit 0\n"):
            with self.assertRaises(ValueError):
                service.install(self.home, "otherbox", "otherbox | ")
        self.assertEqual(marker.read_text(), "keep me")
        self.assertEqual(json.loads(config_path.read_text())["ssh_host"], "devbox")

    def test_install_refuses_without_console_script_on_path(self):
        with patch.object(service, "_launcher", return_value=None):
            with self.assertRaisesRegex(ValueError, "not on PATH"):
                service.install(self.home, "devbox", "devbox-work | ")
        support, service_path, _config = service.locations(self.home)
        self.assertFalse(support.exists())
        self.assertFalse(service_path.exists())

    def test_install_validates_before_creating_anything(self):
        with patch.object(service, "_launcher", return_value="#!/bin/sh\nexit 0\n"):
            with self.assertRaises(ValueError):
                service.install(self.home, "-oProxyCommand=evil", "m | ")
        support, service_path, _config = service.locations(self.home)
        self.assertFalse(support.exists())
        self.assertFalse(service_path.exists())

    def test_uninstall_keeps_config_and_other_services(self):
        other = self.home / "Library/Services/Some Other Service.workflow"
        other.mkdir(parents=True)
        with patch.object(service, "_launcher", return_value="#!/bin/sh\nexit 0\n"):
            with contextlib.redirect_stdout(io.StringIO()):
                service.install(self.home, "devbox", "devbox-work | ")
        support, service_path, config_path = service.locations(self.home)
        result = service.uninstall(self.home)
        self.assertFalse(support.exists())
        self.assertFalse(service_path.exists())
        self.assertTrue(config_path.exists())
        self.assertTrue(other.exists())
        self.assertIn(str(config_path), result["config"].as_posix())
        self.assertIn(str(support), " ".join(result["removed"]))

    def test_uninstall_is_idempotent(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(service.uninstall(self.home)["removed"], [])


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.config_path = Path(self.temporary.name) / "config.json"
        self.config_path.write_text(json.dumps(
            {"ssh_host": "devbox", "terminal_title_contains": "devbox-work | ",
             "remote_directory": "/tmp/remote-image-paste"}))
        self.environment = patch.dict(os.environ, {config.CONFIG_ENV: str(self.config_path)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = cli.main(argv)
        return status, out.getvalue(), err.getvalue()

    def test_matches_title_controls_where_images_are_pasted(self):
        with patch("subprocess.run") as run:
            self.assertEqual(self.run_cli(["--matches-title", "main | OpenCode"])[0], 3)
            self.assertEqual(self.run_cli(["--matches-title", "devbox-work | OpenCode"])[0], 0)
            run.assert_not_called()

    def test_upload_prints_path_or_reports_no_image(self):
        with patch.object(upload, "upload", return_value="/tmp/remote-image-paste/clip-1.png"):
            status, out, _err = self.run_cli([])
            self.assertEqual(status, 0)
            self.assertEqual(out.strip(), "/tmp/remote-image-paste/clip-1.png")
        with patch.object(upload, "upload", return_value=None):
            status, _out, err = self.run_cli([])
            self.assertEqual(status, cli.NO_IMAGE_STATUS)
            self.assertIn("No image in clipboard", err)

    def test_explicit_image_path_is_never_treated_as_install(self):
        # Regression: a manual upload with a file argument was misrouted to
        # install and aborted with "install requires --ssh-host".
        with patch.object(upload, "upload", return_value="/tmp/remote-image-paste/clip-9.png") as uploader, \
                patch.object(service, "install") as installer:
            status, out, _err = self.run_cli(["/tmp/some screenshot.png"])
        self.assertEqual(status, 0)
        self.assertEqual(out.strip(), "/tmp/remote-image-paste/clip-9.png")
        uploader.assert_called_once()
        self.assertEqual(uploader.call_args.args[2], "/tmp/some screenshot.png")
        installer.assert_not_called()

    def test_upload_failure_is_status_one_not_text_fallback(self):
        with patch.object(upload, "upload", side_effect=subprocess.CalledProcessError(255, "scp")):
            status, _out, err = self.run_cli([])
            self.assertEqual(status, 1)
            self.assertNotEqual(status, cli.NO_IMAGE_STATUS)
            self.assertIn("failed", err)

    def test_invalid_config_reports_failure(self):
        self.config_path.write_text(json.dumps({"ssh_host": "host; rm -rf /",
                                                "terminal_title_contains": "m | "}))
        with patch("subprocess.run") as run:
            status, _out, err = self.run_cli([])
            self.assertEqual(status, 1)
            run.assert_not_called()
            self.assertIn("ssh_host", err)

    def test_install_requires_destination_arguments(self):
        with self.assertRaises(SystemExit):
            self.run_cli(["--ssh-host", "devbox"])

    def test_install_checks_ssh_before_installing(self):
        with patch.object(service, "check", return_value=False), \
                patch.object(service, "_launcher") as launcher:
            with self.assertRaises(SystemExit):
                self.run_cli(["--ssh-host", "devbox", "--title-contains", "m | "])
            launcher.assert_not_called()

    def test_install_prints_next_step_and_warns_about_missing_ghostty(self):
        with tempfile.TemporaryDirectory() as home, patch.object(service, "check", return_value=True), \
                patch.object(service, "_launcher", return_value="#!/bin/sh\nexit 0\n"), \
                patch.object(service, "ghostty_installed", return_value=False), \
                patch.object(cli, "Path_home", return_value=Path(home)):
            status, out, _err = self.run_cli(["--ssh-host", "devbox", "--title-contains", "m | "])
        self.assertEqual(status, 0)
        self.assertIn("Keyboard Shortcuts", out)
        self.assertIn("Ghostty was not found", out)

    def test_uninstall_is_mac_only(self):
        with patch.object(service, "is_macos", return_value=False):
            status, _out, err = self.run_cli(["--uninstall"])
        self.assertEqual(status, 1)
        self.assertIn("requires macOS", err)

    def test_upload_is_mac_only(self):
        with patch.object(service, "is_macos", return_value=False):
            status, _out, _err = self.run_cli([])
        self.assertEqual(status, 1)

    def test_help_documents_install_arguments(self):
        text = build_help()
        for flag in ("--ssh-host", "--title-contains", "--remote-directory", "--uninstall"):
            self.assertIn(flag, text)


def build_help():
    parser = cli.build_parser()
    return parser.format_help()


if __name__ == "__main__":
    unittest.main()