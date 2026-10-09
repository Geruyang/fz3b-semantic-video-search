import pathlib
import sys
import threading
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from cnn_pipeline_v10_delivery import V10ResultDelivery


class DeliveryTests(unittest.TestCase):
    def test_ordered_delivery_overlaps_producer_and_drains(self):
        entered, release = threading.Event(), threading.Event()
        received = []
        def emit(value):
            entered.set()
            self.assertTrue(release.wait(2))
            received.append(value)
        delivery = V10ResultDelivery(emit, 2)
        try:
            delivery.submit(0)
            self.assertTrue(entered.wait(2))
            delivery.submit(1)
            delivery.submit(2)
            self.assertEqual(received, [])
            release.set()
            summary = delivery.close()
            self.assertEqual(received, [0, 1, 2])
            self.assertEqual(summary['delivered'], 3)
            self.assertEqual(summary['status'], 'DRAINED')
            self.assertLessEqual(summary['queue_high_water'], 2)
            with self.assertRaisesRegex(RuntimeError, 'closed'):
                delivery.submit(3)
        finally:
            release.set()
            delivery.close()

    def test_slow_sink_backpressures_without_unbounded_buffering(self):
        entered, release, submitted = threading.Event(), threading.Event(), threading.Event()
        def emit(value):
            entered.set()
            self.assertTrue(release.wait(2))
        delivery = V10ResultDelivery(emit, 1)
        delivery.submit(0)
        self.assertTrue(entered.wait(2))
        delivery.submit(1)
        producer = threading.Thread(target=lambda: (delivery.submit(2), submitted.set()))
        producer.start()
        try:
            self.assertFalse(submitted.wait(.03))
            release.set()
            producer.join(2)
            self.assertFalse(producer.is_alive())
            self.assertEqual(delivery.close()['delivered'], 3)
        finally:
            release.set()
            producer.join(2)
            delivery.close()

    def test_callback_failure_unblocks_full_queue_and_is_reported(self):
        entered, release = threading.Event(), threading.Event()
        def emit(value):
            entered.set()
            self.assertTrue(release.wait(2))
            raise ValueError('sink unavailable')
        delivery = V10ResultDelivery(emit, 1)
        delivery.submit(0)
        self.assertTrue(entered.wait(2))
        delivery.submit(1)
        release.set()
        with self.assertRaisesRegex(RuntimeError, 'delivery failed'):
            delivery.submit(2)
        with self.assertRaisesRegex(RuntimeError, 'delivery failed'):
            delivery.close()
        self.assertEqual(delivery.summary()['status'], 'FAILED')
        self.assertEqual(delivery.summary()['delivered'], 0)
        self.assertFalse(delivery._thread.is_alive())


if __name__ == '__main__':
    unittest.main()
