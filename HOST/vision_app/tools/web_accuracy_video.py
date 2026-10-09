"""Public Pexels footage discovery/download for local accuracy validation."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from vision_app.tools.board_link import ROOT

def main():
    page='https://www.pexels.com/video/a-person-pouring-a-cup-of-coffee-beside-a-laptop-8472298/'
    request=urllib.request.Request(page,headers={'User-Agent':'Mozilla/5.0'})
    html=urllib.request.urlopen(request,timeout=30).read().decode()
    links=list(dict.fromkeys(re.findall(r'https://[^"\s<>]+?\.mp4(?:\?[^"\s<>]*)?',html)))
    links=[link.replace('\\u0026','&').replace('&amp;','&').replace('\\/','/') for link in links if '8472298' in link]
    target=ROOT/'artifacts/semantic-video-20261009/web-accuracy';target.mkdir(exist_ok=True)
    (target/'source-links.json').write_text(json.dumps(dict(page=page,license='https://www.pexels.com/license/',urls=links),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(links))
    if not links:raise RuntimeError('public video source not found')

if __name__=='__main__':main()
