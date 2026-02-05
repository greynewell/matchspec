"""Tests for infrastructure and platform distribution files.

Validates that all Docker, GitHub Action, CI template, packaging, and
distribution files exist and contain the required structure and fields.
"""

import re
from pathlib import Path

import pytest
import yaml

# Project root relative to test file
PROJECT_ROOT = Path(__file__).parent.parent


class TestDockerApp:
    """Tests for the Dockerfile.app multi-stage build."""

    @pytest.fixture
    def dockerfile_path(self) -> Path:
        return PROJECT_ROOT / "Dockerfile.app"

    @pytest.fixture
    def dockerfile_content(self, dockerfile_path: Path) -> str:
        return dockerfile_path.read_text()

    def test_dockerfile_app_exists(self, dockerfile_path: Path) -> None:
        """Dockerfile.app must exist in the project root."""
        assert dockerfile_path.exists(), "Dockerfile.app should exist"

    def test_dockerfile_app_has_from(self, dockerfile_content: str) -> None:
        """Dockerfile.app must have a FROM instruction."""
        assert "FROM" in dockerfile_content, "Dockerfile.app should have FROM instruction"

    def test_dockerfile_app_has_workdir(self, dockerfile_content: str) -> None:
        """Dockerfile.app must have a WORKDIR instruction."""
        assert "WORKDIR" in dockerfile_content, "Dockerfile.app should have WORKDIR instruction"

    def test_dockerfile_app_has_entrypoint(self, dockerfile_content: str) -> None:
        """Dockerfile.app must have an ENTRYPOINT instruction."""
        assert "ENTRYPOINT" in dockerfile_content, (
            "Dockerfile.app should have ENTRYPOINT instruction"
        )

    def test_dockerfile_app_is_multistage(self, dockerfile_content: str) -> None:
        """Dockerfile.app must use multi-stage build (multiple FROM)."""
        from_count = len(re.findall(r"^FROM\s", dockerfile_content, re.MULTILINE))
        assert from_count >= 2, f"Expected multi-stage build (>=2 FROM), got {from_count}"

    def test_dockerfile_app_uses_python_base(self, dockerfile_content: str) -> None:
        """Dockerfile.app must use a Python base image."""
        assert "python:" in dockerfile_content.lower(), (
            "Dockerfile.app should use a Python base image"
        )

    def test_dockerfile_app_installs_mcpbr(self, dockerfile_content: str) -> None:
        """Dockerfile.app must install the mcpbr package."""
        assert "pip install" in dockerfile_content or ".whl" in dockerfile_content, (
            "Dockerfile.app should install mcpbr"
        )

    def test_dockerfile_app_has_labels(self, dockerfile_content: str) -> None:
        """Dockerfile.app should have OCI labels."""
        assert "LABEL" in dockerfile_content, "Dockerfile.app should have LABEL instructions"


class TestDockerEntrypoint:
    """Tests for the Docker entrypoint script."""

    @pytest.fixture
    def entrypoint_path(self) -> Path:
        return PROJECT_ROOT / "docker" / "entrypoint.sh"

    @pytest.fixture
    def entrypoint_content(self, entrypoint_path: Path) -> str:
        return entrypoint_path.read_text()

    def test_entrypoint_exists(self, entrypoint_path: Path) -> None:
        """docker/entrypoint.sh must exist."""
        assert entrypoint_path.exists(), "docker/entrypoint.sh should exist"

    def test_entrypoint_has_shebang(self, entrypoint_content: str) -> None:
        """Entrypoint must start with a shebang line."""
        assert entrypoint_content.startswith("#!/"), "entrypoint.sh should have a shebang"

    def test_entrypoint_references_mcpbr(self, entrypoint_content: str) -> None:
        """Entrypoint must reference the mcpbr command."""
        assert "mcpbr" in entrypoint_content, "entrypoint.sh should reference mcpbr"

    def test_entrypoint_uses_exec(self, entrypoint_content: str) -> None:
        """Entrypoint should use exec for proper signal handling."""
        assert "exec" in entrypoint_content, "entrypoint.sh should use exec"


