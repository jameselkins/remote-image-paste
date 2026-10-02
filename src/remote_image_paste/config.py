import json
import os
from pathlib import Path
import re

DEFAULT_DIRECTORY = "/tmp/remote-image-paste"
CONFIG_ENV = "REMOTE_IMAGE_PASTE_CONFIG"

# macOS Services do not inherit the interactive shell's Homebrew PATH, so the
# helper must find pngpaste, sips, ssh and scp on its own.
TOOL_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:"


def ensure_tool_path():
    os.environ["PATH"] = TOOL_PATH + os.environ.get("PATH", "")


def default_config_path():
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override)
    return Path.home() / ".config/remote-image-paste/config.json"


def validate(host, marker, directory):
    if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", host):
        raise ValueError("ssh_host must be an SSH alias or user@hostname, without options")
    if not isinstance(marker, str) or not marker.strip():
        raise ValueError("terminal_title_contains must be a nonempty, distinctive remote terminal title marker")
    if not isinstance(directory, str) or not directory.startswith("/"):
        raise ValueError("remote_directory must be an absolute path")
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", directory) or ".." in directory.split("/"):
        raise ValueError("remote_directory may use only letters, numbers, _, ., / and -")
    if directory == "/" or directory.endswith("/"):
        raise ValueError("remote_directory must name a directory without a trailing slash")
    return host, directory, marker


def load(path=None):
    location = Path(path) if path else default_config_path()
    values = json.loads(location.read_text())
    return validate(
        values["ssh_host"],
        values["terminal_title_contains"],
        values.get("remote_directory", DEFAULT_DIRECTORY),
    )