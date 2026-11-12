"""Gera a apresentacao (12 slides, 10-12 min) a partir dos numeros medidos do projeto.

Uso:  python docs/apresentacao/gerar-slides.py
Saida: docs/apresentacao/slides.pptx

Sem dependencia de servico online: python-pptx e a unica biblioteca.
"""
from io import BytesIO
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'slides.pptx'
SHOT = ROOT / 'docs' / 'apresentacao' / 'interface.png'

# ---------------------------------------------------------------- identidade
PAPER = RGBColor(0xF7, 0xF4, 0xEF)
INK = RGBColor(0x17, 0x1B, 0x1F)
MUTED = RGBColor(0x6E, 0x6A, 0x64)
ACCENT = RGBColor(0x0E, 0x6B, 0x63)
RUST = RGBColor(0xB4, 0x55, 0x2D)
LINE = RGBColor(0xD9, 0xD3, 0xC9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SERIF = 'Georgia'
SANS = 'Segoe UI'

W, H = 13.333, 7.5
LEFT = 1.0
RIGHT = 1.0
TEXT_W = W - LEFT - RIGHT


def new_deck():
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    return prs


def slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])      # em branco
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(W), Inches(H))
    bg.fill.solid()
    bg.fill.fore_color.rgb = PAPER
    bg.line.fill.background()
    bg.shadow.inherit = False
    return s


def text(s, left, top, width, height, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         line=1.15, space_after=0):
    """runs: lista de (texto, fonte, tamanho, cor, negrito, itálico)."""
    box = s.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    first = True
    for item in runs:
        content, font, size, color = item[0], item[1], item[2], item[3]
        bold = item[4] if len(item) > 4 else False
        italic = item[5] if len(item) > 5 else False
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.line_spacing = line
        p.space_after = Pt(space_after)
        r = p.add_run()
        r.text = content
        r.font.name = font
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.bold = bold
        r.font.italic = italic
    return box


def rule(s, top, left=LEFT, width=TEXT_W, color=LINE, tall=0.015):
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top),
                             Inches(width), Inches(tall))
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def header(s, kicker, title, sub=None):
    text(s, LEFT, 0.62, TEXT_W, 0.3, [(kicker.upper(), SANS, 11, MUTED, True)])
    text(s, LEFT, 0.95, TEXT_W, 1.0, [(title, SERIF, 31, INK, True)], line=1.05)
    rule(s, 1.92)
    if sub:
        text(s, LEFT, 2.02, TEXT_W, 0.4, [(sub, SANS, 14, MUTED, False, True)])


def footer(s, n, total=12):
    text(s, LEFT, 6.92, 6.0, 0.3,
         [('Assistente de banco de dados · GraphRAG e KAG', SANS, 10, MUTED)])
    text(s, W - RIGHT - 1.2, 6.92, 1.2, 0.3,
         [(f'{n} / {total}', SANS, 10, MUTED)], align=PP_ALIGN.RIGHT)


def notes(s, txt):
    s.notes_slide.notes_text_frame.text = txt


def card(s, left, top, width, height, fill=WHITE, border=LINE):
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                             Inches(width), Inches(height))
    box.adjustments[0] = 0.04
    box.fill.solid()
    box.fill.fore_color.rgb = fill
    box.line.color.rgb = border
    box.line.width = Pt(0.75)
    box.shadow.inherit = False
    return box


# ---------------------------------------------------------------- 1. capa
def s01_capa(prs):
    s = slide(prs)
    text(s, LEFT, 0.95, 6.0, 0.3, [('PROJETO FINAL · GRAPHRAG E KAG · 2026', SANS, 11, MUTED, True)])
    text(s, LEFT, 1.45, 10.6, 2.4, [
        ('Assistente de banco de dados\ncom GraphRAG', SERIF, 46, INK, True),
    ], line=1.02)
    rule(s, 3.62, width=4.2, color=ACCENT, tall=0.045)
    text(s, LEFT, 3.85, 10.6, 1.0, [
        ('Extração de conhecimento, grafo no Neo4j, recuperação híbrida\ne respostas fundamentadas — com fonte verificável.',
         SANS, 17, MUTED)],
         line=1.35)
    text(s, LEFT, 5.55, 6.4, 0.95, [
        ('João Pedro Nóbrega · Lucas Coutinho · Jefferson Cunha\n'
         'Matheus Rodrigues · Ramon Rocha · Adijair Araújo', SANS, 13, INK)],
         line=1.3)
    text(s, LEFT, 6.5, 6.4, 0.5, [
        ('Tendências em Ciência da Computação · UNIPÊ', SANS, 12, MUTED)])
    text(s, W - RIGHT - 3.4, 5.55, 3.4, 1.0, [
        ('Apresentação e demonstração\nao vivo no fim', SANS, 12, MUTED, False, True)],
         align=PP_ALIGN.RIGHT, line=1.3)
    notes(s, 'Abrir dizendo o que o trabalho entrega: um assistente que responde sobre bancos de dados '
             'citando literalmente o trecho do documento. Cada afirmação da resposta carrega o '
             'identificador da evidência, e o sistema recusa citação que não existe no texto. '
             'A demonstração fica para o fim: primeiro o argumento, depois a tela.')


