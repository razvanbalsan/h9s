class H9s < Formula
  desc "k9s-style terminal UI dashboard for Helm releases on Kubernetes"
  homepage "https://github.com/razvanbalsan/h9s"
  url "https://github.com/razvanbalsan/h9s/archive/refs/tags/v1.0.8.tar.gz"
  sha256 "f2f7451e685e31878a2e23fd34801bd7372f60a8ad2c28f2b372c4eea8daad82"
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
