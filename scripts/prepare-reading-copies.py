"""Create readable Markdown copies without changing source evidence or corpus hashes."""
import argparse
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


class Table(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.unsupported = False
        self.depth = 0
        self.callout = False
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.depth += 1
            if self.depth == 1:
                self.callout = 'callout' in dict(attrs).get('summary', '').casefold()
            if self.depth > 1:
                self.unsupported = True
        if tag == 'tr':
            self.row = []
        if tag in ('td', 'th'):
            if any(k in ('rowspan', 'colspan') and v != '1' for k, v in attrs):
                self.unsupported = True
            self.cell = {'text': [], 'header': tag == 'th', 'bold': False}
        if self.cell is not None and tag in ('strong', 'b'):
            self.cell['bold'] = True
        if self.cell is not None and tag == 'br':
            self.cell['text'].append('\n')
        if self.cell is not None and tag == 'a':
            href = dict(attrs).get('href')
            self.links.append(href)
            if href:
                self.cell['text'].append('[')
        if self.cell is not None and tag == 'code':
            self.cell['text'].append('`')

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'].append(data)

    def handle_endtag(self, tag):
        if self.cell is not None and tag == 'a' and self.links:
            href = self.links.pop()
            if href:
                self.cell['text'].append('](' + href + ')')
        if self.cell is not None and tag == 'code':
            self.cell['text'].append('`')
        if tag in ('td', 'th') and self.cell is not None:
            self.cell['value'] = ''.join(self.cell['text']).strip()
            if self.row is None:
                self.unsupported = True
            else:
                self.row.append(self.cell)
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == 'table':
            self.depth -= 1


def cell_text(value):
    return value.replace('\\', '\\\\').replace('|', '\\|').replace('\r\n', '\n').replace('\n', ' ⏎ ')


def render_table(source):
    parsed = Table()
    parsed.feed(source)
    parsed.close()
    rows = parsed.rows
    if parsed.unsupported or not rows or any(len(r) != len(rows[0]) for r in rows):
        return source, 'retained_unsupported_table'
    header = all(c['header'] or c['bold'] for c in rows[0])
    if not header:
        if parsed.callout or (len(rows) == 1 and len(rows[0]) == 1):
            # D08 is an explanatory callout, not a data table. Invent no header.
            text = '\n\n'.join(' '.join(c['value'] for c in row) for row in rows)
            return '\n'.join('> ' + line for line in text.splitlines()), 'callout'
        return source, 'retained_table_without_header'
    lines = ['| ' + ' | '.join(cell_text(c['value']) for c in rows[0]) + ' |',
             '| ' + ' | '.join('---' for _ in rows[0]) + ' |']
    lines += ['| ' + ' | '.join(cell_text(c['value']) for c in row) + ' |' for row in rows[1:]]
    return '\n'.join(lines), 'markdown_table'


def convert(source):
    counts = {'markdown_table': 0, 'callout': 0, 'retained_unsupported_table': 0, 'retained_table_without_header': 0}

    def convert_prose(prose):
        def replace(match):
            result, status = render_table(match.group())
            counts[status] += 1
            return result
        prose = re.sub(r'<table\b[^>]*>.*?</table>', replace, prose, flags=re.I | re.S)
        for tags, delimiter in [('strong|b', '**'), ('em|i', '*')]:
            def emphasis(match):
                content = match[1]
                if not content.strip():
                    return content
                leading = content[:len(content) - len(content.lstrip())]
                trailing = content[len(content.rstrip()):]
                return leading + delimiter + content.strip() + delimiter + trailing
            prose = re.sub(r'<(?:' + tags + r')>(.*?)</(?:' + tags + r')>',
                           emphasis, prose, flags=re.I | re.S)
        return unescape(prose)

    # Keep fenced SQL and text output byte-for-byte in the reading copy as well.
    pieces = re.split(r'(^```[^\n]*\n.*?^```[^\n]*(?:\n|$))', source, flags=re.M | re.S)
    return ''.join(part if i % 2 else convert_prose(part) for i, part in enumerate(pieces)), counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'corpus/reading')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error('Choose a new directory inside the project.')
    documents = []
    rendered = []
    for source in sorted((ROOT / 'corpus/processed').glob('D*.md')):
        text, counts = convert(source.read_text(encoding='utf-8'))
        if counts['retained_unsupported_table'] or counts['retained_table_without_header']:
            raise ValueError('A table requires manual display review: ' + source.name)
        header = '> Cópia para leitura. Tabelas e ênfases foram formatadas; não usar como origem de citações, offsets ou hashes de extração. Evidência original em corpus/processed e corpus/chunks.\n\n'
        content = (header + text).encode('utf-8')
        rendered.append((source.name, content))
        documents.append(dict(document_id=source.stem, source=source.relative_to(ROOT).as_posix(),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            reading_copy=(output / source.name).relative_to(ROOT).as_posix(),
            reading_sha256=hashlib.sha256(content).hexdigest(), **counts))
    output.mkdir(parents=True)
    for name, content in rendered:
        (output / name).write_bytes(content)
    (output / 'manifest.json').write_text(json.dumps(dict(purpose='display_only_not_extraction_evidence', documents=documents),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(documents=len(documents), markdown_tables=sum(d['markdown_table'] for d in documents), callouts=sum(d['callout'] for d in documents)),ensure_ascii=False))


if __name__ == '__main__':
    main()