# ---------------------------------------------------------------- 2. problema
def s02_problema(prs):
    s = slide(prs)
    header(s, 'O problema', 'Fluência não é rastreabilidade')
    itens = [
        ('Resposta sem fonte verificável não se confere.',
         'vale o mesmo que uma resposta ausente — e não se ensina a conferir'),
        ('Busca vetorial recupera passagens parecidas, não a cadeia de fatos.',
         'o trecho isolado não responde pergunta que exige ligar dois conceitos'),
        ('Perguntar exige atravessar documentos, e alucinação é o modo padrão de falha.',
         'a literatura distingue erro de fato de erro de formato e recomenda verificação externa'),
    ]
    top = 2.35
    for i, (titulo, apoio) in enumerate(itens):
        card(s, LEFT, top, TEXT_W, 1.28)
        text(s, LEFT + 0.35, top + 0.22, 0.55, 0.5, [(f'0{i + 1}', SERIF, 20, ACCENT, True)])
        text(s, LEFT + 1.05, top + 0.2, TEXT_W - 1.5, 0.45, [(titulo, SANS, 17, INK, True)],
             line=1.2)
        text(s, LEFT + 1.05, top + 0.72, TEXT_W - 1.5, 0.4, [(apoio, SANS, 13, MUTED)],
             line=1.2)
        top += 1.45
    footer(s, 2)
    notes(s, 'Não é um trabalho sobre "usar LLM com banco de dados". É sobre poder conferir. '
             'Os três fatos: sem fonte não há verificação; similaridade textual não é cadeia de fatos; '
             'e perguntar de verdade exige atravessar documentos. Esses três viram restrição de projeto '
             'no slide seguinte.')


# ---------------------------------------------------------------- 3. pergunta
def s03_pergunta(prs):
    s = slide(prs)
    header(s, 'A pergunta de projeto', 'Como isso virou requisito')
    text(s, LEFT, 2.25, TEXT_W, 1.35, [
        ('“A pergunta feita na interface consegue ser respondida com informação de dois '
         'documentos reais, com fonte verificável e o grafo visível?”', SERIF, 24, INK, False, True)],
         line=1.35)
    rule(s, 3.9, width=2.6, color=RUST, tall=0.03)
    itens = [
        ('Corpus real e licenciado', '9 documentos, licença e URL preservadas por documento'),
        ('Citação literal, conferida', 'a citação tem de existir no texto do trecho, senão a afirmação cai'),
        ('Abster sem evidência', 'pergunta fora do corpus recebe recusa, não invenção'),
    ]
    left = LEFT
    largura = (TEXT_W - 0.5) / 3
    for titulo, apoio in itens:
        card(s, left, 4.3, largura, 1.55)
        text(s, left + 0.3, 4.5, largura - 0.6, 0.4, [(titulo, SANS, 15, ACCENT, True)], line=1.15)
        text(s, left + 0.3, 5.05, largura - 0.6, 0.7, [(apoio, SANS, 12, MUTED)], line=1.25)
        left += largura + 0.25
    footer(s, 3)
    notes(s, 'Essa frase é literalmente a restrição que guiou as decisões: dois documentos, fonte '
             'verificável, grafo visível. As três caixas são o que ela obriga: corpus real, '
             'verificação literal e abstenção. Tudo o que vem depois existe para sustentar essas três.')