class TestDockerCompose:
    """Tests for docker-compose.yml."""

    @pytest.fixture
    def compose_path(self) -> Path:
        return PROJECT_ROOT / "docker" / "docker-compose.yml"

    @pytest.fixture
    def compose_data(self, compose_path: Path) -> dict:
        return yaml.safe_load(compose_path.read_text())

    def test_compose_exists(self, compose_path: Path) -> None:
        """docker/docker-compose.yml must exist."""
        assert compose_path.exists(), "docker/docker-compose.yml should exist"

    def test_compose_is_valid_yaml(self, compose_data: dict) -> None:
        """docker-compose.yml must be valid YAML."""
        assert isinstance(compose_data, dict), "docker-compose.yml should parse to a dict"

    def test_compose_has_services(self, compose_data: dict) -> None:
        """docker-compose.yml must define services."""
        assert "services" in compose_data, "docker-compose.yml should have services"

    def test_compose_has_mcpbr_service(self, compose_data: dict) -> None:
        """docker-compose.yml must have a mcpbr service."""
        assert "mcpbr" in compose_data["services"], "docker-compose.yml should have mcpbr service"


class TestDockerIgnore:
    """Tests for .dockerignore."""

    @pytest.fixture
    def dockerignore_path(self) -> Path:
        return PROJECT_ROOT / ".dockerignore"

    @pytest.fixture
    def dockerignore_content(self, dockerignore_path: Path) -> str:
        return dockerignore_path.read_text()

    def test_dockerignore_exists(self, dockerignore_path: Path) -> None:
        """.dockerignore must exist."""
        assert dockerignore_path.exists(), ".dockerignore should exist"

    def test_dockerignore_excludes_git(self, dockerignore_content: str) -> None:
        """.dockerignore must exclude .git."""
        assert ".git" in dockerignore_content, ".dockerignore should exclude .git"

    def test_dockerignore_excludes_venv(self, dockerignore_content: str) -> None:
        """.dockerignore must exclude virtual environments."""
        assert ".venv" in dockerignore_content or "venv" in dockerignore_content, (
            ".dockerignore should exclude venv"
        )

    def test_dockerignore_excludes_pycache(self, dockerignore_content: str) -> None:
        """.dockerignore must exclude __pycache__."""
        assert "__pycache__" in dockerignore_content, ".dockerignore should exclude __pycache__"


class TestDockerReadme:
    """Tests for docker/README.md."""

    def test_docker_readme_exists(self) -> None:
        """docker/README.md must exist."""
        path = PROJECT_ROOT / "docker" / "README.md"
        assert path.exists(), "docker/README.md should exist"

    def test_docker_readme_not_empty(self) -> None:
        """docker/README.md must not be empty."""
        path = PROJECT_ROOT / "docker" / "README.md"
        content = path.read_text()
        assert len(content) > 100, "docker/README.md should have substantial content"


class TestGitHubAction:
    """Tests for the GitHub Action composite action."""

    @pytest.fixture
    def action_path(self) -> Path:
        return PROJECT_ROOT / "action" / "action.yml"

    @pytest.fixture
    def action_data(self, action_path: Path) -> dict:
        return yaml.safe_load(action_path.read_text())

    def test_action_yml_exists(self, action_path: Path) -> None:
        """action/action.yml must exist."""
        assert action_path.exists(), "action/action.yml should exist"

    def test_action_yml_is_valid_yaml(self, action_data: dict) -> None:
        """action.yml must be valid YAML."""
        assert isinstance(action_data, dict), "action.yml should parse to a dict"

    def test_action_yml_has_name(self, action_data: dict) -> None:
        """action.yml must have a name field."""
        assert "name" in action_data, "action.yml should have 'name'"

    def test_action_yml_has_description(self, action_data: dict) -> None:
        """action.yml must have a description field."""
        assert "description" in action_data, "action.yml should have 'description'"

    def test_action_yml_has_inputs(self, action_data: dict) -> None:
        """action.yml must have inputs."""
        assert "inputs" in action_data, "action.yml should have 'inputs'"
        assert isinstance(action_data["inputs"], dict), "inputs should be a dict"

    def test_action_yml_has_runs(self, action_data: dict) -> None:
        """action.yml must have runs section."""
        assert "runs" in action_data, "action.yml should have 'runs'"

    def test_action_yml_is_composite(self, action_data: dict) -> None:
        """action.yml must use composite runs."""
        assert action_data["runs"]["using"] == "composite", "action should use composite runs"

    def test_action_yml_has_config_input(self, action_data: dict) -> None:
        """action.yml must have a config input."""
        assert "config" in action_data["inputs"], "action.yml should have 'config' input"
        assert action_data["inputs"]["config"]["required"] is True, (
            "config input should be required"
        )

    def test_action_yml_has_outputs(self, action_data: dict) -> None:
        """action.yml must have outputs."""
        assert "outputs" in action_data, "action.yml should have 'outputs'"

    def test_action_yml_has_steps(self, action_data: dict) -> None:
        """action.yml runs must have steps."""
        assert "steps" in action_data["runs"], "action.yml runs should have 'steps'"
        assert len(action_data["runs"]["steps"]) >= 2, "action should have at least 2 steps"


