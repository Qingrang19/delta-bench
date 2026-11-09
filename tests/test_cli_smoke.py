"""Exercise the real module entry point without third-party test runners."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CLISmokeTests(unittest.TestCase):
    def run_cli(self, candidate, *extra):
        return subprocess.run(
            [sys.executable, '-m', 'delta_bench', 'examples/baseline.csv', candidate,
             '--key', 'frame', '--columns', 'conductivity,residual',
             '--atol', '0.0001', '--rtol', '0.001', *extra],
            cwd=ROOT, text=True, capture_output=True, check=False)

    def test_passing_example_exit_zero(self):
        run = self.run_cli('examples/candidate-pass.csv')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)['passed'])

    def test_failing_example_exit_one(self):
        run = self.run_cli('examples/candidate-fail.csv')
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertFalse(json.loads(run.stdout)['passed'])

    def test_invalid_input_exit_two(self):
        run = self.run_cli('examples/candidate-pass.csv', '--atol', '-1')
        self.assertEqual(run.returncode, 2)
        self.assertIn('error', json.loads(run.stderr))
        self.assertEqual(run.stdout, '')


if __name__ == '__main__':
    unittest.main()
