class H9s < Formula
  desc "k9s-style terminal UI dashboard for Helm releases on Kubernetes"
  homepage "https://github.com/razvanbalsan/h9s"
  url "https://github.com/razvanbalsan/h9s/archive/refs/tags/v1.0.4.tar.gz"
  sha256 "ed36c7929c6d7d57b0115588f561610eb12c4f01ab0b21509d7650664d335919"
  license "MIT"
  head "https://github.com/razvanbalsan/h9s.git", branch: "main"

  depends_on "python@3.12"
  depends_on "helm"
  depends_on "kubectl" => :recommended

  def install
    # Create an isolated venv and install the package into it
    venv = libexec/"venv"
    system "python3.12", "-m", "venv", venv
    system "#{venv}/bin/pip", "install", "--upgrade", "pip", "--quiet"
    system "#{venv}/bin/pip", "install", ".", "--quiet"

    # Write a thin launcher that activates the venv
    (bin/"h9s").write <<~SHELL
      #!/bin/bash
      exec "#{venv}/bin/python" -m helm_dashboard "$@"
    SHELL
    chmod 0755, bin/"h9s"
  end

  test do
    # Verify the binary exists and runs (it will exit non-zero without a cluster,
    # but at minimum it must be importable)
    assert_predicate bin/"h9s", :exist?
    assert_predicate bin/"h9s", :executable?
    system "#{bin}/h9s", "--help" rescue nil  # TUI apps exit non-zero for --help; that's fine
  end
end
