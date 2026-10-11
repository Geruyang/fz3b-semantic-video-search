"""Execute an authorized board-test script using the existing pinned SSH link."""
import argparse
import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from fz3b_ssh import open_link

parser = argparse.ArgumentParser()
parser.add_argument('--script', required=True, type=Path)
parser.add_argument('--name', required=True)
parser.add_argument('--output-directory', type=Path)
args = parser.parse_args()
if not args.name.replace('-', '').replace('_', '').isalnum():
    raise SystemExit('Invalid evidence name.')
script = args.script.read_text(encoding='utf-8')
directory = (args.output_directory or ROOT / 'rtl_optim/reports/board').resolve()
directory.relative_to((ROOT / 'rtl_optim/reports/board').resolve())
directory.mkdir(parents=True, exist_ok=True)
started = datetime.now(timezone.utc).isoformat()
(directory / (args.name + '.executed.sh')).write_text(script, encoding='utf-8', newline='\n')
script_sha256 = hashlib.sha256(script.encode('utf-8')).hexdigest()
client = open_link()
try:
    stdin, stdout, stderr = client.exec_command('sudo -n bash -s 2>&1', timeout=900)
    stdin.write(script + '\n')
    stdin.channel.shutdown_write()
    with (directory / (args.name + '.log')).open('w', encoding='utf-8') as log:
        for line in stdout:
            print(line, end='', flush=True)
            log.write(line)
            log.flush()
    error = stderr.read().decode('utf-8', 'replace')
    code = stdout.channel.recv_exit_status()
    receipt = {'started_utc': started, 'ended_utc': datetime.now(timezone.utc).isoformat(),
               'exit_code': code, 'script': str(args.script), 'executed_script_sha256': script_sha256, 'stderr': error}
    (directory / (args.name + '.execution.json')).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    if error:
        print(error)
    raise SystemExit(code)
finally:
    client.close()
