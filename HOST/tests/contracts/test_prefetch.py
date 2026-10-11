import threading
import time
import unittest


class PrefetchContract(unittest.TestCase):
    def test_bounded_and_ordered_no_duplicates(self):
        from vision_app.prefetch import BoundedPrefetch
        pulled = []
        def source():
            for value in range(7):
                pulled.append(value)
                yield value
        with BoundedPrefetch(source(), capacity=2) as prepared:
            time.sleep(.05)
            self.assertEqual(pulled, [0,1])
            self.assertEqual(list(prepared), list(range(7)))
        self.assertFalse(prepared.thread.is_alive())

    def test_error_propagates_and_early_close_stops(self):
        from vision_app.prefetch import BoundedPrefetch
        def failed():
            yield 1
            raise ValueError('decoder failed')
        with BoundedPrefetch(failed()) as prepared:
            self.assertEqual(next(prepared), 1)
            with self.assertRaisesRegex(ValueError, 'decoder failed'):
                next(prepared)
        with BoundedPrefetch(iter(range(100000))) as prepared:
            self.assertEqual(next(prepared), 0)
        self.assertFalse(prepared.thread.is_alive())
