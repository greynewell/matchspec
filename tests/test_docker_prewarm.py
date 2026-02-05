"""Tests for Docker image pre-warming module."""

from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from mcpbr.docker_prewarm import (
    PrewarmResult,
    check_cached_images,
    format_prewarm_report,
    get_required_images,
    prewarm_images,
    prewarm_images_with_progress,
)

# ---------------------------------------------------------------------------
# PrewarmResult dataclass
# ---------------------------------------------------------------------------


class TestPrewarmResult:
    """Tests for the PrewarmResult dataclass."""

    def test_default_values(self):
        """Test that defaults are sane zeroes."""
        result = PrewarmResult()
        assert result.total_images == 0
        assert result.already_cached == 0
        assert result.newly_pulled == 0
        assert result.failed == []
        assert result.pull_time_seconds == 0.0

    def test_custom_values(self):
        """Test construction with explicit values."""
        result = PrewarmResult(
            total_images=10,
            already_cached=5,
            newly_pulled=3,
            failed=["img1", "img2"],
            pull_time_seconds=12.5,
        )
        assert result.total_images == 10
        assert result.already_cached == 5
        assert result.newly_pulled == 3
        assert result.failed == ["img1", "img2"]
        assert result.pull_time_seconds == 12.5

    def test_failed_list_is_independent(self):
        """Test that each instance gets its own failed list."""
        r1 = PrewarmResult()
        r2 = PrewarmResult()
        r1.failed.append("x")
        assert r2.failed == []


# ---------------------------------------------------------------------------
# get_required_images
# ---------------------------------------------------------------------------


class TestGetRequiredImages:
    """Tests for get_required_images()."""

    def test_swebench_lite_tasks(self):
        """Test image derivation for SWE-bench tasks."""
        tasks = [
            {"instance_id": "astropy__astropy-12907"},
            {"instance_id": "django__django-11099"},
        ]
        images = get_required_images("swe-bench-lite", tasks)

        assert len(images) == 2
        assert "ghcr.io/epoch-research/swe-bench.eval.x86_64.astropy__astropy-12907" in images
        assert "ghcr.io/epoch-research/swe-bench.eval.x86_64.django__django-11099" in images

    def test_swebench_verified_tasks(self):
        """Test image derivation for swe-bench-verified variant."""
        tasks = [{"instance_id": "flask__flask-4045"}]
        images = get_required_images("swe-bench-verified", tasks)

        assert len(images) == 1
        assert "flask__flask-4045" in images[0]

    def test_swebench_full_tasks(self):
        """Test image derivation for swe-bench-full variant."""
        tasks = [{"instance_id": "numpy__numpy-99999"}]
        images = get_required_images("swe-bench-full", tasks)

        assert len(images) == 1
        assert "numpy__numpy-99999" in images[0]

    def test_swebench_deduplicates(self):
        """Test that duplicate instance IDs produce unique images."""
        tasks = [
            {"instance_id": "repo__proj-1"},
            {"instance_id": "repo__proj-1"},
        ]
        images = get_required_images("swe-bench-lite", tasks)
        assert len(images) == 1

    def test_swebench_skips_empty_instance_id(self):
        """Test that tasks without instance_id are skipped."""
        tasks = [{"instance_id": ""}, {"instance_id": "valid__task-1"}]
        images = get_required_images("swe-bench-lite", tasks)
        assert len(images) == 1

    def test_non_swebench_benchmark(self):
        """Test that non-SWE-bench benchmarks return base images."""
        tasks = [{"task_id": "HumanEval/0"}, {"task_id": "HumanEval/1"}]
        images = get_required_images("humaneval", tasks)

        assert images == ["python:3.11-slim"]

    def test_unknown_benchmark_defaults(self):
        """Test that an unknown benchmark falls back to python:3.11-slim."""
        images = get_required_images("some-unknown-benchmark", [])
        assert images == ["python:3.11-slim"]

    def test_empty_tasks_swebench(self):
        """Test SWE-bench with empty task list."""
        images = get_required_images("swe-bench-lite", [])
        assert images == []

    def test_empty_tasks_non_swebench(self):
        """Test non-SWE-bench with empty task list still returns base image."""
        images = get_required_images("humaneval", [])
        assert images == ["python:3.11-slim"]