class TestActionExamples:
    """Tests for the GitHub Action example workflows."""

    def test_basic_example_exists(self) -> None:
        """action/examples/basic.yml must exist."""
        path = PROJECT_ROOT / "action" / "examples" / "basic.yml"
        assert path.exists(), "action/examples/basic.yml should exist"

    def test_basic_example_is_valid_yaml(self) -> None:
        """action/examples/basic.yml must be valid YAML."""
        path = PROJECT_ROOT / "action" / "examples" / "basic.yml"
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict), "basic.yml should parse to a dict"

    def test_matrix_example_exists(self) -> None:
        """action/examples/matrix.yml must exist."""
        path = PROJECT_ROOT / "action" / "examples" / "matrix.yml"
        assert path.exists(), "action/examples/matrix.yml should exist"

    def test_matrix_example_is_valid_yaml(self) -> None:
        """action/examples/matrix.yml must be valid YAML."""
        path = PROJECT_ROOT / "action" / "examples" / "matrix.yml"
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict), "matrix.yml should parse to a dict"

    def test_matrix_example_has_strategy(self) -> None:
        """matrix.yml must use strategy.matrix."""
        path = PROJECT_ROOT / "action" / "examples" / "matrix.yml"
        data = yaml.safe_load(path.read_text())
        # Look for strategy.matrix in any job
        jobs = data.get("jobs", {})
        has_matrix = any(
            "strategy" in job and "matrix" in job["strategy"]
            for job in jobs.values()
            if isinstance(job, dict)
        )
        assert has_matrix, "matrix.yml should have strategy.matrix in at least one job"


class TestActionReadme:
    """Tests for action/README.md."""

    def test_action_readme_exists(self) -> None:
        """action/README.md must exist."""
        path = PROJECT_ROOT / "action" / "README.md"
        assert path.exists(), "action/README.md should exist"


class TestBuildBinaries:
    """Tests for the build-binaries workflow."""

    @pytest.fixture
    def workflow_path(self) -> Path:
        return PROJECT_ROOT / ".github" / "workflows" / "build-binaries.yml"

    @pytest.fixture
    def workflow_data(self, workflow_path: Path) -> dict:
        return yaml.safe_load(workflow_path.read_text())

    def test_build_binaries_exists(self, workflow_path: Path) -> None:
        """build-binaries.yml must exist."""
        assert workflow_path.exists(), "build-binaries.yml should exist"

    def test_build_binaries_is_valid_yaml(self, workflow_data: dict) -> None:
        """build-binaries.yml must be valid YAML."""
        assert isinstance(workflow_data, dict), "build-binaries.yml should parse to a dict"

    def test_build_binaries_has_strategy_matrix(self, workflow_data: dict) -> None:
        """build-binaries.yml must have strategy.matrix for cross-platform builds."""
        jobs = workflow_data.get("jobs", {})
        has_matrix = any(
            "strategy" in job and "matrix" in job["strategy"]
            for job in jobs.values()
            if isinstance(job, dict)
        )
        assert has_matrix, "build-binaries.yml should have strategy.matrix"

    def test_build_binaries_has_multiple_platforms(self, workflow_data: dict) -> None:
        """build-binaries.yml must target multiple platforms."""
        jobs = workflow_data.get("jobs", {})
        for job in jobs.values():
            if isinstance(job, dict) and "strategy" in job:
                matrix = job["strategy"].get("matrix", {})
                # Check for include-style or os-style matrix
                includes = matrix.get("include", [])
                os_list = matrix.get("os", [])
                total = len(includes) + len(os_list)
                if total >= 2:
                    return
        pytest.fail("build-binaries.yml should target at least 2 platforms")

    def test_build_binaries_triggers_on_release(self, workflow_data: dict) -> None:
        """build-binaries.yml must trigger on release events."""
        on_config = workflow_data.get("on", workflow_data.get(True, {}))
        assert "release" in on_config, "build-binaries.yml should trigger on release"

    def test_build_binaries_uses_pyinstaller(self, workflow_path: Path) -> None:
        """build-binaries.yml must use PyInstaller."""
        content = workflow_path.read_text()
        assert "pyinstaller" in content.lower(), "build-binaries.yml should use PyInstaller"