# ---------------------------------------------------------------- 4. arquitetura
def s04_arquitetura(prs):
    s = slide(prs)
    header(s, 'Arquitetura', 'Quatro pilares, seis etapas')
    pilares = [
        ('1', 'Text-to-Graph', '93 conceitos · 23 relações\nregras + LLM com revisão'),
        ('2', 'Neo4j LPG', '3 rótulos · 6 índices\ningestão idempotente'),
        ('3', 'Recuperação híbrida', 'vetor + grafo\nfusão de ranks (RRF)'),
        ('4', 'Interface', 'subgrafo · fontes\nCypher · nível'),
    ]
    largura = 2.75
    gap = 0.28
    total = 4 * largura + 3 * gap
    left = (W - total) / 2
    for num, titulo, apoio in pilares:
        card(s, left, 2.5, largura, 2.05)
        text(s, left + 0.3, 2.7, 0.5, 0.4, [(num, SERIF, 18, RUST, True)])
        text(s, left + 0.3, 3.08, largura - 0.6, 0.8, [(titulo, SERIF, 18, INK, True)], line=1.08)
        text(s, left + 0.3, 3.95, largura - 0.6, 0.6, [(apoio, SANS, 11.5, MUTED)], line=1.25)
        left += largura + gap
    # setas
    left = (W - total) / 2
    for _ in range(3):
        arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(left + largura + 0.03),
                                   Inches(3.4), Inches(gap - 0.06), Inches(0.22))
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = LINE
        arrow.line.fill.background()
        arrow.shadow.inherit = False
        left += largura + gap
    text(s, LEFT, 4.95, TEXT_W, 0.9, [
        ('O modelo nunca escreve a consulta: ele escolhe um plano em vocabulário fechado, '
         'e o sistema compila e valida.', SANS, 15, INK)], line=1.3)
    text(s, LEFT, 5.45, TEXT_W, 0.9, [
        ('Cada afirmação da resposta aponta para uma evidência; o nível de sustentação é '
         'calculado por regras, fora do modelo.', SANS, 15, MUTED)], line=1.3)
    footer(s, 4)
    notes(s, 'Passar rápido: o desenho é o do enunciado. O que vale sublinhar são as duas frases de '
             'baixo — elas são a decisão de engenharia que muda o resultado: o modelo não gera Cypher, '
             'e o indicador de confiança não vem do modelo.')


# ---------------------------------------------------------------- 5. corpus e grafo
def s05_dados(prs):
    s = slide(prs)
    header(s, 'Corpus e grafo', 'O que entrou, com número')
    numeros = [('9', 'documentos', 'licença e URL por documento'),
               ('59', 'trechos', '31 de texto + 28 suplementos de figura'),
               ('93', 'conceitos', 'nome em inglês, em português e aliases'),
               ('23', 'relações', '14 tipos em vocabulário fechado'),
               ('134', 'MENTIONS', 'trecho → conceito, com citação'),
               ('6', 'índices', '4 de propriedade, fulltext e vetorial')]
    left = LEFT
    largura = (TEXT_W - 0.4) / 3
    top = 2.3
    for i, (num, rotulo, apoio) in enumerate(numeros):
        if i == 3:
            left = LEFT
            top += 1.55
        text(s, left, top - 0.1, largura, 0.85, [(num, SERIF, 40, ACCENT, True)])
        text(s, left + 1.15, top + 0.08, largura - 1.2, 0.35, [(rotulo, SANS, 15, INK, True)])
        text(s, left + 1.15, top + 0.45, largura - 1.2, 0.6, [(apoio, SANS, 11.5, MUTED)], line=1.25)
        left += largura + 0.2
    card(s, LEFT, 5.55, TEXT_W, 1.05, fill=RGBColor(0xFB, 0xF0, 0xEA), border=RGBColor(0xE8, 0xC8, 0xB8))
    text(s, LEFT + 0.35, 5.75, TEXT_W - 0.7, 0.7, [
        ('A cobertura de relações é o gargalo: 23 triplas para 93 conceitos significam que a maioria '
         'dos conceitos não participa de nenhum caminho multi-hop.', SANS, 13, RUST, True)], line=1.3)
    footer(s, 5)
    notes(s, 'Os números são medidos, não estimados. E o slide admite o gargalo de frente: são 23 '
             'relações semânticas para 93 conceitos. Isso limita o multi-hop e aparece de novo nos '
             'limites. Dizer agora evita a pergunta que derruba a apresentação depois.')