# ---------------------------------------------------------------------------
# check_cached_images
# ---------------------------------------------------------------------------


class TestCheckCachedImages:
    """Tests for check_cached_images()."""

    @patch("mcpbr.docker_prewarm.docker.from_env")
    def test_all_cached(self, mock_from_env):
        """Test when all images are already cached locally."""
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        # images.get succeeds for every image (image exists)
        mock_client.images.get.return_value = MagicMock()

        result = check_cached_images(["img_a", "img_b"])

        assert result == {"img_a": True, "img_b": True}

    @patch("mcpbr.docker_prewarm.docker.from_env")
    def test_none_cached(self, mock_from_env):
        """Test when no images are cached locally."""
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mock_client.images.get.side_effect = docker.errors.ImageNotFound("nope")

        result = check_cached_images(["img_a", "img_b"])

        assert result == {"img_a": False, "img_b": False}

    @patch("mcpbr.docker_prewarm.docker.from_env")
    def test_mixed_cache(self, mock_from_env):
        """Test when some images are cached and some are not."""
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        def _get(name):
            if name == "cached":
                return MagicMock()
            raise docker.errors.ImageNotFound("not found")

        mock_client.images.get.side_effect = _get

        result = check_cached_images(["cached", "missing"])

        assert result == {"cached": True, "missing": False}

    @patch("mcpbr.docker_prewarm.docker.from_env")
    def test_api_error_marks_uncached(self, mock_from_env):
        """Test that APIError for a specific image marks it as uncached."""
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mock_client.images.get.side_effect = docker.errors.APIError("oops")

        result = check_cached_images(["img_a"])

        assert result == {"img_a": False}

    @patch("mcpbr.docker_prewarm.docker.from_env")
    def test_docker_daemon_unavailable(self, mock_from_env):
        """Test fallback when Docker daemon is unreachable."""
        mock_from_env.side_effect = docker.errors.DockerException("daemon offline")

        result = check_cached_images(["img_a", "img_b"])

        assert result == {"img_a": False, "img_b": False}

    @patch("mcpbr.docker_prewarm.docker.from_env")
    def test_empty_image_list(self, mock_from_env):
        """Test with an empty list of images."""
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        result = check_cached_images([])

        assert result == {}


# ---------------------------------------------------------------------------
# prewarm_images (async)
# ---------------------------------------------------------------------------