class TestPyInstallerSpec:
    """Tests for the PyInstaller spec file."""

    @pytest.fixture
    def spec_path(self) -> Path:
        return PROJECT_ROOT / "mcpbr.spec"

    @pytest.fixture
    def spec_content(self, spec_path: Path) -> str:
        return spec_path.read_text()

    def test_spec_exists(self, spec_path: Path) -> None:
        """mcpbr.spec must exist."""
        assert spec_path.exists(), "mcpbr.spec should exist"

    def test_spec_has_analysis(self, spec_content: str) -> None:
        """mcpbr.spec must have an Analysis section."""
        assert "Analysis(" in spec_content, "mcpbr.spec should have Analysis"

    def test_spec_has_exe(self, spec_content: str) -> None:
        """mcpbr.spec must have an EXE section."""
        assert "EXE(" in spec_content, "mcpbr.spec should have EXE"

    def test_spec_has_pyz(self, spec_content: str) -> None:
        """mcpbr.spec must have a PYZ section."""
        assert "PYZ(" in spec_content, "mcpbr.spec should have PYZ"

    def test_spec_names_binary_mcpbr(self, spec_content: str) -> None:
        """mcpbr.spec should name the output binary 'mcpbr'."""
        assert 'name="mcpbr"' in spec_content, "spec should name binary 'mcpbr'"

    def test_spec_includes_hidden_imports(self, spec_content: str) -> None:
        """mcpbr.spec must list hidden imports."""
        assert "hiddenimports" in spec_content, "spec should have hiddenimports"

    def test_spec_references_main(self, spec_content: str) -> None:
        """mcpbr.spec should reference the __main__.py entry point."""
        assert "__main__.py" in spec_content, "spec should reference __main__.py"


class TestHomebrewFormula:
    """Tests for the Homebrew formula."""

    @pytest.fixture
    def formula_path(self) -> Path:
        return PROJECT_ROOT / "Formula" / "mcpbr.rb"

    @pytest.fixture
    def formula_content(self, formula_path: Path) -> str:
        return formula_path.read_text()

    def test_formula_exists(self, formula_path: Path) -> None:
        """Formula/mcpbr.rb must exist."""
        assert formula_path.exists(), "Formula/mcpbr.rb should exist"

    def test_formula_has_class(self, formula_content: str) -> None:
        """Formula must define a Mcpbr class inheriting from Formula."""
        assert "class Mcpbr < Formula" in formula_content, (
            "Formula should have 'class Mcpbr < Formula'"
        )

    def test_formula_has_desc(self, formula_content: str) -> None:
        """Formula must have a desc field."""
        assert 'desc "' in formula_content, "Formula should have 'desc'"

    def test_formula_has_homepage(self, formula_content: str) -> None:
        """Formula must have a homepage field."""
        assert 'homepage "' in formula_content, "Formula should have 'homepage'"

    def test_formula_has_url(self, formula_content: str) -> None:
        """Formula must have a url field."""
        assert 'url "' in formula_content, "Formula should have 'url'"

    def test_formula_has_sha256(self, formula_content: str) -> None:
        """Formula must have a sha256 field (even as placeholder)."""
        assert "sha256" in formula_content, "Formula should have 'sha256'"

    def test_formula_has_license(self, formula_content: str) -> None:
        """Formula must have a license field."""
        assert 'license "' in formula_content, "Formula should have 'license'"

    def test_formula_has_depends_on_python(self, formula_content: str) -> None:
        """Formula must depend on Python."""
        assert 'depends_on "python' in formula_content, "Formula should depend on Python"

    def test_formula_has_install_method(self, formula_content: str) -> None:
        """Formula must have a def install block."""
        assert "def install" in formula_content, "Formula should have 'def install'"

    def test_formula_has_test_block(self, formula_content: str) -> None:
        """Formula must have a test block."""
        assert "test do" in formula_content, "Formula should have 'test do'"

    def test_formula_has_resources(self, formula_content: str) -> None:
        """Formula should have resource blocks for dependencies."""
        assert "resource " in formula_content, "Formula should have resource blocks"


