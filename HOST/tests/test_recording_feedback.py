import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from vision_app.semantic_ui import SemanticWindow

APP=QApplication.instance() or QApplication([])


class RecordingFeedback(unittest.TestCase):
    def setUp(self):
        self.window=SemanticWindow();self.window.link=SimpleNamespace(send=Mock(),close=Mock())
        self.window.status_data={'inference':{'state':'STOPPED'}}
    def tearDown(self):
        self.window.archive=None;self.window.link=None;self.window.close()

    def test_start_immediately_waits_and_encoding_failure_restores_idle(self):
        w=self.window
        with patch.object(w,'encode'):w.start_inference()
        self.assertEqual(w.start_button.text(),'等待推理…')
        self.assertEqual(w.live_state,'preparing')
        self.assertFalse(w.start_button.isEnabled())
        w.encoding_error('test error')
        self.assertEqual(w.live_state,'idle')
        self.assertTrue(w.start_button.isEnabled())

    def test_stop_success_only_after_archive_is_complete_and_notifies_once(self):
        w=self.window
        w.archive=SimpleNamespace(closed=threading.Event(),finish_at=Mock(),revision=1)
        with patch.object(w,'notify_success') as success:
            w.message(dict(type='status',inference={'state':'STARTING'}))
            self.assertEqual(w.live_state,'preparing')
            w.message(dict(type='status',inference={'state':'RUNNING'}))
            self.assertEqual(w.start_button.text(),'正在推理')
            w.stop_inference()
            w.message(dict(type='status',inference={'state':'STOPPED'},camera={'frames':11}))
            w.archive.finish_at.assert_called_once_with(10)
            success.assert_not_called()
            w.archive.closed.set()
            report=dict(done=True,ok=True,path='saved-session',segments=[],candidates=[],frames=10)
            w.archive_updated(report);w.archive_updated(report)
            self.assertEqual(w.live_state,'idle');success.assert_called_once()

    def test_manual_description_update_waits_for_matching_board_ack(self):
        w=self.window;w.prompts.setPlainText('杯子')
        with patch.object(w.worker,'start'),patch.object(w,'notify_success') as success:
            w.encode();revision=w.worker.revision
            success.assert_not_called()
            w.encoded(dict(op='queries',revision=revision,items=[dict(id='0',label='杯子',text='a photo of a cup')],features=[[1.]*512],identity={}))
            request_id=next(key for key,op in w.request_ids.items() if op=='queries')
            success.assert_not_called()
            w.message(dict(type='ack',request_id=request_id,op='queries',ok=True,result=dict(query_revision=revision,count=1)))
            success.assert_called_once()
            self.assertFalse(w.prompts.isReadOnly())

    def test_rejected_update_does_not_report_success(self):
        w=self.window
        with patch.object(w.worker,'start'),patch.object(w,'notify_success') as success:
            w.encode();w.request_ids['reject']='queries'
            w.message(dict(type='ack',request_id='reject',op='queries',ok=False,error='reject'))
            success.assert_not_called();self.assertFalse(w.prompts.isReadOnly())

    def test_description_send_failure_unlocks_controls(self):
        w=self.window;w.link.send.side_effect=ConnectionError('lost')
        with patch.object(w.worker,'start'):
            w.encode()
            w.encoded(dict(op='queries',revision=w.worker.revision,items=[dict(id='0',label='杯子',text='a cup')],features=[[1.]*512],identity={}))
            self.assertFalse(w.prompts.isReadOnly());self.assertTrue(w.start_button.isEnabled())

    def test_rejected_start_queries_restore_idle(self):
        w=self.window;w.want_recording=True;w.pending_start=True;w.set_live_state('preparing')
        w.request_ids['reject-start']='queries'
        w.message(dict(type='ack',request_id='reject-start',op='queries',ok=False,error='identity rejected'))
        self.assertEqual(w.live_state,'idle');self.assertTrue(w.start_button.isEnabled())

