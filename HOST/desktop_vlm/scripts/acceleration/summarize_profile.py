"""Refine real board profile groups using the exact optimized Conv attributes."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import onnx


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--analysis',required=True)
    ap.add_argument('--optimized-model',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    report=json.loads(Path(args.analysis).read_text(encoding='utf-8'))
    model_path=Path(args.optimized_model)
    digest=hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest!=report['optimized_sha256']:raise ValueError('optimized graph SHA mismatch')
    graph=onnx.load(str(model_path))
    lookup={n.name:n for n in graph.graph.node}
    groups=defaultdict(lambda:{'count':0,'ms':0.0})
    stages=defaultdict(float)
    runtime=sum(report['model_run_ms'])/len(report['model_run_ms'])
    for node in report['nodes']:
        kind=node['op']
        if kind in ('Conv','FusedConv'):
            attrs={a.name:onnx.helper.get_attribute_value(a) for a in lookup[node['name']].attribute}
            weights=next(x['shape'] for x in node['inputs'] if x['constant'] and len(x['shape'])==4)
            activation=next(x['shape'] for x in node['inputs'] if not x['constant'] and len(x['shape'])==4)
            if attrs.get('group',1)==activation[1] and activation[1]>1 and weights[1]==1:
                kind='depthwise_%dx%d'%(weights[2],weights[3])
            elif weights[2:]==[1,1]:kind='pointwise'
            else:kind='conv_other'
        groups[kind]['count']+=1
        groups[kind]['ms']+=node['mean_ms']
        # Fused Gelu names are generic; its dynamic input retains source scope.
        names=[node['name']]+[x['tensor'] for x in node['inputs'] if not x['constant']]
        stage=next((m.group(1) for text in names if (m:=re.search(r'/network\.(\d+)/',text))),None)
        if stage is not None:stages[stage]+=node['mean_ms']
    for value in groups.values():value['model_percent']=100*value['ms']/runtime
    result={'source_profile_sha256':report['profile_sha256'],'optimized_graph_sha256':digest,
            'method':'Diagnostic kernel times, exact optimized Conv group attributes/runtime shapes; not formal latency percentiles; stage grouping follows source names',
            'model_mean_ms':runtime,'groups':dict(sorted(groups.items(),key=lambda item:-item[1]['ms'])),
            'source_stages_ms':dict(stages)}
    target=Path(args.output)
    with target.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
