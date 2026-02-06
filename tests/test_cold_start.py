"""Tests for cold-start staggering and zero-iteration retry logic."""

import asyncio

import pytest

from mcpbr.harness import TaskResult, _should_retry_zero_iteration, _stagger_delay


class TestStaggeredStarts:
    """Verify that concurrent task launches are staggered to avoid cold-start failures."""

    @pytest.mark.asyncio
    async def test_tasks_are_staggered(self) -> None:
        """First-batch tasks should not all start at the same instant.

        When max_concurrent > 1, the semaphore wrapper should insert a small
        delay between task launches so Docker isn't overwhelmed by simultaneous
        image pulls and container startups.
        """
        launch_times: list[float] = []
        loop = asyncio.get_running_loop()

        async def fake_run_single_task(task):
            launch_times.append(loop.time())
            await asyncio.sleep(0.05)  # Simulate brief work
            return TaskResult(instance_id=f"task-{len(launch_times)}")

        tasks = [{"instance_id": f"task-{i}"} for i in range(5)]
        max_concurrent = 5  # All 5 could start at once without staggering

        semaphore = asyncio.Semaphore(max_concurrent)
        task_counter = 0

        async def run_with_semaphore(task):
            nonlocal task_counter
            async with semaphore:
                my_index = task_counter
                task_counter += 1
                delay = _stagger_delay(my_index, max_concurrent)
                if delay > 0:
                    await asyncio.sleep(delay)
                return await fake_run_single_task(task)

        async_tasks = [asyncio.create_task(run_with_semaphore(t)) for t in tasks]
        await asyncio.gather(*async_tasks)

        assert len(launch_times) == 5

        # The first and last task should be separated by at least some delay
        spread = launch_times[-1] - launch_times[0]
        assert spread > 0.1, (
            f"Tasks launched with only {spread:.3f}s spread — expected staggering to space them out"
        )

    @pytest.mark.asyncio
    async def test_stagger_delay_values(self) -> None:
        """_stagger_delay should return increasing delays for the first batch."""
        # First task: no delay
        assert _stagger_delay(0, max_concurrent=5) == 0.0

        # Subsequent first-batch tasks: increasing delay
        d1 = _stagger_delay(1, max_concurrent=5)
        d2 = _stagger_delay(2, max_concurrent=5)
        assert d1 > 0
        assert d2 > d1

        # Tasks beyond the first batch: no delay
        assert _stagger_delay(5, max_concurrent=5) == 0.0
        assert _stagger_delay(10, max_concurrent=5) == 0.0

    @pytest.mark.asyncio
    async def test_stagger_delay_single_concurrent(self) -> None:
        """With max_concurrent=1, no staggering is needed."""
        assert _stagger_delay(0, max_concurrent=1) == 0.0
        assert _stagger_delay(1, max_concurrent=1) == 0.0


class TestZeroIterationRetry:
    """Verify that _should_retry_zero_iteration detects cold-start failures."""

    @pytest.mark.asyncio
    async def test_detects_cold_start_failure(self) -> None:
        """Zero iterations + zero tokens + timeout = cold-start failure."""
        zero_iter_result = {
            "resolved": False,
            "patch_applied": False,
            "status": "timeout",
            "error": "Timeout",
            "tokens": {"input": 0, "output": 0},
            "iterations": 0,
            "tool_calls": 0,
            "cost": 0.0,
            "runtime_seconds": 236.0,
        }
        assert _should_retry_zero_iteration(zero_iter_result) is True

    @pytest.mark.asyncio
    async def test_completed_task_not_retried(self) -> None:
        """A task that completed successfully should never be retried."""
        good_result = {
            "resolved": True,
            "status": "completed",
            "iterations": 20,
            "tokens": {"input": 10000, "output": 5000},
        }
        assert _should_retry_zero_iteration(good_result) is False

    @pytest.mark.asyncio
    async def test_nonzero_iteration_timeout_not_retried(self) -> None:
        """A timeout with real iterations is a genuine timeout, not cold-start."""
        real_timeout = {
            "resolved": False,
            "status": "timeout",
            "iterations": 5,
            "tokens": {"input": 3000, "output": 1500},
        }
        assert _should_retry_zero_iteration(real_timeout) is False

    @pytest.mark.asyncio
    async def test_non_timeout_error_not_retried(self) -> None:
        """Zero iterations from a non-timeout error should not trigger retry."""
        error_result = {
            "resolved": False,
            "status": "error",
            "error": "Something broke",
            "iterations": 0,
            "tokens": {"input": 0, "output": 0},
        }
        assert _should_retry_zero_iteration(error_result) is False
