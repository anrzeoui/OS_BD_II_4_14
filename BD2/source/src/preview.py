"""Allocation previews reuse the model on an isolated copy."""
from copy import deepcopy
from .allocator import AllocationError


def compare_request(model, pid, size):
    """Evaluate F/B/W against the same input state without changing it."""
    rows = []
    for strategy in "FBW":
        trial = deepcopy(model)
        try:
            block = trial.request(pid, size, strategy)
            hole = next(b for b in model.blocks if b.start == block.start)
            rows.append({"strategy": strategy, "ok": True,
                         "start": block.start, "end": block.end,
                         "hole_size": hole.size, "remainder": hole.size - size,
                         "stats_after": trial.stats()})
        except AllocationError as exc:
            rows.append({"strategy": strategy, "ok": False, "message": str(exc)})
    return rows
