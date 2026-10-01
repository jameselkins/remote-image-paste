import contextlib
import io
import json
import os
from pathlib import Path
import plistlib
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
runtime = runpy.run_path(str(ROOT / 'bin/remote-image-paste'))
installer = runpy.run_path(str(ROOT / 'install.py'))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.config = self.home / 'config.json'
        self.values = dict(ssh_host='devbox', terminal_title_contains='devbox-work | ',
                           remote_directory='/tmp/remote-image-paste')
        self.config.write_text(json.dumps(self.values))
        self.environment = patch.dict(os.environ, REMOTE_IMAGE_PASTE_CONFIG=str(self.config))
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def invoke(self, *args):
        with patch('sys.argv', ['remote-image-paste', *args]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return runtime['main']()

    def test_distinct_title_prevents_local_upload(self):
        with patch('subprocess.run') as run:
            self.assertEqual(self.invoke('--matches-title', 'main | OpenCode'), 3)
            self.assertEqual(self.invoke('--matches-title', 'devbox-work | OpenCode'), 0)
            run.assert_not_called()

    def test_rejects_shell_syntax_and_empty_marker(self):
        for field, value in [('ssh_host', '-oProxyCommand=evil'),
                             ('remote_directory', '/tmp/a;touch-pwned'),
                             ('remote_directory', '/tmp/../root'),
                             ('terminal_title_contains', '')]:
            values = dict(self.values, **{field: value})
            self.config.write_text(json.dumps(values))
            with patch('subprocess.run') as run:
                self.assertEqual(self.invoke(), 1)
                run.assert_not_called()

    def test_no_image_uses_fallback_status_without_ssh(self):
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertEqual(self.invoke(), 2)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], 'pngpaste')

    def test_missing_pngpaste_is_error_not_text_fallback(self):
        with patch('subprocess.run', side_effect=FileNotFoundError('pngpaste')):
            self.assertEqual(self.invoke(), 1)

    def test_unique_uploads_permissions_cleanup_and_no_clipboard_writes(self):
        commands = []
        temporary_files = []

        def run(command, **kwargs):
            commands.append(command)
            if command[0] == 'pngpaste':
                Path(command[1]).write_bytes(b'png fixture')
                temporary_files.append(Path(command[1]))
            if command[0] == 'scp':
                self.assertEqual(Path(command[-2]).stat().st_mode & 0o777, 0o600)
                self.assertIn('-p', command)
            return subprocess.CompletedProcess(command, 0)

        with patch('subprocess.run', side_effect=run):
            first = runtime['upload']('devbox', '/tmp/remote-image-paste')
            second = runtime['upload']('devbox', '/tmp/remote-image-paste')
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith('/tmp/remote-image-paste/clip-'))
        self.assertTrue(all(not path.exists() for path in temporary_files))
        self.assertEqual([c[0] for c in commands], ['pngpaste', 'ssh', 'scp'] * 2)

    def test_ssh_failure_cleans_local_image_and_is_not_fallback(self):
        temporary_files = []

        def run(command, **kwargs):
            if command[0] == 'pngpaste':
                Path(command[1]).write_bytes(b'png fixture')
                temporary_files.append(Path(command[1]))
                return subprocess.CompletedProcess(command, 0)
            raise subprocess.CalledProcessError(255, command)

        with patch('subprocess.run', side_effect=run):
            self.assertEqual(self.invoke(), 1)
        self.assertTrue(all(not path.exists() for path in temporary_files))

    def test_file_upload_converts_to_png(self):
        source = self.home / 'image with spaces.jpg'
        source.write_bytes(b'fixture')
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if command[0] == 'sips':
                Path(command[-1]).write_bytes(b'png fixture')
            return subprocess.CompletedProcess(command, 0)

        with patch('subprocess.run', side_effect=run):
            runtime['upload']('devbox', '/tmp/remote-image-paste', str(source))
        self.assertEqual(commands[0][4], str(source.resolve()))
        self.assertEqual([c[0] for c in commands], ['sips', 'ssh', 'scp'])

    def test_install_uninstall_leaves_other_integrations_and_config(self):
        existing = self.home / 'Library/Services/Personal Paste.workflow'
        existing.mkdir(parents=True)
        with contextlib.redirect_stdout(io.StringIO()):
            installer['install'](self.home, 'devbox', 'devbox-work | ')
        support, service, config = installer['locations'](self.home)
        self.assertTrue(os.access(support / 'remote-image-paste', os.X_OK))
        for name in ['Info.plist', 'document.wflow']:
            with (service / 'Contents' / name).open('rb') as file:
                self.assertIsInstance(plistlib.load(file), dict)
        self.assertEqual(json.loads(config.read_text())['ssh_host'], 'devbox')
        with self.assertRaises(ValueError):
            installer['install'](self.home, 'otherbox', 'otherbox | ')
        self.assertEqual(json.loads(config.read_text())['ssh_host'], 'devbox')
        with contextlib.redirect_stdout(io.StringIO()):
            installer['uninstall'](self.home)
        self.assertFalse(support.exists())
        self.assertFalse(service.exists())
        self.assertTrue(config.exists())
        self.assertTrue(existing.exists())


if __name__ == '__main__':
    unittest.main()
