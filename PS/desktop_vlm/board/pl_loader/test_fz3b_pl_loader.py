import importlib.util
import pathlib
import tempfile
import unittest

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('loader',str(HERE/'fz3b_pl_loader.py'))
loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)

class FakeBackend(object):
    def __init__(self, fail=None, target='factory'):
        self.ops=[];self.fail=fail;self.target=target;self.lease_fd=None
    def _op(self,name,value=None):
        self.ops.append(name)
        if self.fail==name:
            if name=='ensure_no_owner': raise loader.BusyError(name)
            raise loader.LoaderError(name)
        return value
    def verify_assets(self): return self._op('verify_assets')
    def wait_manager(self): return self._op('wait_manager')
    def detect_target(self): return self.target
    def runtime_status(self): return {'detected_target':self.target}
    def ensure_no_owner(self): return self._op('ensure_no_owner')
    def remove_a0005_stack(self): return self._op('remove_a0005_stack')
    def remove_factory_stack(self): return self._op('remove_factory_stack')
    def acquire_lease(self): self.lease_fd=7; return self._op('acquire_lease',{'flags':0x27})
    def set_pl1(self,a,b): return self._op('set_pl1_%08x_%08x'%(a,b))
    def load_firmware(self,label): return self._op('load_'+label)
    def apply_a0005_stack(self): return self._op('apply_a0005_stack')
    def strict_identity(self): return self._op('strict_identity',{'core_abi':0xA0005})
    def quiesce_a0005(self): return self._op('quiesce_a0005',{'core_abi':0xA0005})
    def finalize_lease(self): self.lease_fd=None; return self._op('finalize_lease')
    def apply_factory_stack(self): return self._op('apply_factory_stack')

class ControllerTests(unittest.TestCase):
    def controller(self,backend):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        return loader.Controller({},backend,pathlib.Path(tmp.name)/'state.json',lambda *a,**k:None)
    def test_a0005_order(self):
        backend=FakeBackend(); result=self.controller(backend).switch_a0005()
        self.assertTrue(result['ready']);self.assertEqual(result['target'],'a0005')
        self.assertEqual(backend.ops,['verify_assets','wait_manager','ensure_no_owner','remove_a0005_stack','remove_factory_stack','acquire_lease','set_pl1_00052000_01010f00','load_a0005_firmware','apply_a0005_stack','strict_identity'])
    def test_busy_owner_stops_before_mutation(self):
        backend=FakeBackend('ensure_no_owner'); ctl=self.controller(backend)
        with self.assertRaises(loader.LoaderError): ctl.switch_a0005()
        self.assertEqual(backend.ops,['verify_assets','wait_manager','ensure_no_owner'])
        self.assertEqual(ctl.status()['status'],'READY_FACTORY')
    def test_bad_sha_never_rolls_back(self):
        backend=FakeBackend('verify_assets'); ctl=self.controller(backend)
        with self.assertRaises(loader.LoaderError): ctl.switch_a0005()
        self.assertNotIn('load_factory_firmware',backend.ops)
        self.assertEqual(ctl.status()['status'],'READY_FACTORY')
    def test_program_failure_never_rolls_back(self):
        backend=FakeBackend('load_a0005_firmware'); ctl=self.controller(backend)
        with self.assertRaises(loader.LoaderError): ctl.switch_a0005()
        self.assertNotIn('load_factory_firmware',backend.ops)
        self.assertNotIn('finalize_lease',backend.ops)
        self.assertEqual(ctl.status()['target'],'unknown')
    def test_factory_reverse_order(self):
        backend=FakeBackend(target='a0005');backend.lease_fd=7
        result=self.controller(backend).switch_factory()
        self.assertTrue(result['ready']);self.assertEqual(result['target'],'factory')
        self.assertEqual(backend.ops,['verify_assets','wait_manager','ensure_no_owner','quiesce_a0005','remove_a0005_stack','load_factory_firmware','set_pl1_01010f00_00052000','finalize_lease','apply_factory_stack'])
    def test_idempotent_targets_do_not_mutate(self):
        factory=FakeBackend(target='factory');self.controller(factory).switch_factory()
        self.assertEqual(factory.ops,['verify_assets','wait_manager'])
        a5=FakeBackend(target='a0005');a5.lease_fd=7
        self.controller(a5).switch_a0005()
        self.assertEqual(a5.ops,['verify_assets','wait_manager','ensure_no_owner','remove_a0005_stack','apply_a0005_stack','strict_identity'])
    def test_busy_same_a0005_is_status_only(self):
        a5=FakeBackend('ensure_no_owner',target='a0005');a5.lease_fd=7
        result=self.controller(a5).switch_a0005()
        self.assertTrue(result['ready'])
        self.assertEqual(a5.ops,['verify_assets','wait_manager','ensure_no_owner'])
    def test_word_swap_contract(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        native=pathlib.Path(tmp.name)/'native.bin';pcap=pathlib.Path(tmp.name)/'pcap.bin'
        native.write_bytes(bytes.fromhex('aa99556611223344'))
        pcap.write_bytes(bytes.fromhex('665599aa44332211'))
        loader.LinuxBackend._verify_word_swap(str(native),str(pcap),'test')
        pcap.write_bytes(bytes.fromhex('665599aa44332210'))
        with self.assertRaises(loader.LoaderError):
            loader.LinuxBackend._verify_word_swap(str(native),str(pcap),'test')

    def test_backend_removal_quiesces_pinned_driver_before_rmmod(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        backend=loader.LinuxBackend({'paths':{'a0005_module':'candidate',
                    'overlay_dir':str(pathlib.Path(tmp.name)/'absent')}},lambda *a,**k:None)
        operations=[]
        backend._module=lambda name:True
        backend.quiesce_a0005=lambda:operations.append('quiesce')
        backend.run=lambda argv:operations.append(argv)
        backend.remove_a0005_stack()
        self.assertEqual(operations,['quiesce',['/sbin/rmmod','candidate']])

if __name__=='__main__':unittest.main()
