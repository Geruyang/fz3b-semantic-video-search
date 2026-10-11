import unittest
from PySide6.QtWidgets import QApplication
from vision_app.semantic_ui import SemanticWindow

APP=QApplication.instance() or QApplication([])


def segment(qid,start):
    return dict(query_id=qid,label=qid,first_hit_s=start,start_s=start,
                end_s=start+1,frame_ids=[1,2],best_score=.3)


class SegmentSelection(unittest.TestCase):
    def test_refresh_keeps_selected_event_when_another_row_is_inserted(self):
        window=SemanticWindow()
        try:
            report=dict(path='session-one',source='camera',segments=[segment('cup',2),segment('hand',5)])
            window.show_segments(report);window.segments_table.selectRow(1)
            window.show_segments(dict(report,segments=[segment('bottle',0),segment('cup',2),segment('hand',5)]))
            self.assertEqual(window.shown_segments[window.segments_table.currentRow()]['query_id'],'hand')
            self.assertEqual(len(window.segments_table.selectedItems()),3)
        finally:window.close()

    def test_new_session_does_not_inherit_old_selection(self):
        window=SemanticWindow()
        try:
            window.show_segments(dict(path='one',source='camera',segments=[segment('cup',2)]))
            window.segments_table.selectRow(0)
            window.show_segments(dict(path='two',source='camera',segments=[segment('cup',2)]))
            self.assertEqual(window.segments_table.selectedItems(),[])
        finally:window.close()
