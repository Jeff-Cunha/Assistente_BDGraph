"""Print the first non-whitespace text difference between raw body and rendered MD."""
from prepare import *

for source in json.loads((ROOT/'metadata'/'collection_log.json').read_text(encoding='utf-8')):
    soup=BeautifulSoup((ROOT/source['path']).read_bytes(),'html.parser')
    _,_,clone=semantic_blocks(body_of(soup,'opentextbc' in source['requested_url']),source)
    md=(ROOT/'processed'/(source['document_id']+'.md')).read_text(encoding='utf-8')
    rendered=BeautifulSoup(MD.render(md),'html.parser')
    a=re.sub(r'\s+','',clone.get_text()); b=re.sub(r'\s+','',rendered.get_text())
    if a!=b:
        i=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
        print(source['document_id'],json.dumps({'raw':a[max(0,i-80):i+160],'processed':b[max(0,i-80):i+160]},ensure_ascii=True))
    expected=[('h2' if h.name=='p' else h.name,space(h.get_text(' ',strip=True))) for h in clone.select('h1,h2,h3,h4,h5,h6,p.textbox__title') if h.get_text(strip=True)]
    actual=[(h.name,space(h.get_text(' ',strip=True))) for h in rendered.select('h1,h2,h3,h4,h5,h6')]
    if expected!=actual:
        print(source['document_id'],'heading difference',json.dumps({'raw':expected,'processed':actual},ensure_ascii=True))
