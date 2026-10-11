import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from PIL import Image

class ArchiveCompletion(unittest.TestCase):
    def jpeg(self):
        out=io.BytesIO();Image.new('RGB',(32,32),'red').save(out,'JPEG');return out.getvalue()
    def test_waits_for_video_tail_after_inference_stop(self):
        from vision_app.semantic_media import SemanticArchive
        with tempfile.TemporaryDirectory() as d:
            a=SemanticArchive(Path(d)/'record',[],1)
            a.feed_frame(dict(frame_id=0,capture_monotonic=100,width=32,height=32),self.jpeg())
            a.finish_at(1);time.sleep(.15);self.assertFalse(a.closed.is_set())
            a.feed_frame(dict(frame_id=1,capture_monotonic=100.1,width=32,height=32),self.jpeg())
            self.assertTrue(a.closed.wait(3))
            report=json.loads((a.path/'session.json').read_text())
            self.assertTrue(report['ok']);self.assertEqual(report['last_saved_frame_id'],1)
    def test_missing_frame_is_not_complete_and_disk_failure_cannot_trap_ui(self):
        from vision_app.semantic_media import SemanticArchive
        with tempfile.TemporaryDirectory() as d:
            updates=[]
            a=SemanticArchive(Path(d)/'record',[],1,on_update=updates.append)
            a.feed_frame(dict(frame_id=0,capture_monotonic=100,width=32,height=32),self.jpeg())
            a.feed_frame(dict(frame_id=2,capture_monotonic=100.1,width=32,height=32),self.jpeg())
            with patch.object(Path,'write_text',side_effect=OSError('disk full')):
                a.finish_at(2);self.assertTrue(a.closed.wait(3))
                time.sleep(.05)
            self.assertFalse(updates[-1]['ok']);self.assertTrue(updates[-1]['done'])
    def test_subscriber_overflow_is_visible(self):
        from vision_app.state import LatestSlot
        slot=LatestSlot();queue,overflow=slot.subscribe(2)
        for i in range(3):slot.publish(i)
        self.assertTrue(overflow.is_set());self.assertEqual([queue.get_nowait(),queue.get_nowait()],[0,1])
        slot.unsubscribe(queue);self.assertFalse(slot.subscribers)
