"""Shared allocation model. Addresses are inclusive; sizes are simulated bytes."""
from dataclasses import asdict, dataclass
import re


class AllocationError(ValueError):
    """Invalid request; the model remains unchanged."""


@dataclass(frozen=True)
class Block:
    start: int
    size: int
    pid: str | None = None

    @property
    def end(self):
        return self.start + self.size - 1


class Allocator:
    def __init__(self, total: int):
        if type(total) is not int or not 1 <= total <= 2**63 - 1:
            raise AllocationError("Санах ойн хэмжээ 1..2^63-1 бүхэл тоо байна.")
        self.total = total
        self._blocks = [Block(0, total)]

    @property
    def blocks(self):
        return tuple(self._blocks)

    def request(self, pid: str, size: int, strategy: str):
        if not isinstance(pid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", pid):
            raise AllocationError("PID: үсгээр эхэлсэн 1-32 латин үсэг, цифр, _ байна.")
        if any(b.pid == pid for b in self._blocks):
            raise AllocationError(f"{pid} процесс аль хэдийн санах ой эзэмшиж байна.")
        if type(size) is not int or size <= 0:
            raise AllocationError("Хүсэлтийн хэмжээ эерэг бүхэл тоо байна.")
        if strategy not in ("F", "B", "W"):
            raise AllocationError("Стратеги F (first), B (best), W (worst) байна.")
        candidates = [(i, b) for i, b in enumerate(self._blocks)
                      if b.pid is None and b.size >= size]
        if not candidates:
            free = self.stats()["free"]
            if free >= size:
                raise AllocationError("Нийт сул зай хүрэлцээтэй ч залгаа hole хүрэлцэхгүй. C командаар нягтруулж болно.")
            raise AllocationError(f"Сул санах ой хүрэлцэхгүй: хүсэлт {size}, сул {free}.")
        if strategy == "F":
            index, hole = candidates[0]
        elif strategy == "B":
            index, hole = min(candidates, key=lambda x: (x[1].size, x[1].start))
        else:
            index, hole = min(candidates, key=lambda x: (-x[1].size, x[1].start))
        allocated = Block(hole.start, size, pid)
        replacement = [allocated]
        if hole.size > size:
            replacement.append(Block(hole.start + size, hole.size - size))
        self._blocks[index:index + 1] = replacement
        self.check_invariants()
        return allocated

    def release(self, pid: str):
        if not any(b.pid == pid for b in self._blocks) or pid is None:
            raise AllocationError(f"{pid} процесс олдсонгүй.")
        merged = []
        for block in self._blocks:
            current = Block(block.start, block.size) if block.pid == pid else block
            if merged and merged[-1].pid is None and current.pid is None:
                previous = merged.pop()
                merged.append(Block(previous.start, previous.size + current.size))
            else:
                merged.append(current)
        self._blocks = merged
        self.check_invariants()

    def compact(self):
        cursor, result, moves = 0, [], []
        for block in self._blocks:
            if block.pid is not None:
                result.append(Block(cursor, block.size, block.pid))
                if cursor != block.start:
                    moves.append({"pid": block.pid, "from": block.start, "to": cursor,
                                  "size": block.size})
                cursor += block.size
        if cursor < self.total:
            result.append(Block(cursor, self.total - cursor))
        self._blocks = result
        self.check_invariants()
        return moves

    def stats(self):
        holes = [b.size for b in self._blocks if b.pid is None]
        free = sum(holes)
        largest = max(holes, default=0)
        return {"total": self.total, "used": self.total - free, "free": free,
                "holes": len(holes), "largest_hole": largest,
                "fragmentation": 0.0 if not free else 1 - largest / free}

    def snapshot(self):
        return {"stats": self.stats(),
                "blocks": [dict(asdict(b), end=b.end) for b in self._blocks]}

    def status(self):
        return "\n".join(f"Addresses [{b.start}:{b.end}] " +
                         (f"Process {b.pid}" if b.pid else "Unused") for b in self._blocks)

    def check_invariants(self):
        cursor, previous_free, pids = 0, False, set()
        for block in self._blocks:
            assert block.start == cursor and block.size > 0
            assert not (previous_free and block.pid is None)
            if block.pid is not None:
                assert block.pid not in pids
                pids.add(block.pid)
            previous_free = block.pid is None
            cursor += block.size
        assert cursor == self.total


def execute(model: Allocator, command: str):
    """Return message and exit flag. Invalid commands never mutate the model."""
    parts = command.split()
    if not parts:
        raise AllocationError("Команд оруулна уу: RQ / RL / C / STAT / X.")
    op = parts[0].upper()
    if op == "RQ" and len(parts) == 4:
        try:
            size = int(parts[2])
        except ValueError:
            raise AllocationError("Хүсэлтийн хэмжээ бүхэл тоо байна.") from None
        b = model.request(parts[1], size, parts[3].upper())
        return f"{b.pid}: [{b.start}:{b.end}], {b.size} bytes", False
    if op == "RL" and len(parts) == 2:
        model.release(parts[1])
        return f"{parts[1]} чөлөөлөгдлөө; хөрш hole-ууд нэгтгэгдлээ.", False
    if op == "C" and len(parts) == 1:
        moves = model.compact()
        details = "; ".join(f"{m['pid']}: {m['from']} -> {m['to']}" for m in moves)
        return f"Нягтрууллаа. Шилжсэн процесс: {len(moves)}. {details}", False
    if op == "STAT" and len(parts) == 1:
        return model.status(), False
    if op == "X" and len(parts) == 1:
        return "Программ дууслаа.", True
    raise AllocationError("Зөв хэлбэр: RQ P0 100 F | RL P0 | C | STAT | X")