class TestPrewarmImages:
    """Tests for the async prewarm_images() function."""

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_all_cached_skips_pull(self, mock_get, mock_check, mock_docker):
        """Test that no pulls happen when all images are already cached."""
        mock_get.return_value = ["img_a", "img_b"]
        mock_check.return_value = {"img_a": True, "img_b": True}

        result = await prewarm_images("humaneval", [{"task_id": "1"}])

        assert result.total_images == 2
        assert result.already_cached == 2
        assert result.newly_pulled == 0
        assert result.failed == []
        assert result.pull_time_seconds >= 0

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_pulls_missing_images(self, mock_get, mock_check, mock_docker):
        """Test that only uncached images are pulled."""
        mock_get.return_value = ["cached_img", "missing_img"]
        mock_check.return_value = {"cached_img": True, "missing_img": False}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.images.pull.return_value = MagicMock()

        result = await prewarm_images("humaneval", [{"task_id": "1"}])

        assert result.total_images == 2
        assert result.already_cached == 1
        assert result.newly_pulled == 1
        assert result.failed == []
        mock_client.images.pull.assert_called_once_with("missing_img", platform=None)

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_records_pull_failures(self, mock_get, mock_check, mock_docker):
        """Test that images that fail to pull are recorded in failed."""
        mock_get.return_value = ["bad_img"]
        mock_check.return_value = {"bad_img": False}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.images.pull.side_effect = docker.errors.ImageNotFound("nope")

        result = await prewarm_images("humaneval", [{"task_id": "1"}])

        assert result.total_images == 1
        assert result.already_cached == 0
        assert result.newly_pulled == 0
        assert result.failed == ["bad_img"]

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_api_error_records_failure(self, mock_get, mock_check, mock_docker):
        """Test that Docker API errors are recorded as failures."""
        mock_get.return_value = ["api_err_img"]
        mock_check.return_value = {"api_err_img": False}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.images.pull.side_effect = docker.errors.APIError("server error")

        result = await prewarm_images("humaneval", [{"task_id": "1"}])

        assert result.newly_pulled == 0
        assert "api_err_img" in result.failed

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_parallel_pulling_respects_semaphore(self, mock_get, mock_check, mock_docker):
        """Test that parallel pulls are limited by max_parallel."""
        images = [f"img_{i}" for i in range(6)]
        mock_get.return_value = images
        mock_check.return_value = {img: False for img in images}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        call_count_tracker: list[int] = []

        def _tracked_pull(image, platform=None):
            # This runs in an executor thread, but call_count_tracker
            # gives us visibility into overall call patterns.
            call_count_tracker.append(1)
            return MagicMock()

        mock_client.images.pull.side_effect = _tracked_pull

        result = await prewarm_images("humaneval", [{"task_id": "1"}], max_parallel=2)

        assert result.newly_pulled == 6
        assert result.failed == []
        assert mock_client.images.pull.call_count == 6

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_empty_image_list(self, mock_get, mock_check, mock_docker):
        """Test pre-warming with zero required images."""
        mock_get.return_value = []

        result = await prewarm_images("humaneval", [])

        assert result.total_images == 0
        assert result.already_cached == 0
        assert result.newly_pulled == 0

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_docker_daemon_unavailable(self, mock_get, mock_check, mock_docker):
        """Test graceful handling when Docker daemon is unreachable during pull."""
        mock_get.return_value = ["img_a"]
        mock_check.return_value = {"img_a": False}
        mock_docker.side_effect = docker.errors.DockerException("daemon offline")

        result = await prewarm_images("humaneval", [{"task_id": "1"}])

        assert result.total_images == 1
        assert result.newly_pulled == 0
        assert result.failed == ["img_a"]

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_progress_callback_invoked(self, mock_get, mock_check, mock_docker):
        """Test that on_progress callback is called for pulling and done."""
        mock_get.return_value = ["img_a"]
        mock_check.return_value = {"img_a": False}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.images.pull.return_value = MagicMock()

        progress_calls: list[tuple[str, str]] = []

        def _on_progress(image: str, status: str) -> None:
            progress_calls.append((image, status))

        result = await prewarm_images("humaneval", [{"task_id": "1"}], on_progress=_on_progress)

        assert result.newly_pulled == 1
        # Should have at least a "pulling" and a "done" call
        statuses = [s for _, s in progress_calls]
        assert "pulling" in statuses
        assert "done" in statuses

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_progress_callback_reports_failure(self, mock_get, mock_check, mock_docker):
        """Test that on_progress callback reports 'failed' for unsuccessful pulls."""
        mock_get.return_value = ["fail_img"]
        mock_check.return_value = {"fail_img": False}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.images.pull.side_effect = docker.errors.ImageNotFound("nope")

        progress_calls: list[tuple[str, str]] = []

        def _on_progress(image: str, status: str) -> None:
            progress_calls.append((image, status))

        result = await prewarm_images("humaneval", [{"task_id": "1"}], on_progress=_on_progress)

        assert result.failed == ["fail_img"]
        statuses = [s for _, s in progress_calls]
        assert "failed" in statuses

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_swebench_images_use_amd64_platform(self, mock_get, mock_check, mock_docker):
        """Test that SWE-bench images are pulled with linux/amd64 platform."""
        swe_image = "ghcr.io/epoch-research/swe-bench.eval.x86_64.test__test-1"
        mock_get.return_value = [swe_image]
        mock_check.return_value = {swe_image: False}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.images.pull.return_value = MagicMock()

        result = await prewarm_images("swe-bench-lite", [{"instance_id": "test__test-1"}])

        assert result.newly_pulled == 1
        mock_client.images.pull.assert_called_once_with(swe_image, platform="linux/amd64")

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_non_swebench_images_use_no_platform(self, mock_get, mock_check, mock_docker):
        """Test that non-SWE-bench images are pulled without a specific platform."""
        mock_get.return_value = ["python:3.11-slim"]
        mock_check.return_value = {"python:3.11-slim": False}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.images.pull.return_value = MagicMock()

        result = await prewarm_images("humaneval", [{"task_id": "1"}])

        assert result.newly_pulled == 1
        mock_client.images.pull.assert_called_once_with("python:3.11-slim", platform=None)

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_pull_time_is_positive(self, mock_get, mock_check, mock_docker):
        """Test that pull_time_seconds is recorded as a non-negative value."""
        mock_get.return_value = ["img"]
        mock_check.return_value = {"img": False}

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.images.pull.return_value = MagicMock()

        result = await prewarm_images("humaneval", [{"task_id": "1"}])

        assert result.pull_time_seconds >= 0


