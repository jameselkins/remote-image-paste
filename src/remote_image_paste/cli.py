import argparse
import subprocess
import sys

from . import __version__, config as config_module, service, upload as upload_module

NO_IMAGE_STATUS = 2
NOT_REMOTE_STATUS = 3


def _fail(error):
    print("Remote image paste failed: " + str(error), file=sys.stderr)
    return 1


def _require_macos():
    if not service.is_macos():
        print("This integration requires macOS.", file=sys.stderr)
        return 1
    return 0


def _setup_commands(parser):
    setup = parser.add_argument_group("setup")
    setup.add_argument("--ssh-host", metavar="HOST",
                       help="SSH alias or user@hostname from ~/.ssh/config used for uploads")
    setup.add_argument("--title-contains", metavar="TEXT",
                       help="distinctive substring of your remote terminal title")
    setup.add_argument("--remote-directory", metavar="PATH", default=config_module.DEFAULT_DIRECTORY,
                       help="absolute remote directory for uploaded images (default: %(default)s)")
    setup.add_argument("--no-ssh-check", action="store_true",
                       help="skip verifying noninteractive SSH access before installing")
    return setup


def command_install(args, parser):
    if not args.ssh_host or not args.title_contains:
        parser.error("install requires --ssh-host and --title-contains")
    if not args.no_ssh_check and not service.check(args.ssh_host):
        parser.error("noninteractive SSH failed for '" + args.ssh_host +
                     "'. Fix ~/.ssh/config, or pass --no-ssh-check to install anyway.")
    result = service.install(Path_home(), args.ssh_host, args.title_contains, args.remote_directory)
    print("Installed Remote Image Paste.")
    print("Configuration: " + str(result["config"]))
    if not service.ghostty_installed():
        print("Warning: Ghostty was not found at " + str(service.GHOSTTY_BUNDLE) + ".")
    print("Next: System Settings > Keyboard > Keyboard Shortcuts > Services. "
          "Enable '" + service.SERVICE_NAME + "' and assign Control-V.")
    return 0


def command_uninstall(args, parser):
    result = service.uninstall(Path_home())
    if result["removed"]:
        for path in result["removed"]:
            print("Removed " + path)
    else:
        print("Nothing to remove.")
    print("Configuration retained at " + str(result["config"]))
    print("Remove its shortcut in System Settings > Keyboard Shortcuts > Services if still listed.")
    return 0


def command_upload(args, parser):
    host, directory, _marker = config_module.load()
    remote = upload_module.upload(host, directory, args.image)
    if remote is None:
        print("No image in clipboard", file=sys.stderr)
        return NO_IMAGE_STATUS
    print(remote)
    return 0


def command_matches_title(args, parser):
    _host, _directory, marker = config_module.load()
    return 0 if marker in args.matches_title else NOT_REMOTE_STATUS


def Path_home():
    from pathlib import Path
    return Path.home()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="remote-image-paste",
        description="Paste clipboard images into remote OpenCode sessions over SSH from macOS Ghostty.")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    _setup_commands(parser)
    parser.add_argument("--uninstall", action="store_true",
                        help="remove the installed Service and helper, keeping configuration")
    parser.add_argument("--matches-title", metavar="TITLE",
                        help=argparse.SUPPRESS)
    parser.add_argument("image", nargs="?", help="optional local image file instead of the clipboard")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.uninstall:
            blocked = _require_macos()
            if blocked:
                return blocked
            return command_uninstall(args, parser)
        if args.matches_title is not None:
            return command_matches_title(args, parser)
        if args.image is None and not (args.ssh_host or args.title_contains):
            blocked = _require_macos()
            if blocked:
                return blocked
            return command_upload(args, parser)
        blocked = _require_macos()
        if blocked:
            return blocked
        return command_install(args, parser)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        return _fail(error)


if __name__ == "__main__":
    sys.exit(main())