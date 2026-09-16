"""
Async Coordinator Agent (class-based)
=====================================

Hub-and-spoke multi-agent research system using:

    - Python asyncio
    - Anthropic AsyncAnthropic client
    - Parallel research subagents
    - Final synthesis/aggregation agent

Architecture
------------

                    ┌──────────────────────┐
                    │     COORDINATOR      │
                    │  1. Decompose topic  │
                    │  2. Select agents    │
                    └──────────┬───────────┘
                               ▼
                ┌──────────────────────────────┐
                │      PARALLEL RESEARCH       │
                │  Agent 1  Agent 2  ...       │
                │       asyncio.gather()       │
                └──────────────┬───────────────┘
                       WAIT FOR ALL
                               ▼
                    ┌──────────────────────┐
                    │   SYNTHESIS AGENT    │
                    └──────────┬───────────┘
                               ▼
                         FINAL REPORT

Behavior contract (unchanged from the original script)
------------------------------------------------------

1. The coordinator creates the research plan.
2. Every research subagent is started concurrently.
3. Each subagent sees ONLY its own question.
4. A failed subagent does not cancel the others.
5. The coordinator waits for ALL research agents.
6. Only after all research agents finish does synthesis begin.
7. Failed research tasks are explicitly passed to synthesis as gaps.
8. Retry delays use asyncio.sleep() and never block the event loop.

Setup
-----

    pip install anthropic

Run:

    python coordinator_first_agent.py

Configuration is loaded from ../.claude/settings.json:

    {
        "env": {
            "ANTHROPIC_MODEL": "...",
            "ANTHROPIC_AUTH_TOKEN": "...",
            "ANTHROPIC_BASE_URL": "...",
            "MAX_PARALLEL_SUBAGENTS": "8"
        }
    }
"""

import os
import json
import time
import asyncio
from datetime import datetime

from anthropic import AsyncAnthropic


# ============================================================================
# Prompts and tool schema (module-level constants: shared, immutable)
# ============================================================================

COORDINATOR_SYSTEM_PROMPT = """\
You are the COORDINATOR in a hub-and-spoke research system.

You are the hub.

You never perform the primary research yourself.

Your responsibilities are:

1. Decompose a broad research topic into AT LEAST 5 focused,
   non-overlapping sub-questions.

2. The sub-questions together must cover the FULL BREADTH of the subject.

3. Do not focus only on the two or three most commonly discussed
   aspects of the topic.

4. Decide which research subagent should handle each sub-question.

5. Later, when all research findings are provided to you, synthesize
   them into one coherent final report.

6. During synthesis:
   - resolve contradictions where possible
   - remove unnecessary redundancy
   - preserve important distinctions
   - identify missing information
   - explicitly identify failed research tasks

Breadth requirement:

Before finalizing the research plan, explicitly consider whether
ALL major categories, technologies, dimensions, stakeholders,
risks, alternatives, and other important perspectives have been
covered.

Err on the side of more sub-questions.

Use between 5 and 8 sub-questions.

Subagents:

Each subagent receives exactly ONE research question.

Subagents:
- do not see the original broad topic
- do not see the other research questions
- do not see other subagents' answers
- do not decompose the question further
- do not communicate with each other
- do not produce the final report

All orchestration and final synthesis belongs to the coordinator.
"""


SUBAGENT_SYSTEM_TEMPLATE = (
    "You are '{subagent_name}', a narrow research subagent.\n\n"
    "Answer ONLY the research question you are given.\n\n"
    "You have no context beyond this single question.\n\n"
    "Do not attempt to coordinate with other agents.\n"
    "Do not create additional research tasks.\n"
    "Do not produce a final combined report.\n\n"
    "Provide useful, factual, concise research findings."
)


