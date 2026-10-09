"""Developer-only baseline: hold the verified original CPU clock unchanged."""
import json
from .board_agent import Agent, CpuPolicy
from .cpu_clock_service import Lease


class BaselineCpu:
    def __init__(self):
        self.lease = Lease()

    def status(self):
        state = self.lease.status()
        if state['actual_hz'] != 1066666656 or state['acpu_ctrl'] != 0x03000100:
            raise RuntimeError('diagnostic baseline CPU changed')
        result = CpuPolicy().status()
        result.update(state, current_khz=1066666, verified=True,
                      governor='diagnostic_read_only_original_clock')
        return result

    def set_frequency(self, khz):
        raise RuntimeError('read-only baseline diagnostic')


class BaselineAgent(Agent):
    def apply_boot_defaults(self):
        self.cpu = BaselineCpu()
        return self.cpu.status()


def main():
    with open('config.json') as handle:
        config = json.load(handle)
    config['preprocess_async'] = False
    agent = BaselineAgent(config)
    try:
        agent.run()
    finally:
        if isinstance(agent.cpu, BaselineCpu):
            agent.cpu.lease.close()


if __name__ == '__main__':
    main()
