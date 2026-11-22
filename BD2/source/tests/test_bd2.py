"""Regression tests for Memory Lab 2 previews, lessons and UTF-8 input."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from src.allocator import Allocator, AllocationError, execute
from src.preview import compare_request
from src.scenarios import SCENARIOS


def scenario_model(key, count=None):
    spec = SCENARIOS[key]
    model = Allocator(spec['total'])
    results = []
    for command, _ in spec['steps'][:count]:
        try:
            execute(model, command)
            results.append(True)
        except AllocationError:
            results.append(False)
    return model, results


class PreviewTests(unittest.TestCase):
    def test_three_strategies_same_state(self):
        model, _ = scenario_model('strategies')
        before = model.snapshot()
        rows = compare_request(model, 'Q', 150)
        self.assertEqual([r['start'] for r in rows], [0, 500, 900])
        self.assertEqual([r['remainder'] for r in rows], [250, 50, 450])
        self.assertEqual(model.snapshot(), before)

    def test_preview_matches_real_allocation(self):
        for strategy in 'FBW':
            model, _ = scenario_model('strategies')
            row = next(r for r in compare_request(model, 'Q', 150) if r['strategy'] == strategy)
            allocated = model.request('Q', 150, strategy)
            self.assertEqual((allocated.start, allocated.end), (row['start'], row['end']))
            self.assertEqual(model.stats(), row['stats_after'])

    def test_invalid_previews_do_not_mutate(self):
        model, _ = scenario_model('strategies')
        before = model.snapshot()
        for pid, size in [('A', 50), ('bad pid', 5), ('Q', 0), ('Q', -1), ('Q', True), ('Q', 2000)]:
            with self.subTest(pid=pid, size=size):
                self.assertTrue(all(not row['ok'] for row in compare_request(model, pid, size)))
                self.assertEqual(model.snapshot(), before)

    def test_fragmentation_preview_then_compaction(self):
        model, _ = scenario_model('fragmentation', 4)
        self.assertTrue(all(not r['ok'] for r in compare_request(model, 'P3', 400)))
        model.compact()
        self.assertTrue(all(r['start'] == 500 for r in compare_request(model, 'P3', 400)))

    def test_exact_fit_has_zero_remainder(self):
        rows = compare_request(Allocator(1), 'A', 1)
        self.assertTrue(all(r['end'] == 0 and r['remainder'] == 0 for r in rows))


class ScenarioTests(unittest.TestCase):
    def test_fragmentation_expected_failure_and_recovery(self):
        model, results = scenario_model('fragmentation')
        self.assertEqual(results, [True, True, True, True, False, True, True, True])
        self.assertEqual(model.stats()['used'], 900)
        self.assertEqual(model.stats()['largest_hole'], 100)

    def test_full_memory_and_coalescing(self):
        full, _ = scenario_model('boundary', 2)
        self.assertEqual(full.stats()['free'], 0)
        self.assertEqual(full.stats()['fragmentation'], 0)
        model, results = scenario_model('boundary')
        self.assertEqual(results, [True, True, False, True, True, True])
        self.assertEqual(model.blocks, Allocator(100).blocks)

    def test_replay_every_prefix_is_deterministic(self):
        for key, spec in SCENARIOS.items():
            for count in range(len(spec['steps']) + 1):
                a, _ = scenario_model(key, count)
                b, _ = scenario_model(key, count)
                self.assertEqual(a.snapshot(), b.snapshot())
                a.check_invariants()


class InputEncodingTests(unittest.TestCase):
    def run_file(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'commands.txt'
            path.write_bytes(data)
            return subprocess.run([sys.executable, '-m', 'src.cli', '100', '--file', str(path)], capture_output=True, text=True)

    def test_invalid_utf8_friendly_error(self):
        result = self.run_file(b'\xff\xfe\x00')
        self.assertEqual(result.returncode, 2)
        self.assertIn('UTF-8', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_utf8_bom_supported(self):
        result = self.run_file('\ufeffRQ A 10 F\nSTAT\n'.encode('utf-8'))
        self.assertEqual(result.returncode, 0)
        self.assertIn('Process A', result.stdout)

    def test_utf8_comments_supported(self):
        result = self.run_file('# Монгол тайлбар\nRQ A 10 F\nX\n'.encode('utf-8'))
        self.assertEqual(result.returncode, 0)

    def test_missing_file_no_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-m', 'src.cli', '100', '--file', str(Path(directory)/'missing')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
