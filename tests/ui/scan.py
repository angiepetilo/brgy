"""Shared file walkers for the Stage D UI scans."""
from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)
TEMPLATES = BASE / 'templates'
STATIC = BASE / 'static'


def template_files():
    """All HTML templates except the e-mail bodies (out of scope for the UI theme)."""
    for path in sorted(TEMPLATES.rglob('*.html')):
        if 'emails' in path.relative_to(TEMPLATES).parts:
            continue
        yield path


def static_sources():
    """First-party JS and CSS (vendored third-party code is excluded)."""
    for folder, pattern in (('js', '*.js'), ('css', '*.css')):
        yield from sorted((STATIC / folder).glob(pattern))


def scan(paths, patterns):
    hits = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            for label, pattern in patterns:
                if pattern.search(line):
                    hits.append(f'{path.relative_to(BASE)}:{number}: {label}: {line.strip()[:120]}')
    return hits
