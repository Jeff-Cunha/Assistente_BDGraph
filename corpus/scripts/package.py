"""Verify the prepared corpus, generate the image overview/checksums, and ZIP it."""
from pathlib import Path
import hashlib
import json
import zipfile
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]

def included(path):
    return path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc'

def main():
    qa=json.loads((ROOT/'metadata'/'quality_checks.json').read_text(encoding='utf-8'))
    sources=json.loads((ROOT/'metadata'/'sources.json').read_text(encoding='utf-8'))
    assert len(qa)==len(sources)==9, 'Nine sources must be fully collected.'
    assert all(q['status'].startswith('passed') for q in qa), 'Unresolved quality checks.'
    chunks=[json.loads(line) for line in (ROOT/'chunks'/'chunks.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len({c['chunk_id'] for c in chunks})==len(chunks), 'Duplicate chunk IDs.'
    supplement_validation=None
    if (ROOT/'metadata'/'figure_transcriptions.json').exists():
        from validate_figure_supplements import validate
        supplement_validation=validate(write_report=True)
    for source in sources:
        doc=source['document_id']
        cs=[c for c in chunks if c['document_id']==doc]
        assert [c['chunk_index'] for c in cs]==list(range(1,len(cs)+1))
        assert '\n\n'.join(c['text'] for c in cs)+'\n'==(ROOT/source['clean_file']).read_text(encoding='utf-8')
        assert hashlib.sha256((ROOT/source['original_file']).read_bytes()).hexdigest()==source['raw_sha256']
        assert hashlib.sha256((ROOT/source['clean_file']).read_bytes()).hexdigest()==source['clean_sha256']
    images=sorted((ROOT/'raw'/'assets').glob('*'))
    sheet=Image.new('RGB',(1250,200*((len(images)+4)//5)),'white')
    draw=ImageDraw.Draw(sheet)
    for i,path in enumerate(images):
        with Image.open(path) as original:
            im=original.convert('RGB'); im.thumbnail((238,172))
        x=(i%5)*250; y=(i//5)*200
        sheet.paste(im,(x+(250-im.width)//2,y+20))
        draw.text((x+5,y+3),path.stem,fill='black')
    sheet.save(ROOT/'metadata'/'figures_contact_sheet.jpg',quality=90)
    inventory=ROOT/'metadata'/'files.sha256'
    files=sorted(p for p in ROOT.rglob('*') if included(p) and p!=inventory)
    inventory.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files),encoding='utf-8')
    archive=ROOT.parent/'corpus.zip'
    files=sorted(p for p in ROOT.rglob('*') if included(p))
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files: z.write(p,p.relative_to(ROOT.parent).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None, 'ZIP integrity failure.'
        assert len(z.namelist())==len(files)
        for p in files:
            assert z.read(p.relative_to(ROOT.parent).as_posix())==p.read_bytes()
    print(json.dumps({'documents':len(sources),'chunks':len(chunks),'words':sum(q['word_count'] for q in qa),
                      'chunk_word_range':[min(c['word_count'] for c in chunks),max(c['word_count'] for c in chunks)],
                      'images':len(images),'files':len(files),'archive':str(archive),
                      'figure_supplements':supplement_validation,
                      'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2))

if __name__=='__main__': main()