class TestHomebrewReadme:
    """Tests for homebrew/README.md."""

    def test_homebrew_readme_exists(self) -> None:
        """homebrew/README.md must exist."""
        path = PROJECT_ROOT / "homebrew" / "README.md"
        assert path.exists(), "homebrew/README.md should exist"


class TestGitLabCI:
    """Tests for the GitLab CI template."""

    @pytest.fixture
    def gitlab_path(self) -> Path:
        return PROJECT_ROOT / "ci-templates" / "gitlab" / ".gitlab-ci-mcpbr.yml"

    @pytest.fixture
    def gitlab_data(self, gitlab_path: Path) -> dict:
        return yaml.safe_load(gitlab_path.read_text())

    def test_gitlab_ci_exists(self, gitlab_path: Path) -> None:
        """.gitlab-ci-mcpbr.yml must exist."""
        assert gitlab_path.exists(), ".gitlab-ci-mcpbr.yml should exist"

    def test_gitlab_ci_is_valid_yaml(self, gitlab_data: dict) -> None:
        """.gitlab-ci-mcpbr.yml must be valid YAML."""
        assert isinstance(gitlab_data, dict), ".gitlab-ci-mcpbr.yml should parse to a dict"

    def test_gitlab_ci_has_stages(self, gitlab_data: dict) -> None:
        """.gitlab-ci-mcpbr.yml must define stages."""
        assert "stages" in gitlab_data, ".gitlab-ci-mcpbr.yml should have 'stages'"
        assert isinstance(gitlab_data["stages"], list), "stages should be a list"
        assert len(gitlab_data["stages"]) >= 2, "should have at least 2 stages"

    def test_gitlab_ci_has_variables(self, gitlab_data: dict) -> None:
        """.gitlab-ci-mcpbr.yml must define configurable variables."""
        assert "variables" in gitlab_data, ".gitlab-ci-mcpbr.yml should have 'variables'"

    def test_gitlab_ci_has_benchmark_job(self, gitlab_data: dict) -> None:
        """.gitlab-ci-mcpbr.yml must have a benchmark job."""
        assert "mcpbr_benchmark" in gitlab_data, (
            ".gitlab-ci-mcpbr.yml should have 'mcpbr_benchmark' job"
        )

    def test_gitlab_ci_has_base_template(self, gitlab_data: dict) -> None:
        """.gitlab-ci-mcpbr.yml must define a base template."""
        assert ".mcpbr_base" in gitlab_data, ".gitlab-ci-mcpbr.yml should have '.mcpbr_base'"

    def test_gitlab_ci_has_artifacts(self, gitlab_data: dict) -> None:
        """.gitlab-ci-mcpbr.yml benchmark job must have artifacts."""
        benchmark = gitlab_data.get("mcpbr_benchmark", {})
        assert "artifacts" in benchmark, "mcpbr_benchmark should have artifacts"


class TestGitLabReadme:
    """Tests for ci-templates/gitlab/README.md."""

    def test_gitlab_readme_exists(self) -> None:
        """ci-templates/gitlab/README.md must exist."""
        path = PROJECT_ROOT / "ci-templates" / "gitlab" / "README.md"
        assert path.exists(), "ci-templates/gitlab/README.md should exist"


