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
# uv
uv tool install remote-image-paste

# pipx
pipx install remote-image-paste
```

No Homebrew tap exists yet. A formula is provided in
[`homebrew/remote-image-paste.rb`](homebrew/remote-image-paste.rb) for anyone who
wants to package it, but `brew install` is not currently advertised as supported.

Both package managers above install from GitHub and produce the same
`remote-image-paste` command. `brew install .` works from a local clone too.

Then set it up for your machine:

```sh
remote-image-paste --ssh-host devbox --title-contains 'devbox-work | '
```

This verifies SSH access, then installs the helper, AppleScript bridge, Service,
and configuration. Uninstall with `remote-image-paste --uninstall`.

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

**Compatibility:** the original personal integration was verified end to end
through Ghostty, SSH, Zellij, and OpenCode, including multiple image attachments,
text fallback, and duplicate-paste fixes. This packaged version has automated
tests, and install, launch, configuration, Service plists, and AppleScript
compilation were verified on macOS with `uv`. It has **not** been verified end to
end against a live remote host or a second machine, and exact Ghostty, macOS,
OpenCode, and Python version compatibility is not established. Other terminals,
Windows/Linux clients, and other coding agents are unsupported.

Contributions with tested version combinations or improved terminal targeting are
welcome. Please include reproduction steps and redact private hostnames and keys.

## License

MIT. Built from a personal remote OpenCode screenshot workflow.