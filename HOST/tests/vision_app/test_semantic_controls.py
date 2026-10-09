import unittest
from unittest.mock import patch
import threading
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
APP=QApplication.instance() or QApplication([])

class SemanticControls(unittest.TestCase):
    def test_preset_only_fills_descriptions_and_never_bypasses_recording(self):
        from vision_app.semantic_ui import SemanticWindow
        window=SemanticWindow()
        try:
            with patch.object(window,'request') as request,patch.object(window,'encode') as encode:
                window.preset_classify();request.assert_not_called();encode.assert_not_called()
            self.assertEqual(len(window.prompts.toPlainText().splitlines()),18)
        finally:window.close()
    def test_active_recording_keeps_query_snapshot(self):
        from vision_app.semantic_ui import SemanticWindow
        window=SemanticWindow();original=window.prompts.toPlainText()
        try:
            window.archive=SimpleNamespace(closed=threading.Event())
            window.preset_classify();self.assertEqual(window.prompts.toPlainText(),original)
        finally:window.archive=None;window.close()
