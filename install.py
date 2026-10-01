#!/usr/bin/env python3
"""Install or remove the local Ghostty macOS Service. No network operations."""
import argparse
import json
from pathlib import Path
import plistlib
import shutil
import sys

ROOT = Path(__file__).resolve().parent
SERVICE = 'Remote Image Paste'


def locations(home):
    return (home / 'Library/Application Support/remote-image-paste',
            home / 'Library/Services' / (SERVICE + '.workflow'),
            home / '.config/remote-image-paste/config.json')


def install(home, host, marker):
    support, service, config = locations(home)
    if support.exists() or service.exists() or config.exists():
        raise ValueError('Already installed or destination exists. Uninstall first; existing files were not overwritten.')
    # Validate user input using the runtime's validation before creating files.
    import runpy
    runtime = runpy.run_path(str(ROOT / 'bin/remote-image-paste'))
    import os
    import tempfile
    values = dict(ssh_host=host, terminal_title_contains=marker,
                  remote_directory='/tmp/remote-image-paste')
    with tempfile.TemporaryDirectory() as temporary:
        test_config = Path(temporary) / 'config.json'
        test_config.write_text(json.dumps(values))
        original = os.environ.get('REMOTE_IMAGE_PASTE_CONFIG')
        os.environ['REMOTE_IMAGE_PASTE_CONFIG'] = str(test_config)
        try:
            runtime['load_config']()
        finally:
            if original is None:
                os.environ.pop('REMOTE_IMAGE_PASTE_CONFIG', None)
            else:
                os.environ['REMOTE_IMAGE_PASTE_CONFIG'] = original
    support.mkdir(parents=True)
    shutil.copy2(ROOT / 'bin/remote-image-paste', support)
    (support / 'remote-image-paste').chmod(0o755)
    shutil.copy2(ROOT / 'bin/remote-image-paste.applescript', support)
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(values, indent=2) + '\n')
    contents = service / 'Contents'
    contents.mkdir(parents=True)
    info = {'NSServices': [{'NSMenuItem': {'default': SERVICE},
             'NSMessage': 'runWorkflowAsService',
             'NSRequiredContext': {'NSApplicationIdentifier': 'com.mitchellh.ghostty'}}]}
    command = '/usr/bin/osascript "$HOME/Library/Application Support/remote-image-paste/remote-image-paste.applescript"'
    action = {
        'AMAccepts': {'Container': 'List', 'Optional': True, 'Types': ['com.apple.cocoa.string']},
        'AMProvides': {'Container': 'List', 'Types': ['com.apple.cocoa.string']},
        'AMActionVersion': '2.0.3', 'AMApplication': ['Automator'],
        'AMParameterProperties': {key: {} for key in ['COMMAND_STRING', 'CheckedForUserDefaultShell', 'inputMethod', 'shell', 'source']},
        'ActionBundlePath': '/System/Library/Automator/Run Shell Script.action',
        'ActionName': 'Run Shell Script',
        'ActionParameters': {'COMMAND_STRING': command, 'CheckedForUserDefaultShell': True,
                             'inputMethod': 0, 'shell': '/bin/bash', 'source': ''},
        'BundleIdentifier': 'com.apple.RunShellScript', 'CFBundleVersion': '2.0.3',
        'CanShowSelectedItemsWhenRun': False, 'CanShowWhenRun': True,
        'Category': ['AMCategoryUtilities'], 'Class Name': 'RunShellScriptAction',
        'InputUUID': 'C8858263-5046-4098-8CF3-1B35ED0AFD8D',
        'OutputUUID': '3D390149-4FB2-4776-86AC-47F0CB792F78',
        'UUID': 'CC5869BF-7E01-4B42-8E5D-C13A8B2710BB',
        'UnlocalizedApplications': ['Automator'], 'isViewVisible': 1,
        'nibPath': '/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib',
    }
    metadata = {
        'applicationBundleIDsByPath': {'/Applications/Ghostty.app': 'com.mitchellh.ghostty'},
        'applicationPaths': ['/Applications/Ghostty.app'],
        'inputTypeIdentifier': 'com.apple.Automator.nothing',
        'outputTypeIdentifier': 'com.apple.Automator.nothing',
        'presentationMode': 15, 'processesInput': False,
        'serviceApplicationBundleIdentifier': 'com.mitchellh.ghostty',
        'serviceApplicationPath': '/Applications/Ghostty.app',
        'serviceInputTypeIdentifier': 'com.apple.Automator.nothing',
        'serviceOutputTypeIdentifier': 'com.apple.Automator.nothing',
        'serviceProcessesInput': False, 'systemImageName': 'NSActionTemplate',
        'useAutomaticInputType': False, 'workflowTypeIdentifier': 'com.apple.Automator.servicesMenu',
    }
    workflow = {'AMApplicationBuild': '534', 'AMApplicationVersion': '2.10',
                'AMDocumentVersion': '2', 'actions': [{'action': action, 'isViewVisible': 1}],
                'connectors': {}, 'workflowMetaData': metadata}
    for name, data in [('Info.plist', info), ('document.wflow', workflow)]:
        with (contents / name).open('wb') as output:
            plistlib.dump(data, output)
    print('Installed. Assign Control-V to Remote Image Paste in macOS Keyboard > Keyboard Shortcuts > Services.')
    print('Configuration: ' + str(config))


def uninstall(home):
    support, service, config = locations(home)
    for directory in (support, service):
        if directory.exists():
            shutil.rmtree(directory)
    # Keep user configuration so it is not lost during removal.
    print('Removed scripts and Service. Configuration retained at ' + str(config))
    print('Remove its shortcut in macOS Keyboard Shortcuts > Services if it remains listed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--ssh-host')
    parser.add_argument('--title-contains')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This integration requires macOS')
    try:
        if args.uninstall:
            uninstall(Path.home())
        else:
            if not args.ssh_host or not args.title_contains:
                parser.error('--ssh-host and --title-contains are required')
            install(Path.home(), args.ssh_host, args.title_contains)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
