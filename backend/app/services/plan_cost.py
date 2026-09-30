"""What the planner expects a query to cost, from EXPLAIN (FORMAT JSON)."""
import json
from typing import Any, List, Mapping, Optional, Tuple


def plan_cost(rows: List[Mapping[str, Any]]) -> Optional[Tuple[float, int]]:
    """(total cost, estimated rows), or None when the plan cannot be read."""
    try:
        plan = rows[0]["QUERY PLAN"]
        if isinstance(plan, str):
            plan = json.loads(plan)
        top = plan[0]["Plan"]
        return float(top["Total Cost"]), int(top["Plan Rows"])
    except Exception:
        return None
