"""Running an evaluation set: generate, execute, compare."""
from typing import Any, Awaitable, Callable, Dict, List, Mapping

from app.services.eval_compare import results_match

Generate = Callable[[str], Awaitable[str]]
Execute = Callable[[str], Awaitable[List[Mapping[str, Any]]]]
Progress = Callable[[int, int, List[Dict[str, Any]]], None]


def _reason(exc: Exception) -> str:
    text = str(exc).strip()
    return text.splitlines()[0][:300] if text else type(exc).__name__


async def run_evaluation(
    cases: List[Mapping[str, Any]],
    generate: Generate,
    execute: Execute,
    on_progress: Progress,
) -> List[Dict[str, Any]]:
    """Score each case. A failure — in the model, the database or the case's own
    answer — fails that case only; the others still run."""
    results: List[Dict[str, Any]] = []
    for i, case in enumerate(cases, start=1):
        entry: Dict[str, Any] = {
            "case_id": case["id"],
            "question": case["question"],
            "expected_sql": case["expected_sql"],
            "generated_sql": None,
            "passed": False,
            "reason": "",
        }
        try:
            expected = await execute(case["expected_sql"])
        except Exception as exc:
            # The case is broken, not the model: say so.
            entry["reason"] = f"정답 SQL을 실행하지 못했습니다: {_reason(exc)}"
            results.append(entry)
            on_progress(i, len(cases), results)
            continue

        try:
            entry["generated_sql"] = await generate(case["question"])
            actual = await execute(entry["generated_sql"])
            entry["passed"], entry["reason"] = results_match(expected, actual)
        except Exception as exc:
            entry["reason"] = _reason(exc)

        results.append(entry)
        on_progress(i, len(cases), results)
    return results


def summarize(results: List[Mapping[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    return {"total": total, "passed": passed, "rate": round(passed * 100 / total, 1) if total else 0.0}