class TestCondaPackage:
    """Tests for the conda package files."""

    @pytest.fixture
    def meta_path(self) -> Path:
        return PROJECT_ROOT / "conda" / "meta.yaml"

    @pytest.fixture
    def meta_content(self, meta_path: Path) -> str:
        return meta_path.read_text()

    def test_meta_yaml_exists(self, meta_path: Path) -> None:
        """conda/meta.yaml must exist."""
        assert meta_path.exists(), "conda/meta.yaml should exist"

    def test_meta_yaml_has_package_section(self, meta_content: str) -> None:
        """meta.yaml must have a package section."""
        assert "package:" in meta_content, "meta.yaml should have 'package:' section"

    def test_meta_yaml_has_source_section(self, meta_content: str) -> None:
        """meta.yaml must have a source section."""
        assert "source:" in meta_content, "meta.yaml should have 'source:' section"

    def test_meta_yaml_has_build_section(self, meta_content: str) -> None:
        """meta.yaml must have a build section."""
        assert "build:" in meta_content, "meta.yaml should have 'build:' section"

    def test_meta_yaml_has_requirements_section(self, meta_content: str) -> None:
        """meta.yaml must have a requirements section."""
        assert "requirements:" in meta_content, "meta.yaml should have 'requirements:' section"

    def test_meta_yaml_has_host_requirements(self, meta_content: str) -> None:
        """meta.yaml must have host requirements."""
        assert "host:" in meta_content, "meta.yaml should have 'host:' under requirements"

    def test_meta_yaml_has_run_requirements(self, meta_content: str) -> None:
        """meta.yaml must have run requirements."""
        assert "run:" in meta_content, "meta.yaml should have 'run:' under requirements"

    def test_meta_yaml_has_about_section(self, meta_content: str) -> None:
        """meta.yaml must have an about section."""
        assert "about:" in meta_content, "meta.yaml should have 'about:' section"

    def test_meta_yaml_has_test_section(self, meta_content: str) -> None:
        """meta.yaml must have a test section."""
        assert "test:" in meta_content, "meta.yaml should have 'test:' section"

    def test_meta_yaml_references_mcpbr(self, meta_content: str) -> None:
        """meta.yaml must reference mcpbr package."""
        assert "mcpbr" in meta_content, "meta.yaml should reference mcpbr"

    def test_meta_yaml_has_entry_points(self, meta_content: str) -> None:
        """meta.yaml must define entry points."""
        assert "entry_points" in meta_content, "meta.yaml should have entry_points"

    def test_build_sh_exists(self) -> None:
        """conda/build.sh must exist."""
        path = PROJECT_ROOT / "conda" / "build.sh"
        assert path.exists(), "conda/build.sh should exist"

    def test_bld_bat_exists(self) -> None:
        """conda/bld.bat must exist."""
        path = PROJECT_ROOT / "conda" / "bld.bat"
        assert path.exists(), "conda/bld.bat should exist"

    def test_build_sh_uses_pip(self) -> None:
        """conda/build.sh must use pip install."""
        path = PROJECT_ROOT / "conda" / "build.sh"
        content = path.read_text()
        assert "pip install" in content, "build.sh should use pip install"

    def test_bld_bat_uses_pip(self) -> None:
        """conda/bld.bat must use pip install."""
        path = PROJECT_ROOT / "conda" / "bld.bat"
        content = path.read_text()
        assert "pip install" in content, "bld.bat should use pip install"


class TestCondaReadme:
    """Tests for conda/README.md."""

    def test_conda_readme_exists(self) -> None:
        """conda/README.md must exist."""
        path = PROJECT_ROOT / "conda" / "README.md"
        assert path.exists(), "conda/README.md should exist"


