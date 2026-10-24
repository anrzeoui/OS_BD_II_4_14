import random
import subprocess
import sys
import unittest
from pathlib import Path
from src.allocator import Allocator, AllocationError, execute


def strategy_fixture():
    a = Allocator(1500)
    for pid, size in [("P0", 400), ("A", 100), ("P1", 200), ("B", 200)]:
        a.request(pid, size, "F")
    a.release("P0")
    a.release("P1")
    return a


class AllocationTests(unittest.TestCase):
    def test_book_example(self):
        a = Allocator(1048576)
        b = a.request("P0", 40000, "W")
        self.assertEqual((b.start, b.end), (0, 39999))
        self.assertEqual(a.blocks[1].size, 1008576)

    def test_first_fit(self):
        self.assertEqual(strategy_fixture().request("Q", 150, "F").start, 0)

    def test_best_fit(self):
        self.assertEqual(strategy_fixture().request("Q", 150, "B").start, 500)

    def test_worst_fit(self):
        self.assertEqual(strategy_fixture().request("Q", 150, "W").start, 900)

    def test_ties_choose_low_address(self):
        for strategy in ("F", "B", "W"):
            a = Allocator(500)
            for i in range(5):
                a.request(f"P{i}", 100, "F")
            a.release("P0")
            a.release("P2")
            self.assertEqual(a.request("Q", 50, strategy).start, 0)

    def test_merge_both_neighbors(self):
        a = Allocator(1000)
        for i in range(3):
            a.request(f"P{i}", 200, "F")
        a.release("P0")
        a.release("P2")
        a.release("P1")
        self.assertEqual([(b.start, b.size, b.pid) for b in a.blocks], [(0, 1000, None)])

    def test_fragmentation_and_compaction(self):
        a = Allocator(1000)
        for pid, size in [("P0", 300), ("P1", 200), ("P2", 300)]:
            a.request(pid, size, "F")
        a.release("P0")
        self.assertEqual((a.stats()["free"], a.stats()["largest_hole"]), (500, 300))
        before = a.snapshot()
        with self.assertRaises(AllocationError):
            a.request("P3", 400, "F")
        self.assertEqual(a.snapshot(), before)
        moves = a.compact()
        self.assertEqual([(m["pid"], m["from"], m["to"]) for m in moves],
                         [("P1", 300, 0), ("P2", 500, 200)])
        self.assertEqual(a.request("P3", 400, "F").start, 500)
        self.assertEqual((a.stats()["used"], a.stats()["free"]), (900, 100))

    def test_exact_fit_full_empty_and_one_byte(self):
        a = Allocator(1)
        a.request("P", 1, "B")
        self.assertEqual(a.stats()["holes"], 0)
        self.assertEqual(a.stats()["fragmentation"], 0)
        self.assertEqual(a.compact(), [])
        with self.assertRaises(AllocationError):
            a.request("Q", 1, "F")
        a.release("P")
        self.assertEqual(a.compact(), [])
        self.assertEqual(a.status(), "Addresses [0:0] Unused")

    def test_invalid_total(self):
        for total in (0, -1, 1.5, True, 2**63):
            with self.subTest(total=total), self.assertRaises(AllocationError):
                Allocator(total)

    def test_invalid_requests_atomic(self):
        a = Allocator(100)
        a.request("P0", 20, "F")
        cases = [("P0", 1, "F"), ("P1", 0, "F"), ("P1", -1, "F"),
                 ("P1", 1.5, "F"), ("P1", True, "F"), ("P1", 1, "Z"),
                 ("bad id", 1, "F"), ("1bad", 1, "F"), ("P1", 101, "F")]
        before = a.snapshot()
        for params in cases:
            with self.subTest(params=params), self.assertRaises(AllocationError):
                a.request(*params)
            self.assertEqual(a.snapshot(), before)

    def test_unknown_release_atomic(self):
        a = Allocator(10)
        before = a.snapshot()
        for pid in ("P99", None):
            with self.assertRaises(AllocationError):
                a.release(pid)
            self.assertEqual(a.snapshot(), before)

    def test_command_validation(self):
        a = Allocator(100)
        before = a.snapshot()
        for command in ("", "RQ", "RQ P0 abc F", "RQ P0 1 F EXTRA", "RL", "C EXTRA", "X extra", "WHAT"):
            with self.subTest(command=command), self.assertRaises(AllocationError):
                execute(a, command)
            self.assertEqual(a.snapshot(), before)
        execute(a, "rq P0 10 b")
        self.assertIn("[0:9] Process P0", execute(a, "STAT")[0])
        self.assertTrue(execute(a, "X")[1])

    def test_compaction_preserves_order_sizes_and_is_idempotent(self):
        a = strategy_fixture()
        allocated = [(b.pid, b.size) for b in a.blocks if b.pid]
        a.compact()
        self.assertEqual([(b.pid, b.size) for b in a.blocks if b.pid], allocated)
        self.assertEqual(a.stats()["holes"], 1)
        before = a.snapshot()
        self.assertEqual(a.compact(), [])
        self.assertEqual(a.snapshot(), before)

    def test_large_addresses(self):
        a = Allocator(2**63 - 1)
        a.request("P", 2**63 - 2, "W")
        self.assertEqual(a.request("Q", 1, "B").end, 2**63 - 2)

    def test_randomized_independent_byte_oracle(self):
        # Independent per-byte occupancy oracle, not the allocator's block logic.
        rng = random.Random(14)
        a, memory = Allocator(97), [None] * 97
        for step in range(2000):
            action = rng.choice(("rq", "rq", "rl", "c"))
            active = sorted(set(x for x in memory if x))
            if action == "rq":
                size, strategy, pid = rng.randint(1, 40), rng.choice("FBW"), f"P{step}"
                holes, i = [], 0
                while i < len(memory):
                    if memory[i] is not None:
                        i += 1
                        continue
                    start = i
                    while i < len(memory) and memory[i] is None:
                        i += 1
                    if i - start >= size:
                        holes.append((start, i - start))
                if not holes:
                    with self.assertRaises(AllocationError):
                        a.request(pid, size, strategy)
                else:
                    if strategy == "F":
                        start = holes[0][0]
                    else:
                        start = min(holes, key=lambda h: (h[1] if strategy == "B" else -h[1], h[0]))[0]
                    self.assertEqual(a.request(pid, size, strategy).start, start)
                    memory[start:start + size] = [pid] * size
            elif action == "rl" and active:
                pid = rng.choice(active)
                a.release(pid)
                memory = [None if x == pid else x for x in memory]
            elif action == "c":
                a.compact()
                used = [x for x in memory if x is not None]
                memory = used + [None] * (97 - len(used))
            actual = [b.pid for b in a.blocks for _ in range(b.size)]
            self.assertEqual(actual, memory, f"step {step}")
            a.check_invariants()

    def test_cli_book_script(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-m", "src.cli", "1048576", "--file", "examples/book.txt"],
                                cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Addresses [0:39999] Process P0", result.stdout)
        self.assertIn("Addresses [0:1048575] Unused", result.stdout)

    def test_cli_error_script_keeps_running(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-m", "src.cli", "1000", "--file", "examples/fragmentation.txt"],
                                cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR:", result.stdout)
        self.assertIn("Addresses [500:899] Process P3", result.stdout)


if __name__ == "__main__":
    unittest.main()
