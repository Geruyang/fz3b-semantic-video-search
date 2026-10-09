"""Synthetic verifier tests only, never represented as actual board evidence."""
import copy
import unittest

from check_dw_hpm_capture import WIDTHS, check_rows


def capture():
    rows = []
    output_count = 0
    for cycle in range(8192):
        row = dict.fromkeys(WIDTHS, 0)
        row.update(heartbeat=(0xfffff800 + cycle) % (1 << 32), job_id=1,
                   weight_count=min(cycle, 49), pixel_count=min(max(cycle - 100, 0), 1024),
                   cycles=min(cycle, 2300), status=1 if cycle < 2300 else 2,
                   completed=int(cycle >= 2300))
        if 200 <= cycle < 2248 and cycle % 2 == 0:
            row.update(output_event=1, output_index=output_count, output_value=(-output_count) & 0xffffffff)
            output_count += 1
        row['output_count'] = output_count
        rows.append(row)
    return rows


class CaptureContractTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.jobs = capture(), {1: tuple(-x for x in range(1024))}

    def test_complete(self):
        result = check_rows(self.rows, self.jobs)
        self.assertEqual(result['observed_values_per_job'], {'1': 1024})

    def test_baseline(self):
        rows = [dict(dict.fromkeys(WIDTHS, 0), heartbeat=i) for i in range(8192)]
        self.assertEqual(check_rows(rows)['status'], 'PASS')

    def test_faults(self):
        mutations = [
            (210, 'output_value', 17), (210, 'output_index', 7),
            (210, 'output_event', 0), (210, 'output_count', 10),
            (210, 'heartbeat', 0), (210, 'rst', 1), (210, 'status', 5),
            (210, 'status', 3), (2300, 'weight_count', 48),
            (2300, 'completed', 0), (3000, 'completed', 2),
            (2300, 'cycles', 2299), (2000, 'cycles', 42),
            (210, 'job_id', 2), (210, 'weight_count', 50),
            (210, 'output_value', -(1 << 31) - 1),
        ]
        for sample, field, value in mutations:
            with self.subTest(sample=sample, field=field):
                rows = copy.deepcopy(self.rows)
                rows[sample][field] = value
                with self.assertRaises(ValueError):
                    check_rows(rows, self.jobs)

    def test_bus_errors(self):
        for handshake, responses in [(4, 8), (2, 2)]:
            rows = copy.deepcopy(self.rows)
            rows[210].update(handshakes=handshake, responses=responses)
            with self.assertRaises(ValueError):
                check_rows(rows, self.jobs)

    def test_incomplete(self):
        with self.assertRaises(ValueError):
            check_rows(self.rows[:2048], self.jobs, samples=2048)


if __name__ == '__main__':
    unittest.main()
