"""Keep the approved board-only Ethernet alias across software boots."""
import subprocess
import time

ADDRESS = '169.254.220.254/16'


def main():
    deadline = time.monotonic() + 20
    while True:
        try:
            text = subprocess.check_output(['ip', '-4', 'addr', 'show', 'dev', 'eth0']).decode('ascii')
            break
        except subprocess.CalledProcessError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.2)
    if ADDRESS not in text.split():
        subprocess.check_call(['ip', 'addr', 'add', ADDRESS, 'dev', 'eth0'])
    confirmed = subprocess.check_output(['ip', '-4', 'addr', 'show', 'dev', 'eth0']).decode('ascii')
    if ADDRESS not in confirmed.split():
        raise RuntimeError('approved Ethernet alias not present')
    print('Approved Ethernet alias ready: ' + ADDRESS)


if __name__ == '__main__':
    main()
