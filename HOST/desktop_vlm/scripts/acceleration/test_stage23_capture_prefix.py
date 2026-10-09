"""Synthetic fail-closed checker tests; these are not hardware captures."""
import csv
import tempfile
import unittest
from pathlib import Path

from desktop_vlm.scripts.acceleration.check_stage23_capture_prefix import inspect, packet


class CaptureGateTests(unittest.TestCase):
    def run_case(self, side='out', fault=None):
        depth, position = 1024, 256
        names = ['reset_heartbeat[31:0]', 'reset_rst',
                 'core_reset_sync_peripheral_aresetn[0:0]',
                 'datapath_protocol_error', 'ctrl_debug_status[6:0]',
                 'ctrl_core_mode[31:0]', 'ctrl_core_start_pulse']
        names += ['probe_%s_mon_%s' % (side, suffix) for suffix in
                  ('tvalid', 'tready', 'tdata[63:0]', 'tkeep[7:0]', 'tlast')]
        payload = packet(3, side, 0)[0]
        first = position if side == 'out' else position + 10
        with tempfile.TemporaryDirectory() as directory:
            native = Path(directory) / 'synthetic.ila'
            native.write_bytes(b'SYNTHETIC_CHECKER_TEST_NOT_NATIVE_ILA')
            path = Path(directory) / 'synthetic.csv'
            rows = []
            for i in range(depth):
                active = first <= i < first + 8
                offset = (i - first) * 8
                word = int.from_bytes(payload[offset:offset + 8], 'little') if active else 0
                if fault == 'payload' and i == first + 2:
                    word ^= 1
                values = [i, int(fault == 'reset' and i == 500), 1, 0, 0, 3,
                          int(side == 'in' and i == position),
                          int(active), 1, word, 255 if active else 0,
                          int(fault == 'early_last' and i == first)]
                if fault == 'missed_prefix' and i == first - 1:
                    values[7] = 1
                rows.append([i, i] + [format(value, 'X') for value in values])
            with path.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['Sample in Buffer', 'Sample in Window'] + ['dma_shell_i/' + n for n in names])
                writer.writerow(['DEC', 'DEC'] + ['HEX'] * len(names))
                writer.writerows(rows)
            return inspect(path, native, 3, side, 0, depth, position)

    def test_input_prefix_only(self):
        result = self.run_case('in')
        self.assertEqual(result['bytes_checked'], 64)
        self.assertFalse(result['full_packet_captured'])

    def test_output_prefix_only(self):
        self.assertEqual(self.run_case()['first_handshake_sample'], 256)

    def test_corrupt_payload_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Payload mismatch'):
            self.run_case(fault='payload')

    def test_early_last_rejected(self):
        with self.assertRaisesRegex(ValueError, 'TLAST mismatch'):
            self.run_case(fault='early_last')

    def test_reset_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Reset during'):
            self.run_case(fault='reset')

    def test_missed_output_prefix_rejected(self):
        with self.assertRaisesRegex(ValueError, 'first TVALID'):
            self.run_case(fault='missed_prefix')


if __name__ == '__main__':
    unittest.main()
