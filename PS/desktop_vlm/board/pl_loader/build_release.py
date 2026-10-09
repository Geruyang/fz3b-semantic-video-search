from __future__ import print_function
import argparse, hashlib, json, pathlib, shutil

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'releases/current/pl-loader-a0005'
AUDIT=ROOT/'artifacts/maintenance-20261009/reboot-benchmark-001/fpga-manager-format-audit'

COPY={
 'fz3b_pl_loader.py':HERE/'fz3b_pl_loader.py',
 'strict_a0005_identity.py':HERE/'strict_a0005_identity.py',
 'fz3b-pl-loader.service':HERE/'fz3b-pl-loader.service',
 'README.md':HERE/'README.md',
 'a0005-post-route.bit.bin':AUDIT/'a0005-post-route.bit.bin',
 'factory-restore-pcap-word-swapped.bin':AUDIT/'factory-restore-pcap-word-swapped.bin',
 'a0005-post-route.bit':ROOT/'releases/current/hardware/implementation/final/a0005-post-route.bit',
 'a0005-post-route.bin':ROOT/'releases/current/hardware/implementation/final/a0005-post-route.bin',
}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', default='releases/current/pl-loader-a0005-002')
    args=parser.parse_args()
    out=(ROOT/args.output).resolve()
    if not out.is_relative_to(ROOT/'releases/current'):
        raise RuntimeError('release output must remain under releases/current')
    if out.exists():
        raise RuntimeError('refusing to overwrite a frozen release: '+str(out))
    out.mkdir(parents=True)
    config=json.loads((HERE/'config.example.json').read_text(encoding='utf-8'))
    expected={item['path']:item for item in config['assets'].values()}
    # Pull factory values mechanically from its frozen manifest.
    factory=json.loads((ROOT/'releases/factory/pl/manifest.json').read_text(encoding='utf-8'))
    ffiles={item['path']:item for item in factory['files']}
    ko=config['assets']['factory_driver_ko']
    assert ko['sha256']==ffiles['fpgadrv.ko']['sha256'] and ko['bytes']==ffiles['fpgadrv.ko']['bytes']
    native=config['assets']['factory_native_source']
    assert native['sha256']==ffiles['factory-restore-native.bin']['sha256'] and native['bytes']==ffiles['factory-restore-native.bin']['bytes']
    # Pull PS assets mechanically from the current frozen PS manifest.
    ps=json.loads((ROOT/'releases/current/ps/manifest.json').read_text(encoding='utf-8'))
    bysha={item['sha256']:item for item in ps['files']}
    for label in ('a0005_dtbo','a0005_driver_ko','lease_ko','combined_manifest','admission','range_proof'):
        item=config['assets'][label]; frozen=bysha[item['sha256']]
        assert item['bytes']==frozen['bytes']
    config_path=out/'config.json'
    config_path.write_text(json.dumps(config,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    files=[]
    for name,source in COPY.items():
        target=out/name; shutil.copy2(str(source),str(target))
        files.append({'path':name,'bytes':target.stat().st_size,'sha256':sha(target)})
    files.append({'path':'config.json','bytes':config_path.stat().st_size,'sha256':sha(config_path)})
    manifest={'schema':'fz3b-v10.5-ps-pl-loader-release-v1','status':'FROZEN_FOR_MANUAL_BOARD_GATE',
              'files':sorted(files,key=lambda x:x['path']),
              'a0005_source_bit_sha256':config['assets']['a0005_source_bit']['sha256'],
              'a0005_linux_pcap_sha256':config['assets']['a0005_firmware']['sha256'],
              'factory_native_sha256':config['assets']['factory_native_source']['sha256'],
              'factory_linux_pcap_candidate_sha256':config['assets']['factory_firmware']['sha256'],
              'format_audit_receipt_sha256':'80fc174bcdc90b035caea6e1b2a06f6bd677cbe738215efde0b80aa1284e1414',
              'default_target':'a0005','factory_automatic_rollback':False}
    data=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode();(out/'manifest.json').write_bytes(data)
    print(str(out));print(hashlib.sha256(data).hexdigest())

if __name__=='__main__':main()
