"""Read-only content/reference validation, plus an optional recorded QA result."""
from pathlib import Path
from collections import Counter
import hashlib
import json
from build_figure_supplements import ROOT, core_check, associations

def validate(write_report=False):
    core_files=core_check()
    records=json.loads((ROOT/'metadata'/'figure_transcriptions.json').read_text(encoding='utf-8'))
    figures=json.loads((ROOT/'metadata'/'figures.json').read_text(encoding='utf-8'))
    originals=[json.loads(l) for l in (ROOT/'chunks'/'chunks.jsonl').read_text(encoding='utf-8').splitlines()]
    supplements=[json.loads(l) for l in (ROOT/'chunks'/'figure_supplements.jsonl').read_text(encoding='utf-8').splitlines()]
    report=json.loads((ROOT/'metadata'/'figure_supplement_quality.json').read_text(encoding='utf-8'))
    original_ids={c['chunk_id']:c for c in originals}
    occurrence_ids={f['figure_id'] for f in figures}
    assert len(occurrence_ids)==len(figures)==51
    assert len(records)==51 and {r['figure_id'] for r in records}==occurrence_ids
    assert len({r['figure_id'] for r in records})==51
    assert len({r['original_image_file'] for r in records})==50
    assert len(supplements)==28 and len({c['chunk_id'] for c in supplements})==28
    assert not set(original_ids)&{s['chunk_id'] for s in supplements}
    expected_parents=associations(figures,originals)
    expected_locations=associations(figures,originals,include_offsets=True)
    supplement_by_id={c['chunk_id']:c for c in supplements}
    selected={r['figure_id']:r for r in records if r['decision']=='transcribe'}
    annotations=json.loads((ROOT/'scripts'/'figure_annotations.json').read_text(encoding='utf-8'))
    assert set(annotations)==set(selected)
    assert len(selected)==28
    for r in records:
        fid=r['figure_id']
        assert r['visual_review']['reviewed'] and r['visual_review']['individual_original_opened']
        assert r['parent_chunk_ids']==expected_parents[fid]
        assert r['processed_marker_offset']==expected_locations[fid]['processed_marker_offset']
        assert all(original_ids[p]['document_id']==r['document_id'] for p in r['parent_chunk_ids'])
        image=ROOT/r['original_image_file']
        assert image.is_file() and hashlib.sha256(image.read_bytes()).hexdigest()==r['original_image_sha256']
        assert all((ROOT/p).is_file() for p in r['license_evidence_files'])
        if r['decision']=='transcribe':
            assert r['literal_transcription']==annotations[fid]['literal']
            assert r['visual_description']==annotations[fid]['visual']
            assert r['pending']==annotations[fid]['pending']
            transcript=ROOT/r['transcription_file']
            assert transcript.is_file()
            assert hashlib.sha256(transcript.read_bytes()).hexdigest()==r['transcription_sha256']
            assert len(r['supplement_chunk_ids'])==1
            supplement=supplement_by_id[r['supplement_chunk_ids'][0]]
            assert supplement['figure_ids']==[fid]
            assert supplement['parent_chunk_ids']==r['parent_chunk_ids']
            assert supplement['transcription_status']==r['transcription_status']
            assert supplement['text'] in transcript.read_text(encoding='utf-8')
            assert r['literal_transcription'] in supplement['text']
            assert r['visual_description'] in supplement['text']
            assert r['interpretation'] in supplement['text']
            assert all(p in supplement['text'] for p in r['pending'])
        else:
            assert r['transcription_file'] is None and not r['supplement_chunk_ids']
            assert r['decision'] in ('already_covered_by_text','decorative_or_symbol','illegible')
    reused={r['figure_id']:r for r in records if r['reused_image_occurrences']}
    assert set(reused)=={'D03_F006','D03_F014'}
    assert reused['D03_F006']['original_image_file']==reused['D03_F014']['original_image_file']
    # These two occurrences can belong to the same original chunk; offsets must differ.
    assert reused['D03_F006']['processed_marker_offset']!=reused['D03_F014']['processed_marker_offset']
    assert {r['figure_id'] for r in records if r['transcription_status']=='partial'}=={'D02_F008','D09_F003'}
    for s in supplements:
        for field in ('chunk_id','document_id','figure_ids','parent_chunk_ids','text','source_url','language','content_type','original_image_files','transcription_file'):
            assert field in s and s[field]
        assert s['language']=='en' and s['content_type']=='figure_transcription'
        assert s['transcription_file'].startswith('supplements/figures/')
    attempts=json.loads((ROOT/'metadata'/'figure_resolution_collection.json').read_text(encoding='utf-8'))
    assert len(attempts)==14 and all(a['http_status']==404 for a in attempts)
    assert all((ROOT/a['path']).is_file() for a in attempts)
    assert report['figure_occurrences']==len(records) and report['supplement_chunks']==len(supplements)
    assert report['complete_transcriptions']==26 and report['partial_transcriptions']==2
    assert report['decision_counts']==dict(Counter(r['decision'] for r in records))
    for p in (ROOT/'README.md',ROOT/'quality_report.md'):
        t=p.read_text(encoding='utf-8')
        assert t.count('<!-- FIGURE_SUPPLEMENTS_BEGIN -->')==1
        assert t.count('<!-- FIGURE_SUPPLEMENTS_END -->')==1
    # Data orientation and preserved literal forms are explicitly checked.
    assert '| 1004 |  | 2 | 3256.9 | 01/14/92 | ac-315 |' in selected['D02_F012']['literal_transcription']
    assert '010839' in selected['D02_F013']['literal_transcription']
    assert '| a1 | b1 | c1 | d1 | e1 |' in selected['D04_F001']['literal_transcription']
    assert '| a3 | b2 | C1 | d1 | e1 |' in selected['D04_F001']['literal_transcription']
    assert '| Attribute Name | Sample Value | Sample Value | Sample Value |' in selected['D05_F003']['literal_transcription']
    result={'status':'passed','original_core_files_unchanged':core_files,'original_chunks_unchanged':31,
            'triaged_occurrences':51,'unique_original_images':50,'supplement_chunks':28,
            'complete_transcriptions':26,'partial_transcriptions':2,
            'all_parent_occurrences_resolved':True,'reused_image_contexts_distinguished':True,
            'unique_ids_no_original_collisions':True,'transcript_hashes_verified':True,
            'all_selected_have_visual_review':True,'all_original_images_opened_individually_recorded':True,
            'independent_human_review':False,'pending_details_explicit':True,
            'selected_table_layout_and_literal_sentinels_checked':True,
            'resolution_evidence_available':True}
    if write_report:
        (ROOT/'metadata'/'figure_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__': print(json.dumps(validate(write_report=True),indent=2))
