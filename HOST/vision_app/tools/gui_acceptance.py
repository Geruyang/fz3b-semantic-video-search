"""Actual native UI: multi-query, history retrieval, edit, stop and reconnect."""
import json
from pathlib import Path
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QTabWidget
from vision_app.client import Window


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / 'artifacts/ps-application-20261009'
    app = QApplication([])
    window = Window()
    window.show()
    report = {'ok': False, 'steps': []}
    started, stage, first_revision = time.monotonic(), 0, 0
    reconnect_started = 0
    error = None
    ending = False
    def finish():
        nonlocal ending
        ending = True
        window.stop_inference()
        report['elapsed_s'] = time.monotonic() - started
        report['device'] = window.status_data
        report['accepted_revision'] = window.accepted_revision
        report['gallery_frames'] = len(window.gallery)
        report['last_notice'] = window.log_label.text()
        if error:
            report['error'] = error
        (output / 'gui-acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        QTimer.singleShot(3500, window.close)
    def check():
        nonlocal stage, first_revision, reconnect_started, error
        if ending:
            return
        try:
            if time.monotonic() - started > 125:
                raise TimeoutError('native UI acceptance deadline at stage %d' % stage)
            if stage == 0 and window.status_data.get('contract_id') and window.connection_status.text().startswith('已连接'):
                window.prompts.setPlainText('杯子\n瓶子\n手机\n桌面\n房间\n卧室')
                window.start_inference()
                stage = 1
            elif stage == 1 and window.current_result and len(window.gallery) >= 4:
                assert window.ranking.count() == 6
                assert window.status_data['r5']['offload_verified']
                assert window.displayed > 100
                first_revision = window.accepted_revision
                report['steps'].append({'multi_description_revision': first_revision, 'ranking_count': window.ranking.count(), 'preview_frames': window.displayed})
                window.grab().save(str(output / 'gui-live.png'))
                window.search_gallery()
                assert window.gallery_list.count() == len(window.gallery)
                scores = [float(window.gallery_list.item(i).text().split()[0]) for i in range(window.gallery_list.count())]
                assert scores == sorted(scores, reverse=True)
                window.show_gallery(window.gallery_list.item(0))
                window.findChild(QTabWidget).setCurrentIndex(1)
                window.grab().save(str(output / 'gui-history.png'))
                report['steps'].append({'history_ranked_frames': window.gallery_list.count(), 'scores_descending': True})
                window.prompts.setPlainText('卧室 | a photo of a bedroom')
                window.start_inference()
                stage = 2
            elif stage == 2 and window.current_result and window.current_result[0]['query_revision'] > first_revision:
                assert window.ranking.count() == 1
                report['steps'].append({'new_description_revision': window.accepted_revision, 'result_revision': window.current_result[0]['query_revision'], 'ranking_count': 1})
                window.stop_inference()
                assert window.pending_start is False
                stage = 3
            elif stage == 3 and window.status_data.get('inference', {}).get('state') == 'STOPPED':
                window.findChild(QTabWidget).setCurrentIndex(2)
                window.grab().save(str(output / 'gui-device.png'))
                window.connect_board()
                assert window.accepted_revision == 0 and not window.pending_start
                window.status_data = {}
                window.connect_board()
                reconnect_started = time.monotonic()
                stage = 4
            elif stage == 4 and window.status_data.get('contract_id') and window.connection_status.text().startswith('已连接'):
                assert window.accepted_revision == 0, 'existing board query incorrectly accepted as uploaded'
                report['steps'].append({'reconnect_preserved_server_revision': window.status_data['query_revision'], 'local_accepted_revision': 0})
                window.start_inference()
                stage = 5
            elif stage == 5 and window.current_result:
                assert window.current_result[0]['query_revision'] == window.accepted_revision == window.last_encoded['revision']
                report['steps'].append({'reconnect_new_revision': window.accepted_revision, 'reconnect_to_result_s': time.monotonic() - reconnect_started})
                report['ok'] = True
                finish()
        except Exception as exc:
            error = '%s: %s' % (type(exc).__name__, exc)
            finish()
    timer = QTimer()
    timer.timeout.connect(check)
    timer.start(100)
    QTimer.singleShot(100, window.connect_board)
    app.exec()
    print(json.dumps({k: v for k, v in report.items() if k != 'device'}, ensure_ascii=False))
    if not report['ok']:
        raise RuntimeError(error or 'native UI acceptance failed')


if __name__ == '__main__':
    main()