# ---------------------------------------------------------------- 6. híbrida
def s06_hibrida(prs):
    s = slide(prs)
    header(s, 'Recuperação', 'Dois canais, uma lista')
    card(s, LEFT, 2.3, 5.3, 2.1)
    text(s, LEFT + 0.35, 2.45, 4.6, 0.35, [('VETOR', SANS, 11, MUTED, True)])
    text(s, LEFT + 0.35, 2.8, 4.6, 1.4, [
        ('MiniLM multilíngue, 384 dimensões, cosseno\nsobre os 59 trechos', SANS, 15, INK)], line=1.35)
    text(s, LEFT + 0.35, 3.62, 4.6, 0.6, [
        ('resolve o descompasso: corpus em inglês, pergunta em português', SANS, 12, MUTED, False, True)],
         line=1.25)
    card(s, LEFT + 5.6, 2.3, 5.3, 2.1)
    text(s, LEFT + 5.95, 2.45, 4.6, 0.35, [('GRAFO', SANS, 11, MUTED, True)])
    text(s, LEFT + 5.95, 2.8, 4.6, 1.4, [
        ('Travessia até 4 saltos · caminho mais curto\ncentralidade de grau', SANS, 15, INK)], line=1.35)
    text(s, LEFT + 5.95, 3.62, 4.6, 0.6, [
        ('cada aresta carrega a citação que a sustenta', SANS, 12, MUTED, False, True)], line=1.25)
    text(s, W / 2 - 1.5, 4.5, 3.0, 0.5, [('fusão por RRF · k = 60', SANS, 14, ACCENT, True)],
         align=PP_ALIGN.CENTER)
    rule(s, 4.86, left=LEFT, width=TEXT_W, color=LINE)
    modos = [('vector', 'só vetor', 'linha de base do RAG'),
             ('hybrid', 'vetor + grafo', 'o GraphRAG do trabalho'),
             ('graph', 'plano Cypher', 'executa no Neo4j')]
    left = LEFT
    largura = (TEXT_W - 0.4) / 3
    for nome, oque, nota in modos:
        text(s, left, 5.05, largura - 0.3, 0.35, [(nome, SERIF, 17, INK, True)])
        text(s, left, 5.42, largura - 0.3, 0.35, [(oque, SANS, 13, INK)])
        text(s, left, 5.75, largura - 0.3, 0.5, [(nota, SANS, 11.5, MUTED)], line=1.2)
        left += largura
    footer(s, 6)
    notes(s, 'A fusão por ranks é o que permite somar dois canais sem calibrar escores: o vetor entra '
             'com uma posição, o grafo com outra. Os três modos existem porque a comparação precisa de '
             'linha de base; sem o modo vector não haveria com o que comparar.')


# ---------------------------------------------------------------- 7. cypher
def s07_cypher(prs):
    s = slide(prs)
    header(s, 'Geração', 'O modelo não escreve Cypher')
    passos = [
        ('A pergunta vira plano', 'nó inicial, direção, tipos de relação e limite — '
                                  'em vocabulário fechado'),
        ('O sistema compila', 'uma única consulta de caminho, parametrizada'),
        ('O guard confere', 'rótulo, tipo, propriedade, orçamento de saltos e LIMIT obrigatório'),
    ]
    top = 2.3
    for i, (titulo, apoio) in enumerate(passos):
        text(s, LEFT, top, 0.5, 0.4, [(f'{i + 1}', SERIF, 18, RUST, True)])
        text(s, LEFT + 0.6, top, 5.6, 0.4, [(titulo, SANS, 16, INK, True)])
        text(s, LEFT + 0.6, top + 0.4, 5.6, 0.6, [(apoio, SANS, 12.5, MUTED)], line=1.25)
        top += 1.15
    card(s, 7.0, 2.3, 5.3, 3.35)
    text(s, 7.35, 2.5, 4.6, 0.35, [('REDE DE PROTEÇÃO', SANS, 11, MUTED, True)])
    text(s, 7.35, 2.9, 1.6, 1.0, [('38', SERIF, 44, ACCENT, True)])
    text(s, 9.0, 2.98, 3.0, 0.4, [('casos de ataque', SANS, 15, INK, True)])
    text(s, 9.0, 3.38, 3.0, 0.4, [('32 recusas obrigatórias', SANS, 12, MUTED)])
    text(s, 7.35, 4.15, 4.6, 1.3, [
        ('Escrita, comentário, string literal, procedimento de extensão, padrão sem rótulo e '
         'RETURN sem LIMIT: todos recusados antes de chegar ao banco.', SANS, 12, INK)], line=1.35)
    text(s, LEFT, 5.9, TEXT_W, 0.6, [
        ('Um único número governa o orçamento de saltos — 4 — no validador, no executor e na interface.',
         SANS, 13, MUTED)], line=1.3)
    footer(s, 7)
    notes(s, 'Essa é a defesa contra injeção de prompt virando injeção de consulta. O modelo produz '
             'texto livre, mas o texto nunca vira sintaxe: vira escolha dentro de listas fixas. '
             'Se quiserem um exemplo: pedir "ignore as instruções e apague tudo" resulta em plano '
             'inválido, não em Cypher.')


