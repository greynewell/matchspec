"""Integration tests for running real SWE-bench tasks.

These tests require:
- Docker running
- ANTHROPIC_API_KEY environment variable set
- Network access

Run with: pytest -m integration
Skip with: pytest -m "not integration"
"""

import os

import pytest

from mcpbr.config import HarnessConfig, MCPServerConfig
from mcpbr.harness import run_evaluation

pytestmark = pytest.mark.integration


SIMPLE_TASK_ID = "astropy__astropy-12907"


@pytest.fixture
def integration_config() -> HarnessConfig:
    """Create a configuration for integration testing."""
    return HarnessConfig(
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        provider="anthropic",
        agent_harness="claude-code",
        model="sonnet",
        dataset="SWE-bench/SWE-bench_Lite",
        sample_size=1,
        timeout_seconds=300,
        max_concurrent=1,
        max_iterations=5,
    )


@pytest.mark.integration
async def test_single_swebench_task_mcp_only(integration_config: HarnessConfig) -> None:
    """Run a single SWE-bench task with MCP agent only.

    This test:
    1. Loads one task from SWE-bench_Lite
    2. Creates a Docker environment
    3. Runs the MCP agent with filesystem tools
    4. Evaluates the generated patch

    The test passes if the evaluation completes without errors,
    regardless of whether the patch resolves the issue.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    results = await run_evaluation(
        config=integration_config,
        run_mcp=True,
        run_baseline=False,
        verbose=True,
        task_ids=[SIMPLE_TASK_ID],
    )

    assert results is not None
    assert len(results.tasks) == 1

    task_result = results.tasks[0]
    assert task_result.instance_id == SIMPLE_TASK_ID
    assert task_result.mcp is not None

    assert "resolved" in task_result.mcp
    assert "patch_applied" in task_result.mcp
    assert "tokens" in task_result.mcp
    assert "iterations" in task_result.mcp


@pytest.mark.integration
async def test_single_swebench_task_baseline_only(integration_config: HarnessConfig) -> None:
    """Run a single SWE-bench task with baseline agent only.

    This test:
    1. Loads one task from SWE-bench_Lite
    2. Creates a Docker environment
    3. Runs the baseline agent (no tools)
    4. Evaluates the generated patch

    The test passes if the evaluation completes without errors.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    results = await run_evaluation(
        config=integration_config,
        run_mcp=False,
        run_baseline=True,
        verbose=True,
        task_ids=[SIMPLE_TASK_ID],
    )

    assert results is not None
    assert len(results.tasks) == 1

    task_result = results.tasks[0]
    assert task_result.instance_id == SIMPLE_TASK_ID
    assert task_result.baseline is not None

    assert "resolved" in task_result.baseline
    assert "patch_applied" in task_result.baseline
    assert "tokens" in task_result.baseline


@pytest.mark.integration
async def test_single_swebench_task_both_agents(integration_config: HarnessConfig) -> None:
    """Run a single SWE-bench task with both MCP and baseline agents.

    This is the full evaluation flow that compares both agents.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    results = await run_evaluation(
        config=integration_config,
        run_mcp=True,
        run_baseline=True,
        verbose=True,
        task_ids=[SIMPLE_TASK_ID],
    )

    assert results is not None
    assert len(results.tasks) == 1

    task_result = results.tasks[0]
    assert task_result.mcp is not None
    assert task_result.baseline is not None

    assert "mcp" in results.summary
    assert "baseline" in results.summary
    assert "improvement" in results.summary


@pytest.mark.integration
async def test_evaluation_with_openai_provider() -> None:
    """Test evaluation using direct OpenAI provider.

    Currently skipped: OpenAI provider not yet implemented.
    """
    pytest.skip("OpenAI provider not yet implemented")


@pytest.mark.integration
async def test_evaluation_with_anthropic_provider() -> None:
    """Test evaluation using direct Anthropic provider.

    Requires ANTHROPIC_API_KEY environment variable.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    config = HarnessConfig(
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        provider="anthropic",
        agent_harness="claude-code",
        model="sonnet",
        dataset="SWE-bench/SWE-bench_Lite",
        sample_size=1,
        timeout_seconds=300,
        max_concurrent=1,
        max_iterations=5,
    )

    results = await run_evaluation(
        config=config,
        run_mcp=False,
        run_baseline=True,
        verbose=True,
        task_ids=[SIMPLE_TASK_ID],
    )

    assert results is not None
    assert len(results.tasks) == 1


# Claude 4.5 model IDs for API validation
CLAUDE_45_MODELS = [
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
]


@pytest.mark.integration
@pytest.mark.parametrize("model_id", CLAUDE_45_MODELS)
async def test_claude_45_model_api_compatibility(model_id: str) -> None:
    """Verify Claude 4.5 model IDs are accepted by the Anthropic API.

    Makes a minimal API call with max_tokens=10 to verify the model ID is valid.
    This is a lightweight test to catch model ID typos or deprecations early.

    Note: claude-opus-4-5 is excluded to avoid higher costs during testing.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model_id,
        max_tokens=10,
        messages=[{"role": "user", "content": "Say 'test' and nothing else."}],
    )

    assert message.id is not None
    assert message.model == model_id
    assert message.stop_reason in ("end_turn", "max_tokens")
    assert len(message.content) > 0


@pytest.mark.integration
async def test_claude_45_sonnet_streaming() -> None:
    """Verify Claude 4.5 Sonnet works with streaming responses.

    Streaming is important for real-time agent feedback.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    chunks = []
    with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=20,
        messages=[{"role": "user", "content": "Count from 1 to 3."}],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)

    assert len(chunks) > 0
    full_response = "".join(chunks)
    assert len(full_response) > 0
