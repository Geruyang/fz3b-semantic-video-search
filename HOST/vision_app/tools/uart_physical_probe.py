import serial
import time
from vision_app.tools.board_link import open_link, run

p = serial.Serial(port=None, baudrate=115200, timeout=.2)
p.dtr = p.rts = False
p.port = 'COM6'
p.open()
c = open_link()
try:
    print(run(c, "grep -E 'xuartps|ff000000|ff010000' /proc/interrupts; printf 'UARTPHYSICALTEST\\n' > /dev/ttyPS0"))
    received = b''
    end = time.monotonic() + 2
    while time.monotonic() < end:
        received += p.read(1024)
    print({'expected_text': 'UARTPHYSICALTEST', 'rx_hex': received[:32].hex(), 'rx_bytes': len(received)})
    p.write(b'HOSTPHYSICALTEST\n')
    time.sleep(.5)
    print(run(c, "grep -E 'xuartps|ff000000|ff010000' /proc/interrupts; ps -L -p $(systemctl show fz3b-vision-console.service -p MainPID --value) -o tid,wchan:28,comm"))
finally:
    c.close()
    p.close()
