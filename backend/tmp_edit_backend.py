from pathlib import Path
from textwrap import dedent

root = Path(r'd:\PythonCode\LAW')


def read(rel: str) -> str:
    return (root / rel).read_text(encoding='utf-8')


def write(rel: str, content: str) -> None:
    (root / rel).write_text(content, encoding='utf-8', newline='\n')


def replace(rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'replace target not found in {rel}: {old[:80]!r}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')


def replace_block(rel: str, start_marker: str, end_marker: str, new_block: str) -> None:
    path = root / rel
    text = path.read_text(encoding='utf-8')
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    updated = text[:start] + new_block + text[end:]
    path.write_text(updated, encoding='utf-8', newline='\n')


write(
    'backend/tmp_edit_backend.py.log',
    'script prepared\n',
)

# content omitted in this probe; the next run fills the full script
