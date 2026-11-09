import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from delta_bench.core import compare, InputError
from delta_bench.report import render_html
from delta_bench.__main__ import main


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.root / 'a.csv'
        self.b = self.root / 'b.csv'
        self.a.write_text('id,x\na,1\nb,2\n')
        self.b.write_text('id,x\nb,2\na,1\n')

    def compare(self, **kwargs):
        return compare(self.a, self.b, 'id', ['x'], **kwargs)

    def test_reordering(self):
        self.assertTrue(self.compare()['passed'])

    def test_metrics(self):
        self.b.write_text('id,x\na,4\nb,6\n')
        report = self.compare()
        stats = report['columns']['x']
        self.assertEqual(stats['mae'], 3.5)
        self.assertAlmostEqual(stats['rmse'], (12.5)**0.5)
        self.assertEqual(stats['max_difference'], 4)
        self.assertEqual(len(report['mismatches']), 2)

    def test_absolute_boundary(self):
        self.b.write_text('id,x\na,2\nb,3\n')
        self.assertTrue(self.compare(atol=1)['passed'])

    def test_relative_baseline_reference(self):
        self.a.write_text('id,x\na,100\n')
        self.b.write_text('id,x\na,111\n')
        self.assertFalse(self.compare(rtol=.1)['passed'])

    def test_combined_tolerance(self):
        self.a.write_text('id,x\na,100\n')
        self.b.write_text('id,x\na,112\n')
        self.assertTrue(self.compare(atol=2, rtol=.1)['passed'])

    def test_zero_baseline(self):
        self.a.write_text('id,x\na,0\n')
        self.b.write_text('id,x\na,0.1\n')
        self.assertFalse(self.compare(rtol=1)['passed'])

    def test_missing_and_additional(self):
        self.b.write_text('id,x\na,1\nc,2\n')
        report = self.compare()
        self.assertFalse(report['passed'])
        self.assertEqual(report['missing_rows'], ['b'])
        self.assertEqual(report['additional_rows'], ['c'])

    def test_duplicate_keys(self):
        self.b.write_text('id,x\na,1\na,2\n')
        with self.assertRaises(InputError): self.compare()

    def test_nonfinite_unmatched(self):
        for value in ('nan', 'inf', '-inf', '1e999'):
            with self.subTest(value=value):
                self.b.write_text(f'id,x\nc,{value}\n')
                with self.assertRaises(InputError): self.compare()

    def test_bad_number(self):
        self.b.write_text('id,x\na,nope\n')
        with self.assertRaises(InputError): self.compare()

    def test_missing_column(self):
        self.b.write_text('id,y\na,1\n')
        with self.assertRaises(InputError): self.compare()

    def test_duplicate_header(self):
        self.b.write_text('id,x,x\na,1,1\n')
        with self.assertRaises(InputError): self.compare()

    def test_empty_file_and_header_only(self):
        for content in ('', 'id,x\n'):
            self.b.write_text(content)
            with self.assertRaises(InputError): self.compare()

    def test_ragged_row(self):
        for content in ('id,x\na\n', 'id,x\na,1,2\n'):
            self.b.write_text(content)
            with self.assertRaises(InputError): self.compare()

    def test_empty_key(self):
        self.b.write_text('id,x\n,1\n')
        with self.assertRaises(InputError): self.compare()

    def test_invalid_tolerances(self):
        for value in (-1, float('nan'), float('inf')):
            with self.assertRaises(InputError): self.compare(atol=value)

    def test_invalid_column_selection(self):
        for columns in ([], ['x', 'x'], ['id']):
            with self.assertRaises(InputError): compare(self.a, self.b, 'id', columns)

    def test_no_common_keys(self):
        self.b.write_text('id,x\nc,1\n')
        report = self.compare()
        self.assertFalse(report['passed'])
        self.assertIsNone(report['columns']['x']['mae'])

    def test_overflow_is_rejected(self):
        self.a.write_text('id,x\na,-1e308\n')
        self.b.write_text('id,x\na,1e308\n')
        with self.assertRaises(InputError): self.compare()

    def test_html_escaping(self):
        result = self.compare()
        result['baseline'] = '</pre><script>alert("x")</script>'
        rendered = render_html(result)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_cli_writes_reports(self):
        out, html = self.root / 'result.json', self.root / 'result.html'
        with contextlib.redirect_stdout(io.StringIO()):
            code = main([str(self.a), str(self.b), '--key', 'id', '--columns', 'x',
                         '--json', str(out), '--html', str(html)])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out.read_text())['passed'])
        self.assertIn('PASS', html.read_text())

    def test_cli_hard_link_input_protection(self):
        out = self.root / 'linked.json'
        try:
            out.hardlink_to(self.a)
        except OSError as exc:
            self.skipTest(str(exc))
        original = self.a.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            code = main([str(self.a), str(self.b), '--key', 'id', '--columns', 'x',
                         '--json', str(out)])
        self.assertEqual(code, 2)
        self.assertEqual(self.a.read_bytes(), original)

    def test_cli_hard_link_reports_protection(self):
        out, html = self.root / 'out.json', self.root / 'out.html'
        out.write_text('existing')
        try:
            html.hardlink_to(out)
        except OSError as exc:
            self.skipTest(str(exc))
        with contextlib.redirect_stderr(io.StringIO()):
            code = main([str(self.a), str(self.b), '--key', 'id', '--columns', 'x',
                         '--json', str(out), '--html', str(html)])
        self.assertEqual(code, 2)
        self.assertEqual(out.read_text(), 'existing')

    def test_cli_error_and_overwrite_protection(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code = main([str(self.a), str(self.b), '--key', 'id', '--columns', 'x',
                         '--json', str(self.a)])
        self.assertEqual(code, 2)
        self.assertTrue(self.a.read_text().startswith('id,x'))


if __name__ == '__main__':
    unittest.main()
