class RemoteImagePaste < Formula
  include Language::Python::Virtualenv

  desc "Paste clipboard images into remote OpenCode sessions over SSH from macOS Ghostty"
  homepage "https://github.com/jameselkins/remote-image-paste"
  url "https://github.com/jameselkins/remote-image-paste/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "37bf597af375e283b64fb4c57e38e230562207cc0b39b766f1ef60f413e87378"
  license "MIT"
  head "https://github.com/jameselkins/remote-image-paste.git", branch: "main"

  depends_on "pngpaste"
  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources using: "python@3.13"
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
    # --version proves the console script and its virtualenv wrapper work.
    assert_match version.to_s, shell_output("#{bin}/remote-image-paste --version")
    # A missing config must fail cleanly rather than traceback or hang.
    assert_match "failed", shell_output("#{bin}/remote-image-paste --matches-title anything 2>&1", 1)
  end
end
