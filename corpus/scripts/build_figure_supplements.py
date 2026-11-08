"""Build supplements from reviewed, manually curated annotations; no OCR guesses.

Annotations are the editable source of the visual review, not automatically
inferred facts. Re-running this script performs packaging/association QA only;
it does not claim a fresh independent visual review.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
from prepare import ROOT, dump, words

REVIEW_DATE='2026-11-08'
PARTIAL={'D02_F008','D09_F003'}
COVERED={
 'D01_F001':('The shared repository/application-program concept is described in the body and alt. The drawing adds no essential relational schema.', 'Four Application Program boxes and three User callouts connect to the shared Database/DBMS drawing.'),
 'D01_F002':('The membership example already names the members and explains the shared membership/address. Interface fields and specimen barcodes are not essential additional model evidence for this stage.', 'Membership form above an eight-row member grid. Exact specimen UI values are intentionally not transcribed; this is conceptual coverage, not full image-text coverage.'),
 'D01_F003':('The body and detailed alt already list the departments, DBMS and shared banking data.', 'Personnel Dept., Account Dept. and Loan Dept. connect to DBMS and then Shared Database.'),
 'D02_F001':('The original alt already transcribes entity-set labels, the right-pointing arrow and EMPLOYEE entity type.', 'Entity set e1, e2, en; Represent in ER diagram arrow points right to EMPLOYEE.'),
 'D02_F002':('All four attribute names and their oval-to-entity connections are already in the body/alt.', 'EMPLOYEE rectangle connects to Name, Address, Birthdate and Salary ovals.'),
 'D02_F003':('The composite Address hierarchy and Number/Street/Suburb children are fully described in the body and alt.', 'Simple attribute callout points to Name; Composite attribute callout points to Address, which connects to Number, Street and Suburb.'),
 'D03_F001':('The body already explains the CustID join, enforcement and cascade options. The Access dialog adds no new essential rule.', 'Edit Relationships: Customer.CustID to Order.CustID; Enforce Referential Integrity checked, both Cascade options unchecked; Relationship Type One-To-Many.'),
 'D04_F002':('The reflexivity subsection states the same condition and result in words: if Y is a subset of X, X determines Y.', 'Visible equation: If Y ⊆ X, then X → Y.'),
 'D04_F003':('The augmentation subsection explicitly gives the same antecedent and consequent, including any Z.', 'Visible equation: If X → Y, then XZ → YZ for any Z.'),
 'D04_F004':('The transitivity subsection explicitly states X determines Y and Y determines Z, hence X determines Z.', 'Visible equation: If X → Y and Y → Z, then X → Z.'),
 'D04_F005':('The Union subsection explicitly states both premises and the joint consequent.', 'Visible equation: If X → Y and X → Z, then X → YZ.'),
 'D04_F006':('The Decomposition subsection explicitly states the joint premise and both separate consequents.', 'Visible equation: If X → YZ then X → Y and X → Z.'),
 'D09_F001':('The body explains that a database contains multiple tables; the exact small specimen schema is not needed for that illustration and a complete school ERD is separately transcribed from D02_F015.', 'A cylinder encloses three boxes labelled tblInstructor, tblOffering and tblCourse; this is conceptual coverage, not a transcription of every small field.'),
 'D09_F002':('Field/value organization and the illustrated field domains are explained in the Column/Domain text. The specimen ID-card values do not add an essential key or relationship.', 'Two-column Field Name/Data example with personal fields including First Name, Family Name, Nationality, Salary, Date of Birth, Marital Status, Shift, Place of issue and Valid until. Specimen values intentionally omitted.'),
 'D09_F004':('The body and Key Terms already state Relation/Table/File, Tuple/Row/Record and Attribute/Column/Field synonyms.', 'Three columns Formal Terms (Codd), Alternative 1, Alternative 2; rows Relation/Table/File, Tuple/Row/Record, Attribute/Column/Field.')
}
SYMBOLS={
 'D03_F003':'A horizontal stroke has a bar on the left and a crow\'s foot on the right. The body identifies it as one to many.',
 'D03_F004':'Two bars at the left; bar and crow\'s foot at the right. The body explicitly states minimum/maximum one/one and one/many.',
 'D03_F006':'Circle and crow\'s foot, zero or many; both shapes and their reading are already stated in the body.',
 'D03_F008':'Circle and bar, zero or one; the body explicitly gives that reading.',
 'D03_F010':'Two bars, one and only one; the body explicitly gives that reading.',
 'D03_F012':'Bar and crow\'s foot, mandatory one to many; the body explains the mandatory many side.',
 'D03_F014':'Same source image as D03_F006, reused for Figure 9.14. Circle and crow\'s foot are already discussed in the parent text.',
 'D03_F015':'Bar-circle-bar glyph used by the source as a disallowed-connectivity illustration. The source explicitly discusses it; no corrected notation is invented.'
}
SOURCE_ISSUES=[
 {'issue_id':'V01','document_id':'D01','figure_ids':['D01_F002'],'type':'source_data_discrepancy',
  'observation':'The screenshot address reads 8982 Rodent Lane, whereas the parent text states 8932 Rodent Lane.',
  'resolution':'Deferred; neither image nor original text changed. Screenshot fixture not selected for full transcription.'},
 {'issue_id':'V02','document_id':'D02','figure_ids':['D02_F008'],'type':'source_diagram_context_discrepancy',
  'observation':'The image visibly labels the PROJECT endpoint 1, while its surrounding section discusses many-to-many relationships and displays a JOIN relation.',
  'resolution':'Deferred; N/1 is transcribed as drawn, with no replacement by M/N.'},
 {'issue_id':'V03','document_id':'D04','figure_ids':['D04_F001'],'type':'source_prose_internal_contradiction',
  'observation':'The parent prose first says C → D and later says C does not determine D.',
  'resolution':'Deferred; exact data case preserved, with no new dependency conclusion.'},
 {'issue_id':'V04','document_id':'D04','figure_ids':['D04_F007'],'type':'source_dependency_grouping',
  'observation':'The parent prose places the composite ProjectNo, EmpNo → HrsWork dependency under Partial Dependencies. The upper/lower arrow groups are transcribed without reclassifying that prose.',
  'resolution':'Deferred conceptual review, outside this transcription stage.'}
]

def core_check():
    rows=(ROOT/'metadata'/'original_core.sha256').read_text(encoding='utf-8').splitlines()
    for row in rows:
        expected,relative=row.split('  ',1)
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected, 'Original changed: '+relative
    return len(rows)

def associations(figures,chunks,include_offsets=False):
    """Locate each occurrence sequentially, so reused image files do not merge parents."""
    by_doc=defaultdict(list)
    for c in chunks: by_doc[c['document_id']].append(c)
    cursors=defaultdict(int); result={}
    for f in figures:
        doc=f['document_id']; text=(ROOT/'processed'/(doc+'.md')).read_text(encoding='utf-8')
        needle='](../'+f['local_file']+')'
        start=text.find(needle,cursors[doc]); assert start>=0, f['figure_id']
        cursors[doc]=start+len(needle)
        offset=0; parents=[]
        for c in by_doc[doc]:
            end=offset+len(c['text'])
            if offset<=start<end: parents.append(c['chunk_id'])
            offset=end+2
        assert len(parents)==1, (f['figure_id'],parents)
        result[f['figure_id']]={'parent_chunk_ids':parents,'processed_marker_offset':start} if include_offsets else parents
    return result

def replace_appendix(path,body):
    marker='<!-- FIGURE_SUPPLEMENTS_BEGIN -->'
    initial=path.read_text(encoding='utf-8').split(marker)[0].rstrip()
    path.write_text(initial+'\n\n'+marker+'\n'+body.rstrip()+'\n<!-- FIGURE_SUPPLEMENTS_END -->\n',encoding='utf-8')

def main():
    baseline_count=core_check()
    figures=json.loads((ROOT/'metadata'/'figures.json').read_text(encoding='utf-8'))
    sources={s['document_id']:s for s in json.loads((ROOT/'metadata'/'sources.json').read_text(encoding='utf-8'))}
    originals=[json.loads(line) for line in (ROOT/'chunks'/'chunks.jsonl').read_text(encoding='utf-8').splitlines()]
    annotations=json.loads((ROOT/'scripts'/'figure_annotations.json').read_text(encoding='utf-8'))
    assert len(annotations)==28
    parents=associations(figures,originals)
    locations=associations(figures,originals,include_offsets=True)
    attempts=json.loads((ROOT/'metadata'/'figure_resolution_collection.json').read_text(encoding='utf-8'))
    attempted={r['figure_id']:r for r in attempts}
    out=ROOT/'supplements'/'figures'; out.mkdir(parents=True,exist_ok=True)
    records=[]; supplements=[]
    for f in figures:
        fid=f['figure_id']; doc=f['document_id']; selected=fid in annotations
        entry={
          'figure_id':fid,'document_id':doc,'caption':f['caption'],
          'source_url':sources[doc]['final_url'],'original_image_url':f['source_url'],
          'original_image_file':f['local_file'],'original_image_sha256':hashlib.sha256((ROOT/f['local_file']).read_bytes()).hexdigest(),
          'original_dimensions':f['pixel_dimensions'],'parent_chunk_ids':parents[fid],
          'processed_marker_offset':locations[fid]['processed_marker_offset'],
          'method':'direct visual inspection; no OCR; manually curated English annotation',
          'visual_review':{'reviewed':True,'date':REVIEW_DATE,'reviewer':'Codex','individual_original_opened':True,
                           'independent_human_review':False,'scope':'Individual image; parent text consulted. Some small selected figures also viewed enlarged without claiming recovered resolution.'},
          'resolution_attempt':({'requested_url':attempted[fid]['requested_url'],'http_status':attempted[fid].get('http_status'),
                                  'evidence_file':attempted[fid].get('path'),'use':'not used; candidate unavailable'} if fid in attempted else None),
          'transcription_file':None,'supplement_chunk_ids':[],
          'license_evidence_files':[f'licenses/{doc}_notices.html',f'licenses/{doc}_notices.txt','metadata/sources.json'],
          'source_issue_ids':[i['issue_id'] for i in SOURCE_ISSUES if fid in i['figure_ids']],
          'pending':[]
        }
        if selected:
            a=annotations[fid]; sid=fid+'_T01'; chunk_id=fid+'_S001'
            status='partial' if fid in PARTIAL else 'complete'
            interpretation='No additional business rules, keys, dependency conclusions, exercise answers or conceptual corrections are inferred. Verbal readings of visible notation are identified in the visual description and refer to the source context.'
            content=(f'# {sid} — Figure supplement\n\n'
                     f'Original caption: {f["caption"]}\n\n'
                     f'## Literal transcription\n\n{a["literal"]}\n\n'
                     f'## Visual description / source notation\n\n{a["visual"]}\n\n'
                     f'## Interpretation boundary\n\n{interpretation}\n\n'
                     f'## Uncertainty and deferred source issues\n\n'+
                     ('\n'.join('- '+p for p in a['pending']) if a['pending'] else 'No unresolved transcription detail identified in the selected visual content.')+'\n')
            relative=f'supplements/figures/{fid}.md'
            provenance=(f'Document: {doc}  \nFigure occurrence: {fid}  \nSupplement: {sid}  \n'
                        f'Parent chunks: {", ".join(parents[fid])}  \n'
                        f'Source page: {sources[doc]["final_url"]}  \n'
                        f'Original image URL: {f["source_url"]}  \n'
                        f'Original image file: {f["local_file"]}  \n'
                        f'Review: {REVIEW_DATE}, Codex visual inspection; {status}; no independent human review.  \n'
                        f'License/attribution evidence: licenses/{doc}_notices.html and metadata/sources.json.\n\n'
                        'This is a figure-derived supplement, separate from the page-body transcription. '
                        'Table headers introduced to organize schema labels and bracketed descriptions of icons are editorial notation. '
                        'Empty cells in data tables preserve visible blanks; empty marker cells mean no marker was visible.\n\n')
            (ROOT/relative).write_text(content+'\n---\n\n'+provenance,encoding='utf-8')
            entry.update(decision='transcribe',decision_reason=a['reason'],
                         transcription_status=status,transcription_file=relative,supplement_id=sid,
                         supplement_chunk_ids=[chunk_id],pending=a['pending'],
                         literal_transcription=a['literal'],visual_description=a['visual'],interpretation=interpretation,
                         uncertainty_in_transcription=fid in PARTIAL,
                         transcription_sha256=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest())
            supplements.append({'chunk_id':chunk_id,'supplement_id':sid,'document_id':doc,'figure_ids':[fid],
                                'parent_chunk_ids':parents[fid],'text':content,'source_url':sources[doc]['final_url'],
                                'language':'en','content_type':'figure_transcription',
                                'original_image_files':[f['local_file']],'original_image_urls':[f['source_url']],
                                'transcription_file':relative,'transcription_status':status,
                                'source_issue_ids':entry['source_issue_ids'],'uncertainties':a['pending'],
                                'word_count':words(content),'license_evidence_files':entry['license_evidence_files']})
        elif fid in COVERED:
            reason,observation=COVERED[fid]
            entry.update(decision='already_covered_by_text',decision_reason=reason,visual_observation=observation,
                         coverage_scope='Essential educational role covered; not a claim that every specimen value is transcribed.',
                         transcription_status='not_selected',uncertainty_in_transcription=False)
        elif fid in SYMBOLS:
            entry.update(decision='decorative_or_symbol',decision_reason='Standalone notation already explicitly explained in the parent text; no separate retrieval supplement needed.',
                         visual_observation=SYMBOLS[fid],transcription_status='not_selected',uncertainty_in_transcription=False)
        else:
            raise AssertionError('Untriaged figure '+fid)
        entry['reused_image_occurrences']=[x['figure_id'] for x in figures if x['local_file']==f['local_file'] and x['figure_id']!=fid]
        records.append(entry)
    dump(ROOT/'metadata'/'figure_transcriptions.json',records)
    dump(ROOT/'metadata'/'figure_source_issues.json',SOURCE_ISSUES)
    with (ROOT/'chunks'/'figure_supplements.jsonl').open('w',encoding='utf-8',newline='\n') as stream:
        for s in supplements: stream.write(json.dumps(s,ensure_ascii=False)+'\n')
    decisions=dict(Counter(r['decision'] for r in records))
    perdoc=[]
    for doc in sorted(sources):
        rr=[r for r in records if r['document_id']==doc]
        perdoc.append({'document_id':doc,'occurrences':len(rr),
                       'transcribed':sum(r['decision']=='transcribe' for r in rr),
                       'complete':sum(r['transcription_status']=='complete' for r in rr),
                       'partial':sum(r['transcription_status']=='partial' for r in rr),
                       'covered':sum(r['decision']=='already_covered_by_text' for r in rr),
                       'symbols':sum(r['decision']=='decorative_or_symbol' for r in rr)})
    qa={'original_core_files_unchanged':baseline_count,'figure_occurrences':len(records),
        'unique_original_images':len({r['original_image_file'] for r in records}),
        'decision_counts':decisions,'supplement_chunks':len(supplements),
        'complete_transcriptions':sum(r['transcription_status']=='complete' for r in records),
        'partial_transcriptions':sum(r['transcription_status']=='partial' for r in records),
        'pending_legibility_figures':sorted(PARTIAL),'source_issues_deferred':len(SOURCE_ISSUES),
        'supplement_words':sum(s['word_count'] for s in supplements),
        'resolution_attempts':len(attempts),'resolution_attempt_http_statuses':dict(Counter(str(a.get('http_status')) for a in attempts)),
        'larger_images_used':0,'per_document':perdoc}
    dump(ROOT/'metadata'/'figure_supplement_quality.json',qa)
    qa_text='''## Complementos visuais — triagem e transcrição

Esta etapa mantém intactos os HTML, imagens, Markdown e 31 chunks originais; 69 arquivos do núcleo conferidos com metadata/original_core.sha256. O manifesto inicial e seus indicadores de dependência visual permanecem como registro histórico. A cobertura nova está em metadata/figure_transcriptions.json.

Foram abertas individualmente as 50 imagens originais e avaliadas as 51 ocorrências; a imagem reutilizada de D03 tem dois registros e dois contextos associados. A folha de contato não foi usada como substituto dessa inspeção. Não houve OCR. Ampliações locais serviram apenas à leitura dos pixels existentes, sem declarar resolução recuperada ou revisão humana independente.

| Documento | Ocorrências | Transcritas | Completas | Parciais | Já cobertas no texto | Símbolos explicados |
|---|---:|---:|---:|---:|---:|---:|
'''
    for row in perdoc:
        qa_text+='| '+ ' | '.join(str(row[k]) for k in ('document_id','occurrences','transcribed','complete','partial','covered','symbols'))+' |\n'
    qa_text+='''
Total: **51 ocorrências triadas: 28 selecionadas/transcritas, 15 com função didática já coberta pelo texto e 8 símbolos já explicados**. Nenhuma figura inteira foi classificada como ilegível. Das 28 transcrições, **26 estão completas e 2 têm detalhes incertos explicitamente marcados**. Os valores de telas ilustrativas não essenciais não foram todos transcritos; “já coberta” refere-se à função didática, e essa limitação está registrada por ocorrência.

Foram produzidos **28 novos trechos**, separados em chunks/figure_supplements.jsonl, com IDs Dxx_Fxxx_S001, sem alterar IDs ou texto dos 31 chunks de página. As transcrições se encontram em supplements/figures/. São unidades por figura e podem ter menos de 300 palavras; a faixa 300–600 do corpus original não foi artificialmente imposta a uma fórmula/tabela/diagrama indivisível.

Pendências de legibilidade: D02_F008 (extensão do sublinhado de StartDate na linha JOIN) e D09_F003 (ID, ano e inicial do autor parcialmente encobertos por setas na última linha). Os campos não confirmados estão marcados, sem reconstrução por sequência ou por contexto. Foram tentadas 14 versões maiores no mesmo diretório de uploads, retirando o sufixo de tamanho do nome; todas retornaram HTTP 404. Essas URLs eram candidatas explicitamente identificadas, não fontes substitutas. Respostas e proveniência constam de metadata/figure_resolution_collection.json e supplements/provenance/responses/. Nenhuma imagem nova foi usada nem incorporada ao corpus original.

Quatro observações de divergência da fonte foram separadas em metadata/figure_source_issues.json (endereço na imagem/texto de D01, endpoint N/1 de D02, contradição C → D no texto de D04 e agrupamento de dependências em D04). São pendências para a revisão conceitual posterior; não houve correção silenciosa nem solução de exercícios.

QA dos complementos: cobertura de todas as 51 ocorrências; IDs únicos; vínculos a documentos, imagens e chunks existentes; reutilização de imagem preservada; arquivos e hashes das transcrições; separação de transcrição literal, descrição visual e limites de interpretação; inclusão no inventário e no ZIP. As tabelas de valores foram mantidas na orientação original, incluindo zeros iniciais, casas decimais, células vazias, rótulos repetidos e diferenças de caixa. Esquemas indicam somente chaves e marcas realmente visíveis; mínimos de cardinalidade não foram inventados em diagramas com apenas chave/infinito ou 1/infinito.

Validação de conteúdo: revisão visual por Codex, sem verificação independente por outra pessoa. Esta etapa melhora a recuperação textual das figuras essenciais, mas não transforma as fontes em material conceitualmente corrigido.
'''
    replace_appendix(ROOT/'quality_report.md',qa_text)
    readme=f'''## Complementos das figuras — entrega adicional

O núcleo original continua com **9 documentos, 31 chunks e 13.377 palavras**, sem alteração. A etapa visual acrescenta **28 transcrições/descrições e 28 trechos separados**; são {qa['supplement_words']} palavras nesses trechos, contadas pelo mesmo método de renderização. As contagens originais não incluem os complementos.

- `supplements/figures/Dxx_Fxxx.md`: um complemento por figura selecionada, com IDs próprios e proveniência. O texto em inglês separa rótulos/valores literais, descrição das marcas visuais e limites de interpretação. Colchetes descrevem símbolos ou incertezas editoriais e não simulam texto da imagem.
- `chunks/figure_supplements.jsonl`: novos registros com `content_type=figure_transcription`, `figure_ids`, `parent_chunk_ids`, imagens originais e caminho da transcrição. **Carregue este arquivo além de chunks/chunks.jsonl**, preservando o tipo e a proveniência. Um suplemento não é uma citação literal do corpo da página.
- `metadata/figure_transcriptions.json`: um registro para cada uma das 51 ocorrências, com triagem, justificativa, método, revisão visual, status, arquivo e pendências. Quinze ilustrações têm a função didática já coberta; oito símbolos já estão explicados no texto. A classificação não promete a transcrição de cada valor de telas não essenciais.
- `metadata/figure_supplement_quality.json`: contagens e QA; `metadata/figure_source_issues.json`: divergências das fontes deixadas para revisão conceitual.
- `metadata/original_core.sha256`: baseline dos 69 arquivos originais preservados; `metadata/files.sha256`: inventário da entrega atual inteira.
- `scripts/figure_annotations.json`: anotações visuais curadas, fonte dos novos arquivos. `scripts/build_figure_supplements.py`: geração determinística dos complementos, associações e seção adicional dos relatórios. Não realiza uma nova revisão visual ao ser executado.
- `metadata/figure_resolution_collection.json` e `supplements/provenance/responses/`: evidências das 14 tentativas de imagens maiores, todas HTTP 404. Respostas HTML de erro são apenas evidência de coleta, não imagens nem texto para recuperação.

**26 transcrições completas e 2 parciais**: a extensão do sublinhado de StartDate em D02_F008 e caracteres sob setas em D09_F003 não puderam ser confirmados. Não foi preciso marcar nenhuma imagem inteira como ilegível. A ampliação de pixels não foi tratada como aumento de resolução. Não houve OCR nem revisão humana independente. As atribuições/licenças das fontes continuam em licenses e são referenciadas por cada complemento; não se presumiu uma licença única para todo o material.

Para reconstruir a entrega sobre estes snapshots, execute `python corpus/scripts/build_figure_supplements.py` depois de prepare.py (se este for reexecutado) e **antes de package.py**. O builder repõe suas seções adicionais em README/quality_report sem duplicá-las. A coleta original não precisa ser reexecutada. `python corpus/scripts/validate_figure_supplements.py` confere o núcleo e os complementos; package.py também exige essa validação quando houver complementos. As tentativas de maior resolução podem ser repetidas com fetch_figure_originals.py, mas não são necessárias para reproduzir as transcrições já revisadas.
'''
    replace_appendix(ROOT/'README.md',readme)
    print(json.dumps(qa,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
