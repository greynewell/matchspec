class Mcpbr < Formula
  include Language::Python::Virtualenv

  desc "Model Context Protocol Benchmark Runner - evaluate MCP servers against software engineering benchmarks"
  homepage "https://github.com/greynewell/mcpbr"
  url "https://files.pythonhosted.org/packages/source/m/mcpbr/mcpbr-0.6.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "python@3.11"

  resource "anthropic" do
    url "https://files.pythonhosted.org/packages/source/a/anthropic/anthropic-0.40.0.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.1.7.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "docker" do
    url "https://files.pythonhosted.org/packages/source/d/docker/docker-7.0.0.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic/pydantic-2.0.0.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/p/PyYAML/PyYAML-6.0.1.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.0.0.tar.gz"
    sha256 "PLACEHOLDER_SHA256"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "mcpbr", shell_output("#{bin}/mcpbr --version")
  end
end
