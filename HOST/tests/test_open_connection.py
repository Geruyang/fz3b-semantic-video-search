import os
from pathlib import Path
import subprocess
import sys
import unittest
from PySide6.QtWidgets import QApplication
from vision_app.semantic_ui import SemanticWindow

APP=QApplication.instance() or QApplication([])


class OpenConnection(unittest.TestCase):
    def test_client_has_no_credential_entry(self):
        window=SemanticWindow()
        try:self.assertFalse(hasattr(window,'token'))
        finally:window.close()

    def test_board_accepts_plain_hello_and_rejects_non_handshake(self):
        ps=Path(__file__).resolve().parents[2]/'PS'
        program="from vision_app.board_agent import Agent; assert Agent.accept_hello(None,{'op':'hello'}); assert not Agent.accept_hello(None,{'op':'start'}); assert not Agent.accept_hello(None,None)"
        result=subprocess.run([sys.executable,'-c',program],cwd=ps,env=dict(os.environ,PYTHONPATH=str(ps)),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
