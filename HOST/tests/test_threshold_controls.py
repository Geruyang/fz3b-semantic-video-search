import unittest
from PySide6.QtWidgets import QApplication,QLineEdit
from vision_app.semantic_ui import SemanticWindow

APP=QApplication.instance() or QApplication([])


class ThresholdControls(unittest.TestCase):
    def test_plus_minus_syncs_pages_without_numeric_entry(self):
        window=SemanticWindow()
        try:
            self.assertAlmostEqual(window.threshold.value(),.17)
            self.assertEqual(window.live_threshold.findChildren(QLineEdit),[])
            window.live_threshold.plus_button.click()
            self.assertAlmostEqual(window.offline_threshold.value(),.18)
            window.offline_threshold.minus_button.click()
            self.assertAlmostEqual(window.live_threshold.value(),.17)
        finally:window.close()

    def test_disabled_controls_cannot_change_job_threshold(self):
        window=SemanticWindow()
        try:
            window.set_threshold_enabled(False)
            window.live_threshold.plus_button.click()
            self.assertAlmostEqual(window.threshold.value(),.17)
        finally:window.close()

