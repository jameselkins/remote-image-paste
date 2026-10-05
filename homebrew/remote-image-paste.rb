class RemoteImagePaste < Formula
  include Language::Python::Virtualenv

  desc "Paste clipboard images into remote OpenCode sessions over SSH from macOS Ghostty"
  homepage "https://github.com/jameselkins/remote-image-paste"
  url "https://github.com/jameselkins/remote-image-paste/archive/refs/tags/v0.2.0.tar.gz"
  version "0.2.0"
  license "MIT"
  head "https://github.com/jameselkins/remote-image-paste.git", branch: "main"

  depends_on "pngpaste"

  def install
    virtualenv_install_with_resources
  end

  # Uploads need pngpaste, but the Service runs from a login-free context that
  # does not inherit Homebrew's PATH, so the formula's bin directory is baked
  # into the wrapper at install time.
  def caveats
    <<~EOS
      Set up the Ghostty keyboard shortcut:
        System Settings > Keyboard > Keyboard Shortcuts > Services
        Enable "Remote Image Paste" and assign Control-V.

      Uploads use an SSH alias from ~/.ssh/config:
        remote-image-paste --ssh-host devbox --title-contains 'devbox-work | '
    EOS
  end

  test do
    assert_match "requires macOS", shell_output("#{bin}/remote-image-paste --matches-title x 2>&1", 1)
  end
end