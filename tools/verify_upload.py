"""Read-only verification of the published source snapshot and XPR file references."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'UPLOAD_MANIFEST.json').read_text(encoding='utf-8'))
seen=set()
for entry in manifest['files']:
    relative=Path(entry['path'])
    if relative.is_absolute() or '..' in relative.parts or entry['path'] in seen:
        raise ValueError('Unsafe or duplicate manifest path')
    seen.add(entry['path']);data=(root/relative).read_bytes()
    if hashlib.sha256(data).hexdigest()!=entry['sha256'] or len(data)!=entry['bytes']:
        raise ValueError('Source checksum mismatch: '+entry['path'])
project=root/'PL/project-final-008'
variables={'$PPRDIR':project,'$PSRCDIR':project/'cnn_rtl.srcs','$PGENDIR':project/'cnn_rtl.gen'}
references=0
for node in ET.parse(project/'cnn_rtl.xpr').iter('File'):
    original=node.get('Path')
    if not original:continue
    resolved=original
    for name,directory in variables.items():resolved=resolved.replace(name,str(directory))
    candidate=Path(resolved).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError('XPR source reference missing or outside snapshot: '+original)
    references+=1
print(json.dumps({'status':'PASS','version':manifest['version'],
                  'source_files':len(seen),'xpr_source_references':references}))
