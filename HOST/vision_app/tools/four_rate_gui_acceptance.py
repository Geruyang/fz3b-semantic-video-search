"""Read-only native device page: four choices, actual CPU and live preview."""
import json
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QTabWidget
from vision_app.client import Window
from vision_app.tools.board_link import ROOT

def main():
    app=QApplication([]);window=Window();window.show()
    output=ROOT/'artifacts/ps-application-20261009'
    started=time.monotonic();report={'ok':False,'read_only':True}
    def capture():
        state=window.status_data
        if state.get('cpu',{}).get('verified') and window.displayed>10:
            rates=[window.cpu.itemData(i) for i in range(window.cpu.count())]
            assert rates==[600,800,1000,1200] and window.cpu.currentData()==1200
            assert state['cpu']['actual_hz']==1199999988 and state['inference']['state']=='STOPPED'
            window.findChild(QTabWidget).setCurrentIndex(2)
            window.grab().save(str(output/'gui-four-rates.png'))
            report.update(ok=True,rates_mhz=rates,cpu=state['cpu'],preview_frames=window.displayed,boot_id=state['boot_id'])
            (output/'gui-four-rates.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            window.close();app.quit()
        elif time.monotonic()-started<25:QTimer.singleShot(100,capture)
        else:window.close();app.quit()
    QTimer.singleShot(100,window.connect_board);QTimer.singleShot(1000,capture)
    app.exec()
    assert report['ok'],'four-rate device page did not qualify'
    print(json.dumps(dict(ok=True,rates_mhz=report['rates_mhz'],preview_frames=report['preview_frames'])))

if __name__=='__main__':main()
