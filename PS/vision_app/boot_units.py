"""Systemd service definitions for the already verified PS application."""


def r5_unit(root):
    return '''[Unit]
Description=FZ3B application dual R5 TCM workers
After=fz3b-pl-loader.service
Requires=fz3b-pl-loader.service

[Service]
Type=oneshot
WorkingDirectory={root}
ExecStart=/usr/bin/python3 -B -m vision_app.r5_start
ExecStop=/usr/bin/python3 -B -m vision_app.r5_start --stop
RemainAfterExit=yes
TimeoutStartSec=60
TimeoutStopSec=30
SendSIGKILL=no
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=multi-user.target
'''.format(root=root)


def application_unit(root, boot=False, cpu_clock=False):
    after = 'fz3b-pl-loader.service network.target'
    requires = 'fz3b-pl-loader.service'
    extra = ''
    wants = ''
    if cpu_clock:
        after += ' fz3b-app-cpu-clock.service'
        requires += ' fz3b-app-cpu-clock.service'
    if boot:
        after += ' fz3b-app-r5.service network-online.target serial-getty@ttyPS0.service'
        requires += ' fz3b-app-r5.service'
        wants = 'Wants=network-online.target serial-getty@ttyPS0.service\n'
        extra = 'ExecStartPre=/usr/bin/python3 -B -m vision_app.link_setup\n'
    return '''[Unit]
Description=FZ3B Vision Console application
After={after}
Requires={requires}
{wants}
[Service]
Type=simple
WorkingDirectory={root}
{extra}ExecStart={root}/run.sh
TimeoutStartSec=60
TimeoutStopSec=360
SendSIGKILL=no
Restart=no

[Install]
WantedBy=multi-user.target
'''.format(root=root, after=after, requires=requires, wants=wants, extra=extra)


def cpu_unit(root):
    return '''[Unit]
Description=FZ3B verified CPU-only PM clock owner
After=fz3b-pl-loader.service fz3b-app-r5.service
Requires=fz3b-pl-loader.service fz3b-app-r5.service
Before=fz3b-vision-console.service

[Service]
Type=notify
NotifyAccess=main
WorkingDirectory={root}
ExecStart=/usr/bin/python3 -B -m vision_app.cpu_clock_service --module {root}/cpu-clock/fz3b_cpu_clock.ko
TimeoutStartSec=60
TimeoutStopSec=15
SendSIGKILL=no
Restart=no
UMask=0077
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
'''.format(root=root)