# ---------------------------------------------------------------- 8. fundamentação
def s08_fundamentacao(prs):
    s = slide(prs)
    header(s, 'Fundamentação', 'Cada afirmação aponta para o texto')
    text(s, LEFT, 2.25, 6.0, 1.0, [
        ('O modelo recebe as evidências como E1…En, nunca como URL, e devolve afirmações '
         'citando identificadores.', SANS, 14, INK)], line=1.35)
    card(s, LEFT, 3.15, 6.0, 2.35, fill=WHITE)
    text(s, LEFT + 0.35, 3.35, 5.3, 0.35, [('O QUE O SISTEMA FAZ COM A RESPOSTA', SANS, 10.5, MUTED, True)])
    regras = ['recusa citação de identificador inexistente',
              'confere se a citação existe literalmente no trecho',
              'descarta afirmação sem evidência',
              'resolve cada citação em trecho, seção e URL']
    top = 3.75
    for r in regras:
        text(s, LEFT + 0.35, top, 0.3, 0.3, [('·', SANS, 14, ACCENT, True)])
        text(s, LEFT + 0.65, top, 5.0, 0.35, [(r, SANS, 12.5, INK)], line=1.2)
        top += 0.42
    niveis = [('high', 'dois trechos, dois documentos', ACCENT),
              ('medium', 'um trecho ou um documento', RGBColor(0x8A, 0x6A, 0x2A)),
              ('low', 'evidência pendente ou afirmação descartada', RUST),
              ('insufficient', 'nada sobreviveu à verificação', MUTED)]
    top = 2.25
    text(s, 7.6, top, 4.7, 0.35, [('NÍVEL DE SUSTENTAÇÃO', SANS, 11, MUTED, True)])
    top += 0.45
    for nome, criterio, cor in niveis:
        text(s, 7.6, top, 1.9, 0.35, [(nome, SERIF, 15, cor, True)])
        text(s, 9.4, top + 0.03, 3.0, 0.6, [(criterio, SANS, 11.5, MUTED)], line=1.2)
        top += 0.72
    text(s, 7.6, 5.35, 4.7, 0.9, [
        ('O nível é calculado por regras sobre as citações devolvidas. O modelo é proibido de '
         'informar confiança.', SANS, 12, INK)], line=1.3)
    footer(s, 8)
    notes(s, 'Aqui está a diferença entre "citou" e "citou algo que existe". A citação é conferida '
             'literalmente contra o texto do trecho; se o modelo inventar a frase, a afirmação é '
             'descartada e o nível cai. E o indicador não é probabilidade calibrada: é regra.')


# ---------------------------------------------------------------- 9. interface
def s09_interface(prs):
    s = slide(prs)
    header(s, 'Interface', 'A resposta inteira numa tela')
    if SHOT.exists():
        from PIL import Image
        recorte = Image.open(SHOT).crop((0, 0, 1920, 742))     # resposta, painel e subgrafo
        buffer = BytesIO()
        recorte.save(buffer, format='PNG')
        buffer.seek(0)
        max_w, max_h = TEXT_W, 4.28
        ratio = recorte.size[0] / recorte.size[1]
        largura = min(max_w, max_h * ratio)
        altura = largura / ratio
        s.shapes.add_picture(buffer, Inches(LEFT + (TEXT_W - largura) / 2), Inches(2.12),
                             width=Inches(largura), height=Inches(altura))
    text(s, LEFT, 6.35, TEXT_W, 0.5, [
        ('Execução real: 210,9 s, cobertura 100%, duas afirmações com evidência, '
         'zero citação não verificada.', SANS, 12, MUTED, False, True)])
    footer(s, 9)
    notes(s, 'Apontar da esquerda para a direita: pergunta e o modo usado; resposta com marcadores E1; '
             'painel de sustentação dizendo por que é média; subgrafo com os nomes dos conceitos e o '
             'tipo de cada aresta; fontes com link; citação literal; e o canal usado na recuperação. '
             'Se perguntarem dos 210 s: é qwen3:8b local em GPU de 4 GB.')


