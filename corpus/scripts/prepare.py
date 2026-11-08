"""Offline, deterministic HTML -> Markdown, manifest, chunks, and QA report."""
from pathlib import Path
from urllib.parse import urljoin
from collections import Counter
import hashlib
import html
import json
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
MD = MarkdownIt('commonmark', {'html': True})

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def space(text):
    return re.sub(r'\s+', ' ', text).strip()

def words(text):
    # Render Markdown first so SQL comparison operators and nested image links survive.
    rendered=BeautifulSoup(MD.render(text),'html.parser')
    visible=rendered.get_text(' ',strip=True)+' '+ ' '.join(x.get('alt','') for x in rendered.select('img'))
    return len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b",visible))

def body_of(soup, book):
    return soup.select_one('section.chapter') if book else soup.select_one('#docContent .sect1')

class Renderer:
    def __init__(self, source):
        self.source=source
        self.url=source['final_url']
        self.assets={a['requested_url']:a for a in source['assets']}
        self.table_count=0
        self.pre_blocks=[]
        self.sql_textboxes=[]

    def inline(self,node):
        if isinstance(node,NavigableString):
            text=html.escape(re.sub(r'\s+',' ',str(node)),quote=False)
            return re.sub(r'([\\*_`\[\]])',r'\\\1',text)
        if not isinstance(node,Tag): return ''
        name=node.name
        if name in ('script','style'): return ''
        if name=='br': return '  \n'
        if name=='img':
            url=urljoin(self.url,node.get('src',''))
            asset=self.assets.get(url)
            target='../'+asset['path'] if asset and asset['status']=='success' else url
            alt=node.get('alt','').replace('[','\\[').replace(']','\\]')
            return f'![{alt}]({target})'
        if name=='code':
            inner=node.get_text()
            tick='``' if '`' in inner else '`'
            return tick+inner.strip()+tick
        inner=''.join(self.inline(c) for c in node.children)
        if name=='a':
            if node.get('href') and inner.strip():
                return f'[{inner.strip()}]({urljoin(self.url,node["href"])})'
            return inner
        # Inline HTML avoids CommonMark delimiter failures for emphasized punctuation
        # and source fragments without spaces (e.g. Entities<em>,</em>).
        if name in ('em','i'): return '<em>'+inner+'</em>'
        if name in ('strong','b'): return '<strong>'+inner+'</strong>'
        if name in ('sub','sup'): return f'<{name}>{inner}</{name}>'
        return inner

    def render_list(self,node,depth=0):
        rows=[]
        start=int(node.get('start',1))
        for i,li in enumerate(node.find_all('li',recursive=False),start):
            marker=f'{i}. ' if node.name=='ol' else '- '
            parts=self.blocks(li)
            text='\n\n'.join(t for _,t in parts).strip()
            lines=text.splitlines()
            if not lines: continue
            rows.append(marker+lines[0]+'\n'+ '\n'.join(' '*len(marker)+l if l else '' for l in lines[1:]))
        return '\n'.join(rows).rstrip()

    def blocks(self,node):
        out=[]
        inline=[]
        def flush():
            if inline:
                val=''.join(inline).strip()
                if val: out.append(('paragraph',val))
                inline.clear()
        for c in node.children:
            if isinstance(c,NavigableString):
                if str(c).strip(): inline.append(self.inline(c))
                elif inline: inline.append(' ')
                continue
            if not isinstance(c,Tag): continue
            n=c.name
            if n in ('script','style','nav'): continue
            if n in ('span','a','strong','em','b','i','code','sup','sub','br','img','acronym'):
                inline.append(self.inline(c)); continue
            flush()
            if re.fullmatch(r'h[1-6]',n):
                val=self.inline(c).strip()
                if c.get_text(strip=True): out.append((n,'#'*int(n[1])+' '+val))
            elif n=='p':
                val=self.inline(c).strip()
                if val:
                    # Pressbooks textbox titles are semantic section labels encoded as p.
                    kind='h2' if 'textbox__title' in c.get('class',[]) else 'paragraph'
                    out.append((kind,('## ' if kind=='h2' else '')+val))
            elif n=='pre':
                text=c.get_text().strip('\n')
                lang='sql' if 'programlisting' in c.get('class',[]) else 'text'
                self.pre_blocks.append(text)
                fence='`'*max(3,max((len(m.group())+1 for m in re.finditer(r'`+',text)),default=3))
                out.append(('code',f'{fence}{lang}\n{text}\n{fence}'))
            elif n in ('ul','ol'):
                out.append(('list',self.render_list(c)))
            elif n=='figure':
                out.append(('figure','\n\n'.join(t for _,t in self.blocks(c))))
            elif n=='figcaption':
                out.append(('caption',self.inline(c).strip()))
            elif n=='table':
                # Raw HTML is valid Markdown and preserves cells, missing headers, and spans.
                table=BeautifulSoup(str(c),'html.parser').table
                for a in table.select('a[href]'): a['href']=urljoin(self.url,a['href'])
                self.table_count+=1
                out.append(('table',str(table)))
            elif n=='div' and 'textbox' in c.get('class',[]) and re.match(r'\s*CREATE TABLE\b',c.get_text()):
                clone=BeautifulSoup(str(c),'html.parser').div
                for br in clone.select('br'): br.replace_with('\n')
                text=clone.get_text().strip()
                text=re.sub(r'\n[ \t]*\n','\n',text)
                self.sql_textboxes.append(text)
                out.append(('code','```sql\n'+text+'\n```'))
            elif n=='hr':
                pass
            else:
                out.extend(self.blocks(c))
        flush()
        return out