class TestCircleCIOrb:
    """Tests for the CircleCI orb."""

    @pytest.fixture
    def orb_path(self) -> Path:
        return PROJECT_ROOT / "ci-templates" / "circleci" / "orb.yml"

    @pytest.fixture
    def orb_data(self, orb_path: Path) -> dict:
        return yaml.safe_load(orb_path.read_text())

    def test_orb_yml_exists(self, orb_path: Path) -> None:
        """orb.yml must exist."""
        assert orb_path.exists(), "orb.yml should exist"

    def test_orb_yml_is_valid_yaml(self, orb_data: dict) -> None:
        """orb.yml must be valid YAML."""
        assert isinstance(orb_data, dict), "orb.yml should parse to a dict"

    def test_orb_yml_has_version(self, orb_data: dict) -> None:
        """orb.yml must have a version field."""
        assert "version" in orb_data, "orb.yml should have 'version'"

    def test_orb_yml_has_commands(self, orb_data: dict) -> None:
        """orb.yml must have commands."""
        assert "commands" in orb_data, "orb.yml should have 'commands'"
        assert isinstance(orb_data["commands"], dict), "commands should be a dict"

    def test_orb_yml_has_jobs(self, orb_data: dict) -> None:
        """orb.yml must have jobs."""
        assert "jobs" in orb_data, "orb.yml should have 'jobs'"
        assert isinstance(orb_data["jobs"], dict), "jobs should be a dict"

    def test_orb_yml_has_install_command(self, orb_data: dict) -> None:
        """orb.yml must have an install command."""
        assert "install" in orb_data["commands"], "orb.yml should have 'install' command"

    def test_orb_yml_has_run_benchmark_command(self, orb_data: dict) -> None:
        """orb.yml must have a run-benchmark command."""
        assert "run-benchmark" in orb_data["commands"], (
            "orb.yml should have 'run-benchmark' command"
        )

    def test_orb_yml_has_benchmark_job(self, orb_data: dict) -> None:
        """orb.yml must have a benchmark job."""
        assert "benchmark" in orb_data["jobs"], "orb.yml should have 'benchmark' job"

    def test_orb_yml_has_executors(self, orb_data: dict) -> None:
        """orb.yml must have executors."""
        assert "executors" in orb_data, "orb.yml should have 'executors'"

    def test_orb_yml_has_description(self, orb_data: dict) -> None:
        """orb.yml must have a description."""
        assert "description" in orb_data, "orb.yml should have 'description'"

    def test_orb_yml_has_examples(self, orb_data: dict) -> None:
        """orb.yml must have examples."""
        assert "examples" in orb_data, "orb.yml should have 'examples'"


class TestCircleCIReadme:
    """Tests for ci-templates/circleci/README.md."""

    def test_circleci_readme_exists(self) -> None:
        """ci-templates/circleci/README.md must exist."""
        path = PROJECT_ROOT / "ci-templates" / "circleci" / "README.md"
        assert path.exists(), "ci-templates/circleci/README.md should exist"


class TestAllFilesExist:
    """Meta-test: Ensure all expected infrastructure files exist."""

    EXPECTED_FILES = [
        "Dockerfile.app",
        "docker/entrypoint.sh",
        "docker/docker-compose.yml",
        "docker/README.md",
        ".dockerignore",
        "action/action.yml",
        "action/examples/basic.yml",
        "action/examples/matrix.yml",
        "action/README.md",
        ".github/workflows/build-binaries.yml",
        "mcpbr.spec",
        "Formula/mcpbr.rb",
        "homebrew/README.md",
        "ci-templates/gitlab/.gitlab-ci-mcpbr.yml",
        "ci-templates/gitlab/README.md",
        "conda/meta.yaml",
        "conda/build.sh",
        "conda/bld.bat",
        "conda/README.md",
        "ci-templates/circleci/orb.yml",
        "ci-templates/circleci/README.md",
    ]

    @pytest.mark.parametrize("rel_path", EXPECTED_FILES)
    def test_file_exists(self, rel_path: str) -> None:
        """Each infrastructure file must exist."""
        path = PROJECT_ROOT / rel_path
        assert path.exists(), f"{rel_path} should exist"

    @pytest.mark.parametrize("rel_path", EXPECTED_FILES)
    def test_file_not_empty(self, rel_path: str) -> None:
        """Each infrastructure file must not be empty."""
        path = PROJECT_ROOT / rel_path
        content = path.read_text()
        assert len(content.strip()) > 0, f"{rel_path} should not be empty"


class TestYamlFilesValid:
    """Validate all YAML infrastructure files can be parsed."""

    YAML_FILES = [
        "docker/docker-compose.yml",
        "action/action.yml",
        "action/examples/basic.yml",
        "action/examples/matrix.yml",
        ".github/workflows/build-binaries.yml",
        "ci-templates/gitlab/.gitlab-ci-mcpbr.yml",
        "ci-templates/circleci/orb.yml",
    ]

    @pytest.mark.parametrize("rel_path", YAML_FILES)
    def test_yaml_is_valid(self, rel_path: str) -> None:
        """YAML file must be parseable."""
        path = PROJECT_ROOT / rel_path
        content = path.read_text()
        data = yaml.safe_load(content)
        assert data is not None, f"{rel_path} should parse to non-None"
        assert isinstance(data, dict), f"{rel_path} should parse to a dict"
