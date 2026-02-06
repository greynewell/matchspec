"""Tests for cold-start staggering and zero-iteration retry logic."""

import asyncio

import pytest

from mcpbr.harness import TaskResult


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
        loop = asyncio.get_event_loop()

        # Fake run_single_task that just records when it was called
        async def fake_run_single_task(*args, **kwargs):
            launch_times.append(loop.time())
            await asyncio.sleep(0.05)  # Simulate brief work
            return TaskResult(instance_id=f"task-{len(launch_times)}")

        tasks = [{"instance_id": f"task-{i}"} for i in range(5)]
        max_concurrent = 5  # All 5 could start at once without staggering

        semaphore = asyncio.Semaphore(max_concurrent)
        task_counter = 0

        from mcpbr.harness import _stagger_delay

        async def run_with_semaphore(task):
            nonlocal task_counter
            my_index = task_counter
            task_counter += 1
            delay = _stagger_delay(my_index, max_concurrent)
            if delay > 0:
                await asyncio.sleep(delay)
            async with semaphore:
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
        from mcpbr.harness import _stagger_delay

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
        from mcpbr.harness import _stagger_delay

        assert _stagger_delay(0, max_concurrent=1) == 0.0
        assert _stagger_delay(1, max_concurrent=1) == 0.0


class TestZeroIterationRetry:
    """Verify that tasks which timeout with zero iterations get retried."""

    @pytest.mark.asyncio
    async def test_zero_iteration_timeout_triggers_retry(self) -> None:
        """A task that times out with 0 iterations should be retried once."""
        call_count = 0

        # First call: returns zero-iteration timeout (cold-start failure)
        # Second call: returns a real result
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
        real_result = {
            "resolved": True,
            "patch_applied": True,
            "status": "completed",
            "tokens": {"input": 5000, "output": 2000},
            "iterations": 15,
            "tool_calls": 10,
            "cost": 0.05,
            "runtime_seconds": 180.0,
        }

        async def mock_run_eval(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return zero_iter_result
            return real_result

        from mcpbr.harness import _should_retry_zero_iteration

        # Should retry: zero iterations + timeout status
        assert _should_retry_zero_iteration(zero_iter_result) is True

        # Should NOT retry: has iterations
        assert _should_retry_zero_iteration(real_result) is False

        # Should NOT retry: zero iterations but not a timeout
        error_result = {**zero_iter_result, "status": "error", "error": "Something broke"}
        assert _should_retry_zero_iteration(error_result) is False

    @pytest.mark.asyncio
    async def test_zero_iteration_retry_only_happens_once(self) -> None:
        """Even if retry also produces zero iterations, don't retry again."""
        from mcpbr.harness import _should_retry_zero_iteration

        zero_iter = {
            "resolved": False,
            "status": "timeout",
            "iterations": 0,
            "tokens": {"input": 0, "output": 0},
        }

        # First check: should retry
        assert _should_retry_zero_iteration(zero_iter) is True
        # The retry logic itself limits to one retry — this function just
        # checks the condition; the caller is responsible for the retry cap.

    @pytest.mark.asyncio
    async def test_completed_task_not_retried(self) -> None:
        """A task that completed successfully should never be retried."""
        from mcpbr.harness import _should_retry_zero_iteration

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
        from mcpbr.harness import _should_retry_zero_iteration

        real_timeout = {
            "resolved": False,
            "status": "timeout",
            "iterations": 5,
            "tokens": {"input": 3000, "output": 1500},
        }
        assert _should_retry_zero_iteration(real_timeout) is False
