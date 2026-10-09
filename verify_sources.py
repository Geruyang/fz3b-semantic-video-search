"""Verify the final manifest and the sole IP component's referenced files."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parent
manifest=json.loads((root/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
seen=set()
for entry in manifest['files']:
    relative=Path(entry['path'])
    if relative.is_absolute() or '..' in relative.parts or entry['path'] in seen:
        raise ValueError('Unsafe or duplicate manifest path')
    seen.add(entry['path'])
    data=(root/relative).read_bytes()
    if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
        raise ValueError('Source checksum mismatch: '+entry['path'])
ip=root/'PL/ip/cnn_pipeline_v10'
tree=ET.fromstring((ip/'component.xml').read_bytes())
references=set()
for element in tree.iter():
    if element.tag.split('}')[-1]=='file':
        for child in element:
            if child.tag.split('}')[-1]=='name' and child.text:references.add(child.text)
for relative in references:
    path=(ip/relative).resolve()
    if not path.is_relative_to(ip.resolve()) or not path.is_file():
        raise ValueError('IP reference missing or unsafe: '+relative)
print(json.dumps({'status':'PASS','source_files':len(seen),'final_ip_references':len(references)}))
