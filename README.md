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
- Python 3.9 or newer.
- [`pngpaste`](https://github.com/jcs/pngpaste): `brew install pngpaste`.
- A remote Linux machine reachable with noninteractive SSH authentication.
- Remote OpenCode with image-path paste support. Zellij is the original tested
  multiplexer; it is not a dependency of the transfer helper.

## Install

```sh
# Homebrew
brew tap jameselkins/tap
brew trust jameselkins/tap     # Homebrew 7 requires trusting third-party taps
brew install remote-image-paste

# uv
uv tool install git+https://github.com/jameselkins/remote-image-paste

# pipx
pipx install git+https://github.com/jameselkins/remote-image-paste
```

All three install the same `remote-image-paste` command. The Homebrew formula
lives in [jameselkins/homebrew-tap](https://github.com/jameselkins/homebrew-tap)
and pulls the tagged release tarball.

Then set it up for your machine:

```sh
remote-image-paste --ssh-host devbox --title-contains 'devbox-work | '
```

This verifies SSH access, then installs the helper, AppleScript bridge, Service,
and configuration. Uninstall with `remote-image-paste --uninstall`, or
`brew uninstall remote-image-paste` if you installed with Homebrew.

**One manual step remains:** System Settings → Keyboard → Keyboard Shortcuts →
Services → enable **Remote Image Paste** and assign **Control-V**. macOS owns
keyboard shortcut registration, so it cannot be scripted. Disable any other
Service already using Control-V in Ghostty first.

Command-V keeps its normal Ghostty behavior.

## Configuration

`~/.config/remote-image-paste/config.json`, editable at any time:

```json
{
  "ssh_host": "devbox",
  "terminal_title_contains": "devbox-work | ",
  "remote_directory": "/tmp/remote-image-paste"
}
```

`ssh_host` accepts a plain SSH alias or `user@hostname`. Use `~/.ssh/config` for
ports, keys, and jump hosts. `--remote-directory` accepts an absolute path built
from letters, digits, `_`, `.`, `/`, and `-`; shell syntax, spaces, and parent
traversal are rejected.

**Choosing `terminal_title_contains`:** this decides which terminals get image
pasting, not where images go. Use a distinctive substring of your remote
terminal's title, such as `devbox-work | ` from a uniquely named Zellij session.
It is literal and case-sensitive. OpenCode can rewrite the pane title, so prefer a
stable Zellij session prefix. Avoid generic values like `main | ` that also match
a local session.

This tool cannot detect which remote program is running. Make sure the marker only
matches sessions on the configured host that are ready to accept an attachment.

## Manual use

```sh
remote-image-paste              # clipboard image; prints the remote path
remote-image-paste ./shot.jpg   # converts a local image to PNG first
```

Paste the printed path into remote OpenCode to attach it. Set
`REMOTE_IMAGE_PASTE_CONFIG` to use an alternative config file.

## How it works

```text
Control-V → Ghostty-only macOS Service → capture focused terminal ID and title
  ├─ title doesn't match → send original Control-V
  └─ title matches
      ├─ image → pngpaste → SSH mkdir → SCP unique PNG → input remote path
      └─ text  → input clipboard text once
```

The terminal is captured before the upload, so switching Ghostty tabs mid-upload
cannot redirect the paste. Installation writes a launcher that calls the
installed console script, so upgrades through any package manager keep working
without reinstalling the Service. Temporary local files are cleaned up on success
and failure. Uploaded files remain on the remote host until removed or `/tmp` is
cleared; there is no automatic remote cleanup.

Errors are reported with exit statuses rather than silent fallbacks:
`0` matched remote terminal, `1` failure, `2` no image in clipboard (paste text
instead), `3` not the configured remote terminal (send original Control-V).

## Troubleshooting

- **Nothing happens.** Run it from Ghostty → Services first. Check the shortcut
  and macOS Automation permission for Ghostty. `remote-image-paste` must be on
  the `PATH` your shell uses to launch the Service.
- **Local Ctrl-V behavior instead of an attachment.** The terminal title did not
  contain your marker. Check the live title in your remote OpenCode/Zellij session.
- **SSH failures.** `remote-image-paste` uses `BatchMode=yes` with a 10-second
  connection timeout, so it never waits on a password prompt. A stalled transfer
  can still take longer. Verify with
  `ssh -T -o BatchMode=yes devbox 'printf ready'`.
- **A path appears without an image attachment.** Confirm the terminal matches
  your configured host and that your OpenCode version recognizes pasted image paths.
- **Duplicate text.** Another Service or Ghostty keybinding is also handling Control-V.
- **Image lands in the wrong pane.** Don't switch the active Zellij pane during an
  upload. The Ghostty terminal ID identifies a terminal, not a Zellij pane.

## Uninstall

```sh
remote-image-paste --uninstall
```

Removes the helper and Service, and keeps your configuration. Remove the
shortcut in System Settings if still listed. To reinstall over a retained
config, delete `~/.config/remote-image-paste/config.json` first.

## Development

No third-party Python packages are needed to run the tests:

```sh
python3 -m unittest discover -s tests
```

Tests mock clipboard and SSH commands and install into a temporary home
directory, so they never touch your clipboard, shortcuts, installed Service, or
remote machine.

## Compatibility

**Verified:** a bracketed paste of a remote image path into OpenCode produces a
real `[Image N]` attachment. Tested against OpenCode 1.18.34 and Zellij 0.45.1 on
Linux, and separately with OpenCode driven directly in a pty. A real 3840x2160
image was uploaded over SSH to a live host, arriving with `0600` permissions
under a unique UUID filename. Install, launcher, Service plists, AppleScript
compilation, and uninstall were verified on macOS via `uv`. 30 tests pass.

**Not verified:** the macOS Services keyboard shortcut layer. Ghostty was not
running during testing, so the AppleScript that captures the focused terminal and
injects the remote path has not been exercised against a live Ghostty window.
Installing the Service and pressing Control-V still needs a manual check. Exact
macOS, Ghostty, Python, and OpenCode version compatibility is otherwise not
pinned. Other terminals, Windows/Linux clients, and other coding agents are
unsupported.

**Packaging verified:** the Homebrew formula passes `brew audit --strict`,
installs from the tagged tarball with checksum verification, passes `brew test`,
and retains the AppleScript resource inside its virtualenv. `uv tool install` was
verified in a sandbox `HOME`, covering install, launcher, Service plists,
AppleScript compilation, and uninstall.

Contributions with tested version combinations or improved terminal targeting are
welcome. Please include reproduction steps and redact private hostnames and keys.

## License

MIT. Built from a personal remote OpenCode screenshot workflow.