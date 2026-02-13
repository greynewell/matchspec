"""Agent implementations for SWE-bench evaluation."""

import re
from typing import Any

from .docker_env import TaskEnvironment
from .harnesses import AgentResult
from .models import DEFAULT_MODEL
from .providers import ModelProvider, create_provider

SYSTEM_PROMPT = """\
You are an expert software engineer tasked with fixing a bug in a GitHub repository.
You will be given a problem statement describing the issue.

Your goal is to:
1. Understand the problem from the description
2. Identify the root cause
3. Generate a patch that fixes the issue

Output your fix as a unified diff patch that can be applied with `git apply`.
The patch should be minimal and focused on fixing the specific issue.

Format your final answer as:
```patch
<your unified diff here>
```
"""


def extract_patch(text: str) -> str:
    """Extract patch from agent response."""
    patterns = [
        r"```(?:patch|diff)\n(.*?)```",
        r"```\n((?:---|\+\+\+|@@|diff).*?)```",
        r"((?:^---\s+\S+.*?\n\+\+\+\s+\S+.*?\n@@.*?)+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()

    return ""


class BaselineAgent:
    """Agent without tools - single-shot patch generation."""

    def __init__(
        self,
        provider: ModelProvider | None = None,
        model: str = DEFAULT_MODEL,
        provider_name: str = "openrouter",
        api_key: str | None = None,
    ) -> None:
        """Initialize baseline agent.

        Args:
            provider: Pre-configured ModelProvider. If provided, other args are ignored.
            model: Model identifier.
            provider_name: Provider to use if no provider given.
            api_key: API key for the provider.
        """
        if provider is not None:
            self.provider = provider
        else:
            self.provider = create_provider(provider_name, model, api_key)

    async def solve(
        self,
        task: dict[str, Any],
        env: TaskEnvironment,
        timeout: int = 300,
    ) -> AgentResult:
        """Generate a patch for the task without using tools.

        Args:
            task: SWE-bench task dictionary.
            env: Docker environment (used to get context).
            timeout: Timeout in seconds.

        Returns:
            AgentResult with the generated patch.
        """
        problem_statement = task["problem_statement"]

        context = await self._gather_context(env, task)

        user_message = f"""\
## Problem Statement

{problem_statement}

## Repository Context

{context}

Please analyze the problem and provide a unified diff patch to fix it.
"""

        try:
            response = self.provider.chat(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=4096,
            )

            content = response.message.content or ""
            patch = extract_patch(content)

            return AgentResult(
                patch=patch,
                success=bool(patch),
                error=None if patch else "No patch found in response",
                tokens_input=response.input_tokens,
                tokens_output=response.output_tokens,
                iterations=1,
                tool_calls=0,
                messages=[{"role": "assistant", "content": content}],
            )

        except Exception as e:
            return AgentResult(
                patch="",
                success=False,
                error=str(e),
            )

    async def _gather_context(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
    ) -> str:
        """Gather repository context for the baseline agent."""
        context_parts = []

        exit_code, stdout, _stderr = await env.exec_command(
            "find . -type f -name '*.py' | head -50",
            timeout=30,
        )
        if exit_code == 0 and stdout:
            context_parts.append(f"Python files in repository:\n{stdout}")

        exit_code, stdout, _stderr = await env.exec_command(
            "ls -la",
            timeout=10,
        )
        if exit_code == 0:
            context_parts.append(f"Root directory:\n{stdout}")

        problem = task["problem_statement"].lower()
        keywords = self._extract_keywords(problem)

        for keyword in keywords[:3]:
            exit_code, stdout, _stderr = await env.exec_command(
                f"grep -rl '{keyword}' --include='*.py' . 2>/dev/null | head -5",
                timeout=30,
            )
            if exit_code == 0 and stdout:
                files = stdout.strip().split("\n")
                for filepath in files[:2]:
                    if filepath:
                        exit_code, content, _ = await env.exec_command(
                            f"head -100 '{filepath}'",
                            timeout=10,
                        )
                        if exit_code == 0:
                            context_parts.append(f"File: {filepath}\n```python\n{content}\n```")

        return "\n\n".join(context_parts)

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract likely code-related keywords from problem statement."""
        words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", text)
        keywords = []
        for word in words:
            if (
                len(word) > 3
                and word
                not in {"this", "that", "with", "from", "have", "when", "should", "would", "could"}
                and not word.isupper()
            ) and word not in keywords:
                keywords.append(word)
        return keywords[:10]
