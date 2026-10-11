import unittest

class UploadSourceContract(unittest.TestCase):
    def test_order_extent_backpressure_and_eof(self):
        from vision_app.upload_source import UploadSource
        job=UploadSource('job',capacity=2)
        job.put({'frame_id':0,'video_time_s':0.0},b'jpeg')
        with self.assertRaises(ValueError):job.put({'frame_id':2,'video_time_s':.1},b'jpeg')
        job.put({'frame_id':1,'video_time_s':.1},b'jpeg')
        with self.assertRaises(ValueError):job.put({'frame_id':2,'video_time_s':.2},b'jpeg')
        frame=job.take(.01);self.assertEqual(frame['frame_id'],0)
        job.push_back(frame);self.assertEqual(job.take(.01)['frame_id'],0)
        self.assertEqual(job.take(.01)['frame_id'],1)
        job.finish(2);self.assertIsNone(job.take(.01));self.assertTrue(job.exhausted)

    def test_rejects_nan_and_cancellation(self):
        from vision_app.upload_source import UploadSource
        job=UploadSource('job')
        with self.assertRaises(ValueError):job.put({'frame_id':0,'video_time_s':float('nan')},b'x')
        job.cancel()
        with self.assertRaises(ValueError):job.put({'frame_id':0,'video_time_s':0},b'x')
