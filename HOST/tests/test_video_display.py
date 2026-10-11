import io
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer
from vision_app.semantic_ui import SemanticWindow

APP=QApplication.instance() or QApplication([])


class VideoDisplay(unittest.TestCase):
    def setUp(self):
        self.window=SemanticWindow()
        self.window.tabs.setCurrentIndex(1)
        out=io.BytesIO();Image.new('RGB',(32,32),'red').save(out,'JPEG');self.jpeg=out.getvalue()

    def tearDown(self):self.window.close()

    def test_mode_switch_displays_latest_analyzed_frame_and_preserves_threshold(self):
        w=self.window;w.threshold.setValue(.23)
        w.analysis_frame(self.jpeg)
        w.display_mode.setCurrentIndex(1)
        self.assertEqual(w.preview_stack.currentIndex(),1)
        w.analysis_frame(self.jpeg)
        w.display_mode.setCurrentIndex(0)
        self.assertEqual(w.preview_stack.currentIndex(),0)
        self.assertFalse(w.video.pixmap().isNull())
        self.assertAlmostEqual(w.offline_threshold.value(),.23)

    def test_full_video_pause_and_page_change_stop_playback(self):
        w=self.window;w.display_mode.setCurrentIndex(1)
        w.playback_toggle()
        w.tabs.setCurrentIndex(0)
        self.assertEqual(w.player.playbackState(),QMediaPlayer.StoppedState)
        self.assertEqual(w.preview_stack.currentIndex(),0)

    def test_loaded_notification_does_not_resume_or_rewind_a_paused_video(self):
        w=self.window;w.playing=True;w.playback_kind='full';w.full_position=999
        with patch.object(w.player,'play') as play,patch.object(w.player,'setPosition') as seek:
            w.media_loaded(QMediaPlayer.LoadedMedia)
            play.assert_not_called();seek.assert_not_called()

