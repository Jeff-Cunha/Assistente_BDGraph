"""Collect the nine explicitly requested sources; run from any working directory."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import hashlib
import json
import time
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ('D01','https://opentextbc.ca/dbdesign01/chapter/chapter-2-fundamental-concepts/'),
    ('D02','https://opentextbc.ca/dbdesign01/chapter/chapter-8-entity-relationship-model/'),
    ('D03','https://opentextbc.ca/dbdesign01/chapter/chapter-9-integrity-rules-and-constraints/'),
    ('D04','https://opentextbc.ca/dbdesign01/chapter/chapter-11-functional-dependencies/'),
    ('D05','https://opentextbc.ca/dbdesign01/chapter/chapter-12-normalization/'),
    ('D06','https://www.postgresql.org/docs/18/tutorial-select.html'),
    ('D07','https://www.postgresql.org/docs/18/tutorial-join.html'),
    ('D08','https://www.postgresql.org/docs/18/tutorial-agg.html'),
    ('D09','https://opentextbc.ca/dbdesign01/chapter/chapter-7-the-relational-data-model/'),
]

def fetch(url, path):
    rec = {'requested_url':url, 'collected_at':datetime.now(timezone.utc).isoformat(), 'attempts':[]}
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=(20, 75), headers={'User-Agent':'AcademicCorpusCollector/1.0 (public educational documents)'})
            rec.update(final_url=r.url, http_status=r.status_code,
                       redirects=[{'status':h.status_code,'url':h.url,'location':h.headers.get('Location')} for h in r.history],
                       content_type=r.headers.get('Content-Type'),
                       response_headers={k:v for k,v in r.headers.items() if k.lower() in
                                         ('date','content-type','content-length','content-encoding','etag','last-modified','location')})
            rec['attempts'].append({'number':attempt+1,'status':r.status_code})
            if r.status_code >= 500 and attempt < 2:
                time.sleep(2)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            rec.update(path=path.relative_to(ROOT).as_posix(), bytes=len(r.content), sha256=hashlib.sha256(r.content).hexdigest(),
                       status='success' if r.status_code == 200 else 'http_error')
            return rec
        except requests.RequestException as e:
            rec['attempts'].append({'number':attempt+1,'error':str(e)})
    rec['status']='network_error'
    return rec

def collect_source(source):
    doc_id, url = source
    rec = fetch(url, ROOT/'raw'/f'{doc_id}.html')
    rec['document_id'] = doc_id
    rec['assets'] = []
    if rec['status'] == 'success':
        soup = BeautifulSoup((ROOT/rec['path']).read_bytes(), 'html.parser')
        body = soup.select_one('section.chapter') if 'opentextbc' in url else soup.select_one('#docContent .sect1')
        if body:
            seen = {}
            for img in body.select('img'):
                src = urljoin(rec['final_url'],img.get('src',''))
                if not img.get('src') or src in seen:
                    continue
                ext=Path(urlparse(src).path).suffix.lower()
                if ext not in ('.png','.jpg','.jpeg','.gif','.svg','.webp'): ext='.bin'
                asset=fetch(src,ROOT/'raw'/'assets'/f'{doc_id}_F{len(seen)+1:03d}{ext}')
                asset['alt']=img.get('alt','')
                seen[src]=asset
                rec['assets'].append(asset)
        else:
            rec['status']='content_not_found'
    return rec

def main():
    for folder in ('raw','processed','chunks','metadata','licenses'):
        (ROOT/folder).mkdir(exist_ok=True,parents=True)
    records=list(ThreadPoolExecutor(max_workers=4).map(collect_source,SOURCES))
    (ROOT/'metadata'/'collection_log.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    # Declaration pages are saved as evidence, separate from the nine-document corpus.
    declarations=[('book','https://opentextbc.ca/dbdesign01/'),
                  ('postgresql_18_copyright','https://www.postgresql.org/docs/18/legalnotice.html'),
                  ('postgresql_license','https://www.postgresql.org/about/licence/'),
                  ('cc_by_4','https://creativecommons.org/licenses/by/4.0/'),
                  ('cc_by_3','https://creativecommons.org/licenses/by/3.0/'),
                  ('cc_by_sa_3','https://creativecommons.org/licenses/by-sa/3.0/')]
    notices=list(ThreadPoolExecutor(max_workers=4).map(lambda d:fetch(d[1],ROOT/'licenses'/f'{d[0]}.html'),declarations))
    (ROOT/'licenses'/'collection_log.json').write_text(json.dumps(notices,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'id':r['document_id'],'status':r['status'],'bytes':r.get('bytes'),'images':len(r['assets']),'asset_failures':sum(a['status']!='success' for a in r['assets'])} for r in records],indent=2))

if __name__=='__main__': main()