# ---------------------------------------------------------------- 10. avaliação
def s10_avaliacao(prs):
    s = slide(prs)
    header(s, 'Avaliação', '45 execuções, mesmas regras')
    data = CategoryChartData()
    data.categories = ['Conceitual', 'Multi-hop', 'Sem resposta']
    data.add_series('vector', (60, 20, 100))
    data.add_series('hybrid', (100, 80, 100))
    data.add_series('graph', (80, 100, 100))
    frame = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(LEFT), Inches(2.15),
                               Inches(7.4), Inches(3.5), data)
    chart = frame.chart
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(11)
    chart.legend.font.name = SANS
    chart.font.name = SANS
    chart.font.size = Pt(11)
    chart.font.color.rgb = MUTED
    chart.has_title = False
    plot = chart.plots[0]
    plot.gap_width = 70
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.font.size = Pt(10)
    labels.font.name = SANS
    labels.number_format = '0"%"'
    labels.number_format_is_linked = False
    labels.position = XL_LABEL_POSITION.OUTSIDE_END
    cores = [RGBColor(0xB9, 0xB2, 0xA6), ACCENT, RGBColor(0x8A, 0x6A, 0x2A)]
    for serie, cor in zip(chart.series, cores):
        serie.format.fill.solid()
        serie.format.fill.fore_color.rgb = cor
    axes = chart.value_axis
    axes.maximum_scale = 110
    axes.minimum_scale = 0
    axes.has_major_gridlines = False
    axes.visible = False
    chart.category_axis.tick_labels.font.size = Pt(12)
    chart.category_axis.tick_labels.font.name = SANS
    chart.category_axis.format.line.color.rgb = LINE

    linhas = [('', 'Acerto', 'Nível alto', 'Tempo'),
              ('vector', '60%', '0', '65 s'),
              ('hybrid', '93%', '5', '71 s'),
              ('graph', '93%', '1', '51 s')]
    top = 2.3
    larguras = [1.55, 1.05, 1.15, 0.85]
    x0 = 8.75
    for i, linha in enumerate(linhas):
        x = x0
        for j, celula in enumerate(linha):
            negrito = i == 0 or (i in (2, 3) and j == 1)
            cor = MUTED if i == 0 else INK
            text(s, x, top, larguras[j], 0.35,
                 [(celula, SERIF if 0 < i and j == 0 else SANS, 12, cor, negrito)])
            x += larguras[j]
        if i == 0:
            rule(s, top + 0.3, left=x0, width=sum(larguras), color=LINE)
        top += 0.42
    card(s, 8.75, 4.35, 3.4, 1.35, fill=WHITE)
    text(s, 9.0, 4.5, 2.9, 0.3, [('MULTI-HOP', SANS, 10, MUTED, True)])
    text(s, 9.0, 4.78, 2.9, 0.8, [('1/5 → 4/5 → 5/5', SERIF, 24, ACCENT, True)])
    text(s, 8.75, 5.85, 3.6, 0.9, [
        ('É onde a arquitetura ganha: o trecho isolado não responde pergunta que exige ligar '
         'dois conceitos.', SANS, 11.5, MUTED)], line=1.3)
    text(s, LEFT, 5.85, 7.2, 0.9, [
        ('Abstenção 5/5 nos três modos · nenhuma citação não verificada em 43 respostas · '
         'duas falhas de verificação viraram recusa, não resposta.', SANS, 12, INK)], line=1.3)
    footer(s, 10)
    values = None
    notes(s, 'Este é o slide central. A diferença aparece exatamente no grupo que exige a arquitetura: '
             'multi-hop, 1 de 5 no vetor puro contra 4 e 5. E o número que mais vale para a defesa é o '
             'de abstenção: 5 de 5 nos três modos, ninguém respondeu pergunta fora do corpus. '
             'Se perguntarem de estatística: 15 perguntas, uma execução por célula, 6,7 pontos por acerto.')