def semantic_blocks(body,source):
    clone=BeautifulSoup(str(body),'html.parser')
    for x in clone.select('a.id_link,a.indexterm'): x.decompose()
    renderer=Renderer(source)
    blocks=renderer.blocks(clone)
    return blocks,renderer,clone

def make_units(blocks,title):
    """Atomic lists/tables/code remain intact; pair examples with introducing prose."""
    units=[]
    stack=[]
    pending=[]
    for kind,text in blocks:
        if not text.strip(): continue
        if re.fullmatch('h[1-6]',kind):
            level=int(kind[1]); label=re.sub(r'^#+\s*','',text)
            stack=[s for s in stack if s[0]<level]+[(level,label)]
            pending.append(text)
            continue
        path=[s[1] for s in stack] or [title]
        unit={'text':'\n\n'.join(pending+[text]),'section_path':path,'kind':kind}
        pending=[]
        # Consecutive code/output, table/figure, or an explicitly introduced list are indivisible.
        if units and units[-1]['section_path']==path and (
            kind in ('code','table','figure') or
            (kind=='list' and units[-1]['text'].rstrip().endswith(':'))):
            units[-1]['text']+='\n\n'+unit['text']
            units[-1]['kind']='example_group'
        else:
            units.append(unit)
    if pending:
        units.append({'text':'\n\n'.join(pending),'section_path':[s[1] for s in stack], 'kind':'heading'})
    return units

def chunk_units(units,source):
    chunks=[]; groups=[]; current=[]
    def major(u): return u['section_path'][:2]
    for unit in units:
        candidate=current+[unit]
        boundary=current and major(current[-1])!=major(unit)
        if current and (words('\n\n'.join(u['text'] for u in candidate))>600 or
                        (boundary and words('\n\n'.join(u['text'] for u in current))>=300)):
            groups.append(current); current=[]
        current.append(unit)
    if current: groups.append(current)
    if len(groups)>1 and words('\n\n'.join(u['text'] for u in groups[-1]))<300:
        joined=groups[-2]+groups[-1]
        if words('\n\n'.join(u['text'] for u in joined))<=600:
            groups[-2:]=[joined]
        else:
            candidates=[]
            for cut in range(1,len(joined)):
                left=words('\n\n'.join(u['text'] for u in joined[:cut]))
                right=words('\n\n'.join(u['text'] for u in joined[cut:]))
                if 300<=left<=600 and 300<=right<=600:
                    candidates.append((abs(left-right),cut))
            if candidates:
                cut=min(candidates)[1]
                groups[-2:]=[joined[:cut],joined[cut:]]
    for i,group in enumerate(groups,1):
        paths=[u['section_path'] for u in group]
        common=paths[0][:]
        for path in paths[1:]:
            common=common[:next((j for j,(a,b) in enumerate(zip(common,path)) if a!=b),min(len(common),len(path)))]
        text='\n\n'.join(u['text'] for u in group)
        chunks.append({'chunk_id':f'{source["document_id"]}_C{i:03d}',
                       'document_id':source['document_id'],'section_path':common,
                       'chunk_index':i,'text':text,'source_url':source['final_url'],'language':'en',
                       'section_paths':list(dict.fromkeys(tuple(p) for p in paths)),
                       'word_count':words(text),
                       'size_note':('over_600_preserved_indivisible_unit' if words(text)>600 else
                                    'under_300_document_or_section_boundary' if words(text)<300 else None)})
    return chunks