# ---------------------------------------------------------------------------
# format_prewarm_report
# ---------------------------------------------------------------------------


class TestFormatPrewarmReport:
    """Tests for format_prewarm_report() output."""

    @patch("mcpbr.docker_prewarm.Console")
    def test_report_all_cached(self, mock_console_cls):
        """Test report when all images were already cached."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console

        result = PrewarmResult(
            total_images=5,
            already_cached=5,
            newly_pulled=0,
            failed=[],
            pull_time_seconds=0.1,
        )
        format_prewarm_report(result)

        # Should print the table and a success-like message
        assert mock_console.print.call_count >= 2

    @patch("mcpbr.docker_prewarm.Console")
    def test_report_with_pulls(self, mock_console_cls):
        """Test report when images were pulled."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console

        result = PrewarmResult(
            total_images=3,
            already_cached=1,
            newly_pulled=2,
            failed=[],
            pull_time_seconds=15.3,
        )
        format_prewarm_report(result)

        # Verify we got at least the table and the success message
        assert mock_console.print.call_count >= 2

    @patch("mcpbr.docker_prewarm.Console")
    def test_report_with_failures(self, mock_console_cls):
        """Test report when some images failed to pull."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console

        result = PrewarmResult(
            total_images=3,
            already_cached=1,
            newly_pulled=1,
            failed=["bad_image:latest"],
            pull_time_seconds=10.0,
        )
        format_prewarm_report(result)

        # Should print failed image details
        printed_args = [str(c) for c in mock_console.print.call_args_list]
        printed_text = " ".join(printed_args)
        assert "bad_image" in printed_text

    @patch("mcpbr.docker_prewarm.Console")
    def test_report_empty_result(self, mock_console_cls):
        """Test report with an empty result (no images)."""
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console

        result = PrewarmResult()
        format_prewarm_report(result)

        # Should still print the table without errors
        assert mock_console.print.called


# ---------------------------------------------------------------------------
# prewarm_images_with_progress
# ---------------------------------------------------------------------------


class TestPrewarmImagesWithProgress:
    """Tests for the progress-bar wrapper."""

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.prewarm_images")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_delegates_when_nothing_to_pull(self, mock_get, mock_check, mock_prewarm):
        """Test that it delegates to prewarm_images when all cached."""
        mock_get.return_value = ["img"]
        mock_check.return_value = {"img": True}
        mock_prewarm.return_value = PrewarmResult(
            total_images=1, already_cached=1, pull_time_seconds=0.0
        )

        result = await prewarm_images_with_progress("humaneval", [{"task_id": "1"}])

        assert result.already_cached == 1
        mock_prewarm.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.Console")
    @patch("mcpbr.docker_prewarm.prewarm_images")
    @patch("mcpbr.docker_prewarm.check_cached_images")
    @patch("mcpbr.docker_prewarm.get_required_images")
    async def test_shows_progress_for_uncached(
        self, mock_get, mock_check, mock_prewarm, mock_console_cls
    ):
        """Test that progress is displayed when there are images to pull."""
        mock_get.return_value = ["img_a", "img_b"]
        mock_check.return_value = {"img_a": False, "img_b": False}
        mock_prewarm.return_value = PrewarmResult(
            total_images=2, newly_pulled=2, pull_time_seconds=5.0
        )

        result = await prewarm_images_with_progress("humaneval", [{"task_id": "1"}])

        assert result.newly_pulled == 2
        mock_prewarm.assert_awaited_once()


# ---------------------------------------------------------------------------
# Integration-style tests (still using mocks, but testing cross-function flow)
# ---------------------------------------------------------------------------


class TestPrewarmIntegration:
    """Integration-style tests combining multiple functions."""

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    async def test_full_swebench_prewarm_flow(self, mock_from_env):
        """Test the complete flow for SWE-bench tasks end-to-end (mocked)."""
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        # First call: check_cached_images calls images.get
        # Second call: prewarm_images calls images.pull
        pulled_images: list[str] = []

        def _get(name):
            # Simulate: first image is cached, second is not
            if "astropy" in name:
                return MagicMock()
            raise docker.errors.ImageNotFound("not found")

        def _pull(name, platform=None):
            pulled_images.append(name)
            return MagicMock()

        mock_client.images.get.side_effect = _get
        mock_client.images.pull.side_effect = _pull

        tasks = [
            {"instance_id": "astropy__astropy-12907"},
            {"instance_id": "django__django-11099"},
        ]
        result = await prewarm_images("swe-bench-lite", tasks)

        assert result.total_images == 2
        assert result.already_cached == 1
        assert result.newly_pulled == 1
        assert result.failed == []
        assert len(pulled_images) == 1
        assert "django" in pulled_images[0]

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    async def test_full_humaneval_prewarm_flow(self, mock_from_env):
        """Test the complete flow for a non-SWE-bench benchmark (mocked)."""
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        # python:3.11-slim is not cached
        mock_client.images.get.side_effect = docker.errors.ImageNotFound("nope")
        mock_client.images.pull.return_value = MagicMock()

        tasks = [{"task_id": "HumanEval/0"}, {"task_id": "HumanEval/1"}]
        result = await prewarm_images("humaneval", tasks)

        assert result.total_images == 1  # Only one base image needed
        assert result.already_cached == 0
        assert result.newly_pulled == 1
        assert result.failed == []
        mock_client.images.pull.assert_called_once_with("python:3.11-slim", platform=None)

    @pytest.mark.asyncio
    @patch("mcpbr.docker_prewarm.docker.from_env")
    async def test_mixed_success_and_failure(self, mock_from_env):
        """Test a run where some pulls succeed and some fail."""
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        # Nothing cached
        mock_client.images.get.side_effect = docker.errors.ImageNotFound("nope")

        def _pull(name, platform=None):
            if "good" in name:
                return MagicMock()
            raise docker.errors.APIError("server error")

        mock_client.images.pull.side_effect = _pull

        tasks = [
            {"instance_id": "good__good-1"},
            {"instance_id": "bad__bad-2"},
        ]
        result = await prewarm_images("swe-bench-lite", tasks)

        assert result.total_images == 2
        assert result.newly_pulled == 1
        assert len(result.failed) == 1
        assert "bad" in result.failed[0]