# ---------------------------------------------------------------- 11. limites
def s11_limites(prs):
    s = slide(prs)
    header(s, 'Limites', 'O que este resultado não prova')
    itens = [
        ('Cobertura da extração', '23 relações condicionam tudo: as perguntas da avaliação usam '
                                  'praticamente todos os caminhos disponíveis'),
        ('Circularidade parcial', 'os documentos esperados vêm das evidências do grafo, o que '
                                  'favorece os modos que usam o grafo'),
        ('Amostra', '15 perguntas, uma execução por célula; a mesma consulta já deu níveis '
                    'diferentes em execuções repetidas'),
        ('Revisão humana', 'nenhuma etapa teve revisão independente dos fatos extraídos'),
    ]
    top = 2.3
    for titulo, apoio in itens:
        text(s, LEFT, top, 0.35, 0.35, [('—', SANS, 14, RUST, True)])
        text(s, LEFT + 0.45, top, 3.1, 0.4, [(titulo, SANS, 15, INK, True)])
        text(s, LEFT + 3.65, top, 7.4, 0.7, [(apoio, SANS, 12.5, MUTED)], line=1.3)
        top += 0.95
    card(s, LEFT, 6.0, TEXT_W, 0.7, fill=WHITE)
    text(s, LEFT + 0.3, 6.14, TEXT_W - 0.6, 0.45, [
        ('O próximo passo é o que mais muda o resultado: ampliar a extração de relações e trocar o '
         'gabarito derivado do grafo por anotação humana.', SANS, 12, INK)])
    footer(s, 11)
    notes(s, 'Este slide é o que separa trabalho honesto de propaganda. Dizer o limite antes de ser '
             'perguntado muda o tom da arguição. O compromisso de continuidade é concreto: mais '
             'relações e gabarito anotado por pessoa.')


# ---------------------------------------------------------------- 12. demo
def s12_demo(prs):
    s = slide(prs)
    header(s, 'Demonstração', 'Roteiro de três minutos')
    passos = [
        ('Perguntar pelo grafo',
         '“Quais relações ligam integridade referencial a chaves estrangeiras?” — modo hybrid'),
        ('Apontar a prova',
         'marcadores E1 nas afirmações, painel de sustentação, subgrafo com os nomes, citação literal'),
        ('Pedir o que não existe',
         '“receita de bolo de cenoura” — recusa com sugestões, nunca resposta inventada'),
    ]
    top = 2.3
    for i, (titulo, apoio) in enumerate(passos):
        card(s, LEFT, top, TEXT_W, 1.1)
        text(s, LEFT + 0.35, top + 0.3, 0.6, 0.5, [(f'{i + 1}', SERIF, 22, ACCENT, True)])
        text(s, LEFT + 1.05, top + 0.22, 9.6, 0.35, [(titulo, SANS, 16, INK, True)])
        text(s, LEFT + 1.05, top + 0.62, 9.6, 0.4, [(apoio, SANS, 12.5, MUTED)], line=1.2)
        top += 1.25
    text(s, LEFT, 6.05, TEXT_W, 0.7, [
        ('Antes de abrir a tela: Neo4j no ar, Ollama com qwen3:8b, e uma execução salva pronta '
         'como plano B se a GPU demorar.', SANS, 12.5, RUST, True)], line=1.3)
    footer(s, 12)
    notes(s, 'Deixar uma execução salva aberta antes de começar a falar, para não depender dos 3 minutos '
             'de GPU ao vivo. Se o modelo estiver lento, abrir a execução salva e dizer que é a mesma '
             'pergunta, mesmo sistema. A recusa da receita de bolo é o momento mais forte: mostra que '
             'o sistema prefere não responder.')


def main():
    prs = new_deck()
    for build in (s01_capa, s02_problema, s03_pergunta, s04_arquitetura, s05_dados, s06_hibrida,
                  s07_cypher, s08_fundamentacao, s09_interface, s10_avaliacao, s11_limites, s12_demo):
        build(prs)
    prs.core_properties.title = 'Assistente de banco de dados com GraphRAG'
    prs.core_properties.author = 'João Pedro Nóbrega, Lucas Coutinho, Jefferson Cunha, Matheus Rodrigues, Ramon Rocha, Adijair Araújo'
    prs.core_properties.subject = 'Tendências em Ciência da Computação — UNIPÊ'
    prs.save(OUT)
    print(f'slides salvos em {OUT} ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)')


if __name__ == '__main__':
    main()