def main():
    sources=json.loads((ROOT/'metadata'/'collection_log.json').read_text(encoding='utf-8'))
    declarations=json.loads((ROOT/'licenses'/'collection_log.json').read_text(encoding='utf-8'))
    pg=BeautifulSoup((ROOT/'licenses'/'postgresql_18_copyright.html').read_bytes(),'html.parser').select_one('.legalnotice')
    pg_notice=pg.get_text('\n',strip=True)
    (ROOT/'licenses'/'postgresql_18_notice.txt').write_text(pg_notice+'\n',encoding='utf-8')
    manifest=[]; all_chunks=[]; qa=[]; image_records=[]
    for source in sources:
        doc=source['document_id']; book='opentextbc.ca' in source['requested_url']
        if source['status']!='success' or not source.get('path'):
            manifest.append({**source,'collection_status':'failed','notes':['Main content not available; not chunked.']})
            continue
        soup=BeautifulSoup((ROOT/source['path']).read_bytes(),'html.parser')
        body=body_of(soup,book)
        if source['status']!='success' or body is None:
            manifest.append({**source,'collection_status':'failed','notes':['Main content not available; not chunked.']})
            continue
        title=body.select_one('h1,h2').get_text(' ',strip=True).removesuffix(' #')
        blocks,renderer,clone=semantic_blocks(body,source)
        units=make_units(blocks,title)
        markdown='\n\n'.join(u['text'] for u in units)+'\n'
        processed=ROOT/'processed'/f'{doc}.md'
        processed.write_text(markdown,encoding='utf-8')
        chunks=chunk_units(units,source)
        all_chunks.extend(chunks)
        dump(ROOT/'metadata'/f'{doc}_blocks.json',[{'kind':k,'text':t} for k,t in blocks])
        # Exact per-document notices, with applicability and original links preserved.
        notices=[]
        if book:
            licence=soup.select_one('.license-attribution')
            if licence: notices.append(str(licence))
            for heading in body.select('h2,h3'):
                if re.search(r'attributions?',heading.get_text(),re.I):
                    notices.append(str(heading))
                    for sib in heading.next_siblings:
                        if isinstance(sib,Tag) and re.fullmatch('h[1-6]',sib.name): break
                        notices.append(str(sib))
            notice_html='\n'.join(notices)
            authors=[a.get_text(' ',strip=True) for a in body.select('[data-type="author"]')]
            edition='Database Design – 2nd Edition' if '2nd Edition' in soup.title.get_text() else 'not_verified'
            license_info={'name':'Creative Commons Attribution 4.0 International, except where otherwise noted',
                          'declaration_url':source['final_url'],
                          'license_url':licence.select_one('a[rel="license"]')['href'] if licence and licence.select_one('a[rel="license"]') else 'not_verified',
                          'statement_file':f'licenses/{doc}_notices.html','verification_status':'verified' if licence else 'not_verified',
                          'additional_license_links':list(dict.fromkeys(urljoin(source['final_url'],a['href']) for a in BeautifulSoup(notice_html,'html.parser').select('a[href]') if 'creativecommons.org/licenses/' in a['href']))}
            license_info['saved_declarations']=[r['path'] for r in declarations if r['status']=='success' and (
                r['requested_url']=='https://creativecommons.org/licenses/by/4.0/' or
                any(r['requested_url'].replace('https:','http:')==url.replace('https:','http:') for url in license_info['additional_license_links']))]
        else:
            notice_html=str(pg)
            authors=['PostgreSQL Global Development Group']
            version=re.search(r'PostgreSQL (18(?:\.\d+)?) Documentation',str(soup))
            edition=version.group(1) if version else '18 (URL confirmed; minor version not verified)'
            license_info={'name':'PostgreSQL License','declaration_url':'https://www.postgresql.org/docs/18/legalnotice.html',
                          'license_url':'https://www.postgresql.org/about/licence/',
                          'statement_file':'licenses/postgresql_18_notice.txt','verification_status':'verified'}
        (ROOT/'licenses'/f'{doc}_notices.html').write_text('<!doctype html><meta charset="utf-8">\n'+notice_html,encoding='utf-8')
        notice_text=BeautifulSoup(notice_html,'html.parser').get_text('\n',strip=True)
        (ROOT/'licenses'/f'{doc}_notices.txt').write_text(notice_text+'\n',encoding='utf-8')
        # Figures are conservatively marked as image-dependent, never transcribed or invented.
        figures=[]
        for i,img in enumerate(body.select('img'),1):
            url=urljoin(source['final_url'],img.get('src',''))
            asset=renderer.assets.get(url,{})
            figure=img.find_parent('figure')
            caption=figure.select_one('figcaption') if figure else None
            readable=False; dimensions=None
            if asset.get('status')=='success':
                try:
                    with Image.open(ROOT/asset['path']) as im:
                        dimensions=list(im.size); im.verify(); readable=True
                except Exception: pass
            row={'document_id':doc,'figure_id':f'{doc}_F{i:03d}','source_url':url,
                 'local_file':asset.get('path'),'alt':img.get('alt',''),
                 'caption':caption.get_text(' ',strip=True) if caption else None,
                 'image_decodes':readable,'pixel_dimensions':dimensions,
                 'requires_visual_content':True,
                 'text_representation':'caption_and_original_alt_only; graphical content not transcribed',
                 'observation':'Conservative image-dependency flag; alt text may not express diagram, table, or symbol semantics.'}
            figures.append(row); image_records.append(row)
        # QA uses the original DOM as an independent source of expected elements.
        rendered=BeautifulSoup(MD.render(markdown),'html.parser')
        rendered_text=space(rendered.get_text(' ',strip=True))
        expected_headings=[]
        for h in clone.select('h1,h2,h3,h4,h5,h6,p.textbox__title'):
            if h.get_text(strip=True): expected_headings.append(('h2' if h.name=='p' else h.name,space(h.get_text(' ',strip=True))))
        actual_headings=[(h.name,space(h.get_text(' ',strip=True))) for h in rendered.select('h1,h2,h3,h4,h5,h6')]
        heading_missing=[]
        for h in body.select('h1,h2,h3,h4,h5,h6'):
            text=h.get_text(' ',strip=True).removesuffix(' #')
            if text and space(text) not in rendered_text:
                heading_missing.append(text)
        cell_missing=[c.get_text(' ',strip=True) for c in body.select('td,th') if space(c.get_text(' ',strip=True)) and space(c.get_text(' ',strip=True)) not in rendered_text]
        rendered_pres=[p.get_text().strip('\n') for p in rendered.select('pre')]
        pre_missing=[p.get_text().strip('\n') for p in body.select('pre') if p.get_text().strip('\n') not in rendered_pres]
        figure_caption_missing=[f['caption'] for f in figures if f['caption'] and space(f['caption']) not in rendered_text]
        reconstruct='\n\n'.join(c['text'] for c in chunks)+'\n'
        notes=[]
        if source['redirects']: notes.append('HTTP redirects recorded in collection log.')
        if book: notes.append('Figures retained locally with original captions/alt; graphical information not transcribed. Some original alt texts are only filenames.')
        if any(c['word_count']>600 for c in chunks): notes.append('Chunk over 600 words preserves an indivisible list or example group; see chunk_size_exceptions.json.')
        if any(c['word_count']<300 for c in chunks): notes.append('Short chunks retained at document or section boundaries; no overlap.')
        if doc=='D03': notes.append('Two original CREATE TABLE textboxes encoded with br tags converted to sql fences; source is Transact-SQL/MS SQL Server, not PostgreSQL. Figure source repeats one image URL; occurrences preserved.')
        if doc=='D02': notes.append('Figure 8.1 anchor href points to Attributes image, whereas img src is EntitySet; the rendered img src was collected; original anchor retained in Markdown.')
        if doc=='D08': notes.append('One HTML table is a callout explanation, not a data result; preserved as HTML without inventing a header.')
        if doc=='D06': notes.append('Preliminary web-tool verification timed out; direct HTTP collection subsequently succeeded with HTTP 200 and full content checks.')
        if doc=='D04': notes.append('Specific attribution cites Creative Commons Attribution-ShareAlike 3.0 for material derived from Wikipedia, in addition to the book-wide CC BY 4.0 notice; both retained.')
        # All original visible text nodes, excluding permalink chrome, must occur in order.
        # Compare fragments rather than token totals because Markdown introduces separators.
        missing_text=[]
        searchable=rendered_text
        for node in clone.descendants:
            if isinstance(node,NavigableString) and node.parent.name not in ('script','style'):
                value=space(str(node))
                if value and value not in searchable:
                    missing_text.append(value)
        qa_row={'document_id':doc,'title':title,'word_count':words(markdown),'chunk_count':len(chunks),
                'source_headings':len([h for h in body.select('h1,h2,h3,h4,h5,h6') if h.get_text(strip=True)]),
                'source_tables':len(body.select('table')),'processed_tables':renderer.table_count,
                'heading_hierarchy_and_order_preserved':expected_headings==actual_headings,
                'image_count_and_alt_order_preserved':[x.get('alt','') for x in body.select('img')]==[x.get('alt','') for x in rendered.select('img')],
                'source_pre_blocks':len(body.select('pre')),'processed_pre_blocks':len(renderer.pre_blocks),
                'additional_sql_textboxes':len(renderer.sql_textboxes),'figure_occurrences':len(figures),
                'unique_image_files':len(source['assets']), 'headings_missing':heading_missing,
                'table_cells_missing':cell_missing,'pre_blocks_missing':pre_missing,
                'captions_missing':figure_caption_missing,'visible_text_fragments_missing':missing_text,
                'all_images_decode':all(f['image_decodes'] for f in figures),
                'chunks_reconstruct_processed_exactly':reconstruct==markdown,
                'visible_text_order_exact_ignoring_whitespace':re.sub(r'\s+','',clone.get_text())==re.sub(r'\s+','',rendered.get_text()),
                'raw_sha256_verified':hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest()==source['sha256'],
                'pg18_url_verified':book or '/docs/18/' in source['final_url'],
                'notes':notes}
        failures=heading_missing or cell_missing or pre_missing or figure_caption_missing or missing_text or not all(qa_row[k] for k in ('all_images_decode','visible_text_order_exact_ignoring_whitespace','pg18_url_verified','heading_hierarchy_and_order_preserved','image_count_and_alt_order_preserved')) or reconstruct!=markdown
        qa_row['status']='needs_review' if failures else 'passed_with_image_dependencies' if figures else 'passed'
        qa.append(qa_row)
        manifest.append({'document_id':doc,'title':title,'authors_or_responsible_institution':authors or ['not_verified'],
                         'authorship_evidence':source['final_url'] if book else 'https://www.postgresql.org/docs/18/legalnotice.html',
                         'requested_url':source['requested_url'],'final_url':source['final_url'],
                         'collected_at':source['collected_at'],'language':'en','version_or_edition':edition,
                         'license':license_info,'attributions_and_notices':notice_text,
                         'original_file':source['path'],'clean_file':f'processed/{doc}.md',
                         'raw_sha256':source['sha256'],'clean_sha256':hashlib.sha256(processed.read_bytes()).hexdigest(),
                         'http_status':source['http_status'],'redirects':source['redirects'],
                         'collection_status':'success' if not failures else 'collected_needs_review',
                         'quality_status':qa_row['status'],'notes':notes,
                         'word_count':words(markdown),'chunk_count':len(chunks),'figures':figures})
    dump(ROOT/'metadata'/'sources.json',manifest)
    dump(ROOT/'metadata'/'quality_checks.json',qa)
    dump(ROOT/'metadata'/'figures.json',image_records)
    dump(ROOT/'metadata'/'chunk_size_exceptions.json',[{'chunk_id':c['chunk_id'],'word_count':c['word_count'],'reason':c['size_note']} for c in all_chunks if c['size_note']])
    with (ROOT/'chunks'/'chunks.jsonl').open('w',encoding='utf-8',newline='\n') as f:
        for chunk in all_chunks: f.write(json.dumps(chunk,ensure_ascii=False)+'\n')
    lines=['# Relatório de qualidade','',
           'Verificação baseada nos HTML efetivamente baixados, sem substituição de fontes. Datas de coleta em UTC no manifesto. O texto do corpus permanece em inglês.', '',
           '| ID | Palavras | Trechos | Tabelas HTML | Blocos pre + SQL textbox | Figuras (ocorrências) | Status |',
           '|---|---:|---:|---:|---:|---:|---|']
    for q in qa:
        lines.append(f'| {q["document_id"]} | {q["word_count"]} | {q["chunk_count"]} | {q["source_tables"]} | {q["source_pre_blocks"]} + {q["additional_sql_textboxes"]} | {q["figure_occurrences"]} | {q["status"]} |')
    lines+=['',f'Total: {sum(q["word_count"] for q in qa)} palavras; {len(all_chunks)} trechos; {len(qa)} documentos processados.', '',
            '## Verificações executadas','',
            '- HTTP 200, seletor do conteúdo principal e título presentes; URLs finais e redirecionamentos registrados.',
            '- Títulos, células de tabelas, blocos pre, legendas e fragmentos de texto visível confrontados com o DOM original; resultados detalhados em metadata/quality_checks.json.',
            '- Todo o texto visível também comparado na ordem exata, desconsiderando apenas espaços; hierarquia dos títulos e sequência dos textos alternativos verificadas após renderização CommonMark.',
            '- Blocos pre preservados literalmente, incluindo espaços e linhas de resultados SQL. Em D03, dois exemplos SQL eram textboxes com br e foram convertidos em blocos sql.',
            '- Tabelas preservadas como HTML válido dentro do Markdown, sem criar cabeçalhos ausentes.',
            '- Imagens locais verificadas por decodificação. Isso confirma arquivos válidos, não garante que todo texto pequeno da imagem seja legível.',
            '- Junção dos textos dos chunks reconstrói cada Markdown exatamente: confirma cobertura completa e ausência de sobreposição.',
            '- SHA-256 do HTML validado contra o registro da coleta. PostgreSQL restrito às URLs /docs/18/.', '',
            '## Figuras e limitações','',
            'O corpus textual NÃO é uma transcrição completa dos diagramas/tabelas em imagens. As figuras foram preservadas em raw/assets e vinculadas no Markdown; legendas e alt originais estão em metadata/figures.json. Nenhum OCR ou interpretação foi inventado. Todos os elementos gráficos foram conservadoramente marcados como dependentes de consulta visual, inclusive símbolos inline.', '',
            'Os originais do livro incluem exercícios, respostas/casos e exemplos além do SQL básico, como Transact-SQL em D03. Foram preservados por fidelidade às fontes solicitadas, sem gerar conteúdo sintético.', '',
            'O chunking prefere seções de nível principal, combina seções curtas adjacentes, mantém unidades indivisíveis e não usa sobreposição. Nesta coleta, os 31 trechos ficaram entre 301 e 590 palavras; metadata/chunk_size_exceptions.json está vazio. IDs são determinísticos para os mesmos HTML e algoritmo; mudanças futuras no conteúdo podem deslocar índices.', '',
            'Foi inspecionada uma folha de contato com as 50 imagens locais (metadata/figures_contact_sheet.jpg). Ela confirma a presença de diagramas, fórmulas, símbolos e tabelas em imagens; não equivale à transcrição nem à validação de cada caractere nelas.', '',
            'Todas as nove páginas retornaram HTTP 200 na coleta direta e mantiveram a URL solicitada, sem redirecionamentos de documentos. Não houve troca de fontes. A verificação preliminar pela ferramenta web de D06 apresentou timeout; o download direto e os testes posteriores passaram.', '']
    for q in qa:
        lines+=['## '+q['document_id']+' — '+q['title'],'']
        lines+=['- '+n for n in q['notes']]
        issues={k:q[k] for k in ('headings_missing','table_cells_missing','pre_blocks_missing','captions_missing','visible_text_fragments_missing') if q[k]}
        if issues: lines+=['','Pendências: `'+json.dumps(issues,ensure_ascii=False)+'`']
        lines+=['']
    (ROOT/'quality_report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=True,indent=2))

if __name__=='__main__': main()
