import subprocess
import tempfile
import uuid
from pathlib import Path

from .config import ensure_tool_path

NO_IMAGE_STATUS = 2
SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]


def _clipboard_to_png(destination):
    try:
        result = subprocess.run(["pngpaste", destination], stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise ValueError("pngpaste is not installed. Install it with: brew install pngpaste")
    return result.returncode == 0


def _file_to_png(source, destination):
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError("no such image file: " + str(source))
    subprocess.run(
        ["sips", "-s", "format", "png", str(source), "--out", destination],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def upload(host, directory, image=None):
    """Upload one image and return its remote path, or None when no image exists."""
    ensure_tool_path()
    with tempfile.TemporaryDirectory(prefix="remote-image-paste-") as temporary:
        png = str(Path(temporary) / "clip.png")
        if image is not None:
            _file_to_png(image, png)
        elif not _clipboard_to_png(png):
            return None
        # Each upload gets a unique name so earlier pastes stay valid.
        remote = directory + "/clip-" + str(uuid.uuid4()) + ".png"
        # scp preserves the local mode, so restrict the source before transfer.
        Path(png).chmod(0o600)
        subprocess.run(["ssh", "-T", *SSH_OPTIONS, host,
                        "umask 077; mkdir -p " + _shell_quote(directory)], check=True)
        subprocess.run(["scp", "-p", "-q", *SSH_OPTIONS, png, host + ":" + remote], check=True)
        return remote


def _shell_quote(value):
    return "'" + value.replace("'", "'\\''") + "'"