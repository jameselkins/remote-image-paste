# Remote Image Paste

**Copy a screenshot on your Mac. Press Control-V in remote OpenCode. Get an image attachment.**

For **macOS + Ghostty → SSH → Zellij → OpenCode**. Instead of saving an image,
uploading it, and finding its remote path, a macOS Service does the transfer and
pastes the path into your focused terminal. OpenCode recognizes it as an image.

- Clipboard images stay on your Mac clipboard.
- Each upload gets a unique filename, so later pastes don't overwrite earlier images.
- Text clipboard content is pasted once into matching remote terminals.
- Other terminals receive their original Control-V key.
- Uses your existing SSH configuration. No server daemon, plugin, or additional network service.

## Requirements

- macOS and Ghostty installed at `/Applications/Ghostty.app`, with AppleScript support
  for `terminal id`, `input text`, and `send key`.
- Python 3.9 or newer and [`pngpaste`](https://github.com/jcs/pngpaste).
  With Homebrew: `brew install python pngpaste`.
- A remote Linux machine accessible using noninteractive SSH authentication.
- Remote OpenCode with image-path paste support. Zellij is the original tested
  multiplexer; it is not a dependency of the transfer helper.

**Compatibility:** the original personal integration was verified through Ghostty,
SSH, Zellij, and OpenCode, including multiple image attachments and text fallback.
This packaged version has isolated automated tests and AppleScript compilation
checks; it has not yet been verified end to end on a second machine. Exact version
compatibility has not been established. Other terminals, Windows/Linux clients,
and other coding agents are not currently supported/tested.

## Setup

### 1. Choose an SSH host and a distinct terminal title marker

Use an alias from `~/.ssh/config`, for example `devbox`. Check that it works:

```sh
ssh -T -o BatchMode=yes devbox 'printf "SSH works\n"'
```

Look at the Ghostty title when your remote OpenCode session is active. Choose a
distinct substring that identifies this remote session, such as `devbox-work | `
from a uniquely named Zellij session. The marker is literal and case-sensitive.
OpenCode may change the pane title, so prefer a stable Zellij session prefix.
Avoid generic markers like `main | ` that can also match a local session.

**Title matching selects where images are pasted, not where they are uploaded.**
All matched terminals use the one configured SSH destination. Make sure that
marker only identifies sessions on that destination, with OpenCode ready to
receive an attachment. This tool cannot determine which remote program is active.

### 2. Install

From this repository:

```sh
python3 install.py --ssh-host devbox --title-contains 'devbox-work | '
```

The installer creates:

| Location | Purpose |
| --- | --- |
| `~/Library/Application Support/remote-image-paste/` | Upload helper and Ghostty bridge |
| `~/Library/Services/Remote Image Paste.workflow` | Ghostty-only macOS Service |
| `~/.config/remote-image-paste/config.json` | Your local SSH destination and title marker |

It doesn't alter SSH or Ghostty configuration. It refuses to overwrite existing
installation files or configuration.

### 3. Assign Control-V

1. Open **System Settings → Keyboard → Keyboard Shortcuts → Services**.
2. Find **Remote Image Paste** (usually under General), enable it, and assign **Control-V**.
3. Check that Ghostty has no conflicting explicit `ctrl+v` action and that no other
   macOS Service uses the same shortcut in Ghostty. Disable the old shortcut if
   migrating from a personal version of this integration.
4. If the Service doesn't appear, quit and reopen Ghostty. You can also look under
   **Ghostty → Services → Remote Image Paste**.
5. Allow macOS automation access to Ghostty when prompted.

Command-V keeps its normal Ghostty behavior.

### 4. Paste a screenshot

Capture an image to the clipboard with **Command-Control-Shift-4**. Focus the
remote OpenCode prompt and press **Control-V**. It should show an `[Image N]`
attachment. Then copy some text and check that it pastes only once.

## Configuration

Edit `~/.config/remote-image-paste/config.json`; changes apply on the next paste:

```json
{
  "ssh_host": "devbox",
  "terminal_title_contains": "devbox-work | ",
  "remote_directory": "/tmp/remote-image-paste"
}
```

`ssh_host` accepts a plain SSH alias or `user@hostname`. Use `~/.ssh/config` for
ports, keys, jump hosts, and other options. `remote_directory` must be an absolute
path containing only letters, digits, underscores, dots, slashes, or hyphens.
Spaces, shell syntax, parent traversal, and trailing slashes are rejected.

For manual upload, run:

```sh
python3 bin/remote-image-paste             # clipboard image
python3 bin/remote-image-paste ./shot.jpg  # converts a local image to PNG
```

Both print a bare remote path. Paste that path into remote OpenCode to attach it.
For a separate configuration file, set `REMOTE_IMAGE_PASTE_CONFIG` when invoking
the helper manually. The Service uses the default configuration.

## How it works

```text
Control-V → Ghostty-only macOS Service → capture focused terminal ID and title
  ├─ title doesn't match → send original Control-V
  └─ title matches
      ├─ image → pngpaste → SSH mkdir → SCP unique PNG → input remote path
      └─ text  → input clipboard text once
```

The original terminal ID is retained across the upload, so switching Ghostty tabs
doesn't redirect the paste. The image is transferred over your existing SSH
connection settings. Temporary local files are cleaned up even on failure;
uploaded files remain on the remote machine until you remove them or `/tmp` is
cleared. No automatic remote cleanup runs. Upload errors produce a notification
instead of falling back to a text paste.

## Troubleshooting

- **Nothing happens:** try the Service from Ghostty's menu first. Check its shortcut
  and macOS Automation permission. Python must be available in `/opt/homebrew/bin`,
  `/usr/local/bin`, or `/usr/bin` for the Service.
- **Local Ctrl-V behavior instead of an attachment:** the terminal title didn't
  contain your configured marker. Check the active OpenCode/Zellij title.
- **SSH fails:** run the SSH check above and the manual helper. Authentication must
  work without a password prompt. The helper uses a ten-second connection timeout;
  stalled transfers can still take longer.
- **A path appears without an image attachment:** confirm the destination matches
  this terminal and your OpenCode version recognizes pasted image paths.
- **Duplicate text:** check for another Service or Ghostty keybinding handling Ctrl-V.
- **Image goes to an unexpected pane:** don't change the active Zellij pane during
  an upload. Ghostty's terminal ID identifies the whole terminal, not a Zellij pane.

## Uninstall

```sh
python3 install.py --uninstall
```

This removes the scripts and Service. Remove its shortcut in System Settings if
it remains listed. Configuration and remote uploads are retained. To reinstall,
move or remove `~/.config/remote-image-paste/config.json` first; copy any settings
you want to keep into the new configuration. No other paste utilities are removed.

## Development

No Python packages are required. Run the isolated tests:

```sh
python3 -m unittest discover -s tests -v
```

Tests mock clipboard and SSH commands and install into a temporary home directory.
They don't change your clipboard, hotkeys, installed Service, or remote machine.
For a real end-to-end check, follow setup step 4 and verify that repeated images
attach separately, text pastes once, local Control-V still works, and a failed SSH
upload shows an error without inserting text.

Contributions with tested Ghostty/OpenCode/macOS versions or improved targeting
are welcome. Please include reproduction steps and redact private hostnames/keys.

## License

MIT. Built from a personal remote OpenCode screenshot workflow.