DECOMPOSE_TOOL = {
    "name": "create_research_plan",
    "description": (
        "Submit the decomposition of the topic into focused research "
        "sub-questions, each assigned to a research subagent. The plan "
        "must cover the full breadth of the topic."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "minItems": 5,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "subagent": {
                            "type": "string",
                            "description": (
                                "Name of the research subagent assigned "
                                "to this question. Example: "
                                "'market_research_agent'."
                            ),
                        },
                        "question": {
                            "type": "string",
                            "description": (
                                "A single, self-contained research question."
                            ),
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "The distinct category or dimension "
                                "covered by this question."
                            ),
                        },
                    },
                    "required": ["subagent", "question", "category"],
                },
            }
        },
        "required": ["subtasks"],
    },
}


DEFAULT_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".claude",
    "settings.json",
)


# ============================================================================
# Coordinator Agent
# ============================================================================

class AsyncCoordinatorAgent:
    """
    Hub-and-spoke research coordinator.

    One instance owns:
        - the AsyncAnthropic client
        - the model name
        - the concurrency limit
        - the prompts / tool schema

    Typical use:

        agent = AsyncCoordinatorAgent()
        result = asyncio.run(agent.run("some broad topic"))

    Or with explicit configuration (no settings.json needed):

        agent = AsyncCoordinatorAgent(
            model="claude-sonnet-4-5",
            auth_token="...",
            base_url="...",
            max_parallel_subagents=4,
        )
    """

    # ------------------------------------------------------------------
    # Construction / configuration
    # ------------------------------------------------------------------

    def __init__(
        self,
        model: str | None = None,
        auth_token: str | None = None,
        base_url: str | None = None,
        max_parallel_subagents: int | None = None,
        max_retries: int = 2,
        settings_path: str = DEFAULT_SETTINGS_PATH,
        client: AsyncAnthropic | None = None,
    ) -> None:

        env = self._load_env_settings(settings_path)

        self.model = model or env["ANTHROPIC_MODEL"]

        # Maximum number of research agents allowed to execute concurrently.
        #
        # Decomposition allows 5-8 agents, so the default of 8 means that
        # all research agents can normally run at the same time.
        self.max_parallel_subagents = int(
            max_parallel_subagents
            if max_parallel_subagents is not None
            else env.get("MAX_PARALLEL_SUBAGENTS", "8")
        )

        self.max_retries = max_retries

        self.client = client or AsyncAnthropic(
            auth_token=auth_token or env["ANTHROPIC_AUTH_TOKEN"],
            base_url=base_url or env.get("ANTHROPIC_BASE_URL"),
        )

    @staticmethod
    def _load_env_settings(settings_path: str) -> dict:
        """
        Load environment-style settings from .claude/settings.json.

        Returns an empty dict if the file is absent, so an instance can
        still be constructed from explicit arguments.
        """

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f).get("env", {})
        except FileNotFoundError:
            return {}

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(response) -> str:
        """
        Extract text from an Anthropic response.

        Responses can contain multiple content blocks; only blocks whose
        type is 'text' are collected.
        """

        return "".join(
            block.text
            for block in response.content
            if block.type == "text"
        )

    @staticmethod
    def _log(message: str) -> None:
        """
        Print a timestamped progress message.

        flush=True ensures logs appear immediately while the program runs.
        """

        timestamp = datetime.now().strftime("%H:%M:%S")

        print(f"[{timestamp}] {message}", flush=True)

    @staticmethod
    def _distinct_categories(subtasks: list[dict]) -> set[str]:

        return {
            task.get("category", "").strip().lower()
            for task in subtasks
            if task.get("category", "").strip()
        }

    # ------------------------------------------------------------------
    # STEP 1 - Decomposition
    # ------------------------------------------------------------------

    async def _request_plan(
        self,
        topic: str,
        extra_instruction: str = "",
    ) -> list[dict]:
        """
        Single decomposition call. Forces use of the create_research_plan tool.
        """

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=COORDINATOR_SYSTEM_PROMPT,
            tools=[DECOMPOSE_TOOL],
            tool_choice={
                "type": "tool",
                "name": "create_research_plan",
            },
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Research topic: {topic}\n"
                        f"{extra_instruction}"
                    ),
                }
            ],
        )

        for block in response.content:

            if (
                block.type == "tool_use"
                and block.name == "create_research_plan"
            ):
                return block.input["subtasks"]

        # DEBUG: see what actually came back
        self._log(f"[DEBUG] stop_reason={response.stop_reason}")
        self._log(f"[DEBUG] content={response.content}")

        raise RuntimeError("Coordinator did not return a research plan")

    async def plan_research(self, topic: str) -> list[dict]:
        """
        Ask the coordinator model to decompose the broad topic.

        Returns:

            [{"subagent": "...", "question": "...", "category": "..."}]

        Retries once if the resulting plan does not contain enough
        distinct categories.
        """

        self._log(f"[COORDINATOR] Decomposing topic: '{topic}'")

        subtasks = await self._request_plan(topic)

        categories = self._distinct_categories(subtasks)

        self._log(
            f"[COORDINATOR] First pass: "
            f"{len(subtasks)} subtasks, "
            f"{len(categories)} distinct categories -> "
            f"{sorted(categories)}"
        )

        # Retry if coverage is too narrow
        if len(subtasks) < 5 or len(categories) < 5:

            self._log(
                "[COORDINATOR] Coverage too narrow - "
                "retrying decomposition once"
            )

            subtasks = await self._request_plan(
                topic,
                "Your previous attempt did not cover enough distinct "
                "categories of this topic.\n\n"
                "Provide at least 5 sub-questions spanning 5 genuinely "
                "distinct categories or dimensions of the subject.\n\n"
                "Do not repeat, merge, or unnecessarily overlap categories.",
            )

            categories = self._distinct_categories(subtasks)

            self._log(
                f"[COORDINATOR] Retry result: "
                f"{len(subtasks)} subtasks, "
                f"{len(categories)} distinct categories -> "
                f"{sorted(categories)}"
            )

        self._log(f"[COORDINATOR] Final plan has {len(subtasks)} subtasks:")

        for task in subtasks:

            self._log(
                f"    - [{task['category']}] "
                f"-> {task['subagent']}: "
                f"{task['question']}"
            )

        return subtasks

    # ------------------------------------------------------------------
    # STEP 2 - Research subagents
    # ------------------------------------------------------------------

    async def run_subagent(
        self,
        subagent_name: str,
        question: str,
        max_retries: int | None = None,
    ) -> dict:
        """
        Execute one research subagent asynchronously.

        This method does NOT pass along:
            - the original research topic
            - the research plan
            - other subagents or their answers

        The subagent only ever sees its own question.

        Returns:

            {"answer": str, "is_error": bool}
        """

        retries = self.max_retries if max_retries is None else max_retries

        last_error = None

        for attempt in range(retries + 1):

            self._log(
                f"  [{subagent_name}] "
                f"attempt {attempt + 1}/{retries + 1} "
                f"- calling model..."
            )

            start = time.time()

            try:

                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system=SUBAGENT_SYSTEM_TEMPLATE.format(
                        subagent_name=subagent_name
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": question,
                        }
                    ],
                )

            except Exception as e:

                last_error = f"{type(e).__name__}: {e}"

                elapsed = time.time() - start

                self._log(
                    f"  [{subagent_name}] "
                    f"ERROR after {elapsed:.1f}s: {last_error}"
                )

                # IMPORTANT: asyncio.sleep(), never time.sleep().
                # time.sleep() would block the whole event loop and stall
                # every other research agent.
                await asyncio.sleep(1.5 * (attempt + 1))

                continue

            text = self._extract_text(response)

            elapsed = time.time() - start

            if text.strip():

                self._log(
                    f"  [{subagent_name}] "
                    f"OK in {elapsed:.1f}s - {len(text)} chars returned"
                )

                return {"answer": text, "is_error": False}

            # Empty response
            last_error = f"empty response (stop_reason={response.stop_reason})"

            self._log(
                f"  [{subagent_name}] "
                f"EMPTY in {elapsed:.1f}s - {last_error}"
            )

            await asyncio.sleep(1.5 * (attempt + 1))

        self._log(
            f"  [{subagent_name}] "
            f"FAILED after {retries + 1} attempts: {last_error}"
        )

        return {
            "answer": last_error or "unknown failure",
            "is_error": True,
        }

    async def _run_with_limit(
        self,
        semaphore: asyncio.Semaphore,
        index: int,
        total: int,
        task: dict,
    ) -> dict:
        """
        Run one subagent under the concurrency semaphore and normalize its
        result into a finding dict. Unexpected exceptions are converted into
        failed findings so one broken task cannot destroy the whole run.
        """

        async with semaphore:

            self._log(
                f"[COORDINATOR] "
                f"STARTING ({index + 1}/{total}) "
                f"-> {task['subagent']} [{task['category']}]"
            )

            try:

                result = await self.run_subagent(
                    task["subagent"],
                    task["question"],
                )

            except Exception as e:

                error_message = f"{type(e).__name__}: {e}"

                self._log(
                    f"[COORDINATOR] UNEXPECTED FAILURE -> "
                    f"{task['subagent']}: {error_message}"
                )

                result = {"answer": error_message, "is_error": True}

            return {
                "subagent": task["subagent"],
                "category": task["category"],
                "question": task["question"],
                "answer": result["answer"],
                "is_error": result["is_error"],
            }

    async def run_subagents_parallel(self, plan: list[dict]) -> list[dict]:
        """
        Run every research subagent concurrently.

            Task 1 ─────┐
            Task 2 ─────┤
            Task 3 ─────┤
                        │
                 asyncio.gather()
                        ▼
                 WAIT FOR ALL

        return_exceptions=True is intentionally NOT used: _run_with_limit
        already converts failures into structured results.
        """

        total = len(plan)

        if total == 0:
            return []

        # If there are 8 tasks and max_parallel_subagents=8, all 8 run at
        # once. With max_parallel_subagents=4, only 4 run at a time.
        semaphore = asyncio.Semaphore(self.max_parallel_subagents)

        # All tasks are created first, then gathered - they are not awaited
        # one at a time.
        tasks = [
            asyncio.create_task(
                self._run_with_limit(semaphore, index, total, task)
            )
            for index, task in enumerate(plan)
        ]

        self._log(f"[COORDINATOR] Created {len(tasks)} async research tasks.")

        self._log(
            "[COORDINATOR] All research agents are now running concurrently..."
        )

        dispatch_start = time.time()

        # --------------------------------------------------------------
        # WAIT FOR ALL RESEARCH AGENTS
        #
        # Critical synchronization point: nothing below runs until every
        # task is complete.
        # --------------------------------------------------------------

        findings = await asyncio.gather(*tasks)

        elapsed = time.time() - dispatch_start

        self._log(
            f"[COORDINATOR] ALL {total} research agents completed "
            f"in {elapsed:.1f}s."
        )

        return list(findings)

    # ------------------------------------------------------------------
    # STEP 3 - Synthesis
    # ------------------------------------------------------------------

    @staticmethod
    def _build_findings_block(findings: list[dict]) -> str:

        return "\n\n".join(
            (
                f"[{finding['subagent']}] "
                f"[CATEGORY: {finding.get('category', 'unknown')}]"
                + (" (FAILED - no usable data)" if finding["is_error"] else "")
                + f"\nQ: {finding['question']}"
                + f"\nA: {finding['answer']}"
            )
            for finding in findings
        )

    async def aggregate(self, topic: str, findings: list[dict]) -> dict:
        """
        Final synthesis agent.

        Called ONLY after run_subagents_parallel() has returned, so the
        synthesis agent always receives the complete set of results.
        """

        findings_block = self._build_findings_block(findings)

        self._log("[COORDINATOR] All research agents completed.")
        self._log("[COORDINATOR] Starting final synthesis agent...")

        start = time.time()

        try:

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=COORDINATOR_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Original topic:\n{topic}\n\n"

                            "All parallel research subagents have now "
                            "completed.\n\n"

                            "You are receiving the complete set of "
                            "research findings below.\n\n"

                            "==============================\n"
                            "SUBAGENT FINDINGS\n"
                            "==============================\n\n"

                            f"{findings_block}\n\n"

                            "==============================\n"
                            "SYNTHESIS INSTRUCTIONS\n"
                            "==============================\n\n"

                            "Synthesize ALL available findings into one "
                            "coherent final research report.\n\n"

                            "Requirements:\n\n"

                            "1. Integrate findings across all successful "
                            "research agents.\n\n"

                            "2. Resolve contradictions where possible. "
                            "If a contradiction cannot be resolved from "
                            "the available evidence, explicitly mention it.\n\n"

                            "3. Remove redundant information.\n\n"

                            "4. Preserve important distinctions between "
                            "different categories.\n\n"

                            "5. Do not silently omit a research category.\n\n"

                            "6. Any subagent marked FAILED represents a "
                            "research gap. Explicitly identify it.\n\n"

                            "7. Do not claim that failed research was "
                            "successfully completed.\n\n"

                            "8. Organize the final answer clearly with "
                            "appropriate headings and sections.\n\n"

                            "9. Produce a useful final research report "
                            "rather than simply repeating the individual "
                            "subagent answers."
                        ),
                    }
                ],
            )

            text = self._extract_text(response)

            elapsed = time.time() - start

            if text.strip():

                self._log(
                    f"[COORDINATOR] Final synthesis completed in "
                    f"{elapsed:.1f}s - {len(text)} chars"
                )

                return {"report": text, "is_error": False}

            self._log(
                f"[COORDINATOR] Final synthesis returned empty response "
                f"after {elapsed:.1f}s"
            )

            return {"report": "", "is_error": True}

        except Exception as e:

            elapsed = time.time() - start

            error_message = f"{type(e).__name__}: {e}"

            self._log(
                f"[COORDINATOR] Final synthesis ERROR after "
                f"{elapsed:.1f}s: {error_message}"
            )

            return {"report": error_message, "is_error": True}

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self, topic: str) -> dict:
        """
        Execute the complete research workflow.

            STEP 1  decompose topic
                       ↓
            STEP 2  all research agents run concurrently
                       ↓
                    asyncio.gather() -> ALL COMPLETE
                       ↓
            STEP 3  final synthesis agent
                       ↓
                    FINAL REPORT
        """

        run_start = time.time()

        self._log("=" * 60)
        self._log(f"Starting coordinator run for topic:\n{topic}")
        self._log("=" * 60)

        # STEP 1 - research plan
        plan = await self.plan_research(topic)

        # STEP 2 - this await does NOT return until every agent is done
        findings = await self.run_subagents_parallel(plan)

        # Validate research results
        failed = [
            finding["subagent"]
            for finding in findings
            if finding["is_error"]
        ]

        successful_count = len(findings) - len(failed)

        if failed:
            self._log(
                f"[COORDINATOR] Research complete: "
                f"{successful_count}/{len(findings)} successful."
            )
            self._log(f"[COORDINATOR] Failed agents: {failed}")
        else:
            self._log(
                f"[COORDINATOR] ALL {len(findings)} research agents "
                f"completed successfully."
            )

        # STEP 3 - only now start synthesis
        aggregation = await self.aggregate(topic=topic, findings=findings)

        total_elapsed = time.time() - run_start

        self._log("=" * 60)
        self._log(f"Complete coordinator run finished in {total_elapsed:.1f}s")
        self._log("=" * 60)

        return {
            "topic": topic,
            "plan": plan,
            "findings": findings,
            "failed_subtasks": failed,
            "successful_subtasks": successful_count,
            "total_subtasks": len(findings),
            "report": (
                aggregation["report"]
                if not aggregation["is_error"]
                else None
            ),
            "report_is_error": aggregation["is_error"],
        }


# ============================================================================
# Main
# ============================================================================

async def main(topic: str) -> dict:

    agent = AsyncCoordinatorAgent()

    try:
        return await agent.run(topic)
    finally:
        await agent.client.close()


if __name__ == "__main__":

    TOPIC = "renewable energy technologies"
    # Other topics tried:
    #   "renewable energy technologies"
    # "The impact of remote work on urban commercial real estate"

    result = asyncio.run(main(TOPIC))

    print("\n\n")
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    print(json.dumps(result, indent=2, ensure_ascii=False))