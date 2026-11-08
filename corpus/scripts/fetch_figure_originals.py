"""Targeted higher-resolution candidates; never modifies raw snapshots.

Some Pressbooks snapshots only expose a 300px image. The matching upload filename
without the thumbnail suffix is a candidate, not an asserted original. Every
attempt and dimension is logged; a visual comparison is required before use.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
from collect import ROOT, fetch

SELECTED={'D02_F007','D02_F008','D02_F009','D02_F010',
          'D03_F002','D03_F005','D03_F007','D03_F009','D03_F011','D03_F013','D03_F016',
          'D04_F007','D05_F001','D09_F003'}

def attempt(fig):
    url=re.sub(r'-\d+x\d+(?=\.[^.]+$)','',fig['source_url']).replace('http:','https:',1)
    path=ROOT/'supplements'/'provenance'/'responses'/(fig['figure_id']+'.response')
    record=fetch(url,path)
    record.update(figure_id=fig['figure_id'],snapshot_file=fig['local_file'],
                  snapshot_dimensions=fig['pixel_dimensions'],
                  candidate_basis='same upload directory and filename, thumbnail size suffix removed; not a substitution',
                  visual_identity_verified=False)
    if record['status']=='success':
        try:
            with Image.open(path) as im: record['pixel_dimensions']=list(im.size); im.verify()
            record['higher_resolution']=record['pixel_dimensions'][0]>fig['pixel_dimensions'][0]
        except Exception as e:
            record['image_error']=str(e); record['higher_resolution']=False
    if record.get('path'):
        if record.get('pixel_dimensions'):
            final=ROOT/'supplements'/'assets'/(fig['figure_id']+'_candidate.jpg')
        else:
            final=ROOT/'supplements'/'provenance'/'responses'/(fig['figure_id']+'.html')
        final.parent.mkdir(parents=True,exist_ok=True)
        path.replace(final)
        record['path']=final.relative_to(ROOT).as_posix()
    return record

if __name__=='__main__':
    figs=json.loads((ROOT/'metadata'/'figures.json').read_text(encoding='utf-8'))
    records=list(ThreadPoolExecutor(max_workers=4).map(attempt,[f for f in figs if f['figure_id'] in SELECTED]))
    (ROOT/'metadata'/'figure_resolution_collection.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'id':r['figure_id'],'status':r['status'],'dimensions':r.get('pixel_dimensions'),'higher_resolution':r.get('higher_resolution')} for r in records],indent=2))
