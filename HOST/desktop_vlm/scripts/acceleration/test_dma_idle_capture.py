"""Synthetic checks of the parser/gate, never board evidence."""
import csv
from pathlib import Path
import tempfile
import unittest

from check_dma_idle_capture import EXPECTED_IDLE, HEARTBEAT, inspect_capture


class IdleGateTests(unittest.TestCase):
    def fixture(self, directory, reset=1, frozen_clock=False, unknown=False):
        capture = Path(directory) / 'synthetic.csv'
        native = Path(directory) / 'synthetic.ila'
        native.write_bytes(b'UNIT TEST PLACEHOLDER NOT NATIVE ILA')
        header = ['Sample in Buffer', 'Sample in Window', HEARTBEAT] + list(EXPECTED_IDLE)
        with capture.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerow(['Radix - UNSIGNED', 'UNSIGNED'] + ['HEX'] * (len(header) - 2))
            for sample in range(8192):
                signals = dict(EXPECTED_IDLE)
                signals['dma_shell_i/core_reset_sync_peripheral_aresetn[0:0]'] = reset
                clock = 0 if frozen_clock else (0xfffff000 + sample) & 0xffffffff
                writer.writerow([sample, sample, 'XXXX' if unknown else format(clock, 'x')] +
                                [format(value, 'x') for value in signals.values()])
        return capture, native

    def test_idle_and_heartbeat_wrap(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inspect_capture(*self.fixture(folder))
        self.assertEqual(result['status'], 'IDLE_CAPTURE_GATE_PASS')

    def test_asserted_data_reset_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inspect_capture(*self.fixture(folder, reset=0))
        self.assertEqual(result['status'], 'IDLE_CAPTURE_GATE_FAIL_DO_NOT_BIND')

    def test_stalled_clock_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inspect_capture(*self.fixture(folder, frozen_clock=True))
        self.assertTrue(any('heartbeat' in failure for failure in result['failures']))

    def test_unknown_clock_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                inspect_capture(*self.fixture(folder, unknown=True))


if __name__ == '__main__':
    unittest.main()
