param([string]$ExtractionPath = 'data/extraction/sample.json')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not [IO.Path]::IsPathRooted($ExtractionPath)) { $ExtractionPath = Join-Path $projectRoot $ExtractionPath }
$json = [IO.File]::ReadAllText($ExtractionPath)
$schemaPath = Join-Path $projectRoot 'schemas/extraction.schema.json'
if (-not (Test-Json -Json $json -SchemaFile $schemaPath)) { throw 'JSON não atende ao esquema.' }
$data = $json | ConvertFrom-Json
$chunks = @{}
foreach ($file in @('corpus/chunks/chunks.jsonl','corpus/chunks/figure_supplements.jsonl')) {
    foreach ($line in [IO.File]::ReadLines((Join-Path $projectRoot $file))) {
        if (-not $line.Trim()) { continue }
        $chunk = $line | ConvertFrom-Json
        if ($chunks.ContainsKey($chunk.chunk_id)) { throw "Chunk duplicado: $($chunk.chunk_id)" }
        $chunks[$chunk.chunk_id] = $chunk
    }
}
foreach ($id in $data.input_chunk_ids) { if (-not $chunks.ContainsKey($id)) { throw "Entrada inexistente: $id" } }
$concepts = @{}
$names = @{}
foreach ($c in $data.concepts) {
    if ($concepts.ContainsKey($c.concept_id)) { throw "Conceito duplicado: $($c.concept_id)" }
    $name = $c.canonical_name.Trim().ToLowerInvariant()
    if ($names.ContainsKey($name)) { throw "Nome canônico duplicado: $name" }
    $concepts[$c.concept_id] = $c
    $names[$name] = $true
}
$relationIds = @{}
$triples = @{}
foreach ($r in $data.relations) {
    if ($relationIds.ContainsKey($r.relation_id)) { throw "Relação duplicada: $($r.relation_id)" }
    $relationIds[$r.relation_id] = $true
    foreach ($endpoint in @($r.source,$r.target)) { if (-not $concepts.ContainsKey($endpoint)) { throw "Conceito inexistente: $endpoint" } }
    $key = "$($r.source)|$($r.type)|$($r.target)"
    if ($triples.ContainsKey($key)) { throw "Tripla duplicada: $key" }
    $triples[$key] = $true
    if ($r.assertion_kind -eq 'inferred' -and $r.review_status -eq 'accepted') { throw 'Inferência não pode ser aceita nesta versão.' }
}
$evidenceCount = 0
foreach ($item in @($data.concepts) + @($data.relations)) {
    if ($item.review_status -eq 'flagged' -and [string]::IsNullOrWhiteSpace($item.review_note)) { throw 'Item flagged exige review_note.' }
    foreach ($e in $item.evidence) {
        if ($e.chunk_id -cnotin $data.input_chunk_ids) { throw "Evidência fora das entradas: $($e.chunk_id)" }
        if ([string]::IsNullOrWhiteSpace($e.quote)) { throw 'Citação vazia.' }
        if (-not $chunks[$e.chunk_id].text.Contains($e.quote, [StringComparison]::Ordinal)) { throw "Citação não literal em $($e.chunk_id): $($e.quote)" }
        $evidenceCount++
    }
}
Write-Output "OK: $($data.concepts.Count) conceitos; $($data.relations.Count) relações; $evidenceCount evidências literais; $($chunks.Count) trechos disponíveis."
Write-Output 'Validação estrutural concluída; não substitui revisão conceitual.'
