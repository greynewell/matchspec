"""Test Django test runner detection and command building."""

from mcpbr.evaluation import _build_test_command


class TestDjangoRunner:
    """Test Django test format detection and command building."""

    def test_django_format_with_parentheses(self):
        """Test Django format: test_method (module.TestClass)."""
        # This is the actual format used in Django SWE-bench instances
        test = "test_override_file_upload_permissions (test_utils.tests.OverrideSettingsTests)"
        cmd = _build_test_command(test, uses_prebuilt=False)

        # Should use Django test runner
        assert "cd /testbed/tests" in cmd
        assert "./runtests.py" in cmd
        assert "test_utils.tests" in cmd
        assert "pytest" not in cmd

    def test_django_format_with_parentheses_short_module(self):
        """Test Django format with single-part module name."""
        test = "test_method (admin.TestClass)"
        cmd = _build_test_command(test, uses_prebuilt=False)

        # Should still use Django runner, extracting 2 parts
        assert "cd /testbed/tests" in cmd
        assert "./runtests.py" in cmd
        # With only 2 parts, we get both
        assert "admin.TestClass" in cmd

    def test_django_format_with_parentheses_many_dots(self):
        """Test Django format with deeply nested module."""
        test = "test_method (django.contrib.admin.tests.TestClass)"
        cmd = _build_test_command(test, uses_prebuilt=False)

        # Should extract first 2 parts only
        assert "cd /testbed/tests" in cmd
        assert "./runtests.py" in cmd
        assert "django.contrib" in cmd

    def test_django_format_detection(self):
        """Test that Django dot-separated test format is detected."""
        # Django test format: module.tests.TestClass.test_method
        test = "test_utils.tests.TestClass.test_method"
        cmd = _build_test_command(test, uses_prebuilt=False)

        # Should use Django test runner
        assert "cd /testbed/tests" in cmd
        assert "./runtests.py" in cmd
        assert "test_utils.tests" in cmd
        assert "pytest" not in cmd

    def test_django_short_format(self):
        """Test Django format with just module.tests."""
        test = "test_utils.tests"
        cmd = _build_test_command(test, uses_prebuilt=False)

        assert "cd /testbed/tests" in cmd
        assert "./runtests.py" in cmd
        assert "test_utils.tests" in cmd

    def test_pytest_format_with_double_colon(self):
        """Test that pytest format with :: is not treated as Django."""
        test = "tests/test_file.py::TestClass::test_method"
        cmd = _build_test_command(test, uses_prebuilt=False)

        # Should use pytest
        assert "python -m pytest" in cmd
        assert "runtests.py" not in cmd

    def test_pytest_format_with_py_file(self):
        """Test that .py files use pytest."""
        test = "tests/test_file.py"
        cmd = _build_test_command(test, uses_prebuilt=False)

        assert "python -m pytest" in cmd
        assert "runtests.py" not in cmd

    def test_pytest_format_with_k_flag(self):
        """Test that test names without dots use pytest -k."""
        test = "test_method_name"
        cmd = _build_test_command(test, uses_prebuilt=False)

        assert "python -m pytest -k" in cmd
        assert "runtests.py" not in cmd

    def test_prebuilt_environment_activation(self):
        """Test that prebuilt environments include conda activation."""
        test = "test_utils.tests.TestClass"
        cmd = _build_test_command(test, uses_prebuilt=True)

        assert "source /opt/miniconda3/etc/profile.d/conda.sh" in cmd
        assert "conda activate testbed" in cmd
        assert "./runtests.py" in cmd

    def test_path_not_treated_as_django(self):
        """Test that paths starting with / are not treated as Django format."""
        test = "/testbed/tests/test_file.py"
        cmd = _build_test_command(test, uses_prebuilt=False)

        # Should use pytest since it's a path
        assert "python -m pytest" in cmd
        assert "runtests.py" not in cmd
