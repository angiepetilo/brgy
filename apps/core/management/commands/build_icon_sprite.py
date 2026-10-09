"""
Build static/vendor/lucide/sprite.svg from a lucide-static icons directory.

Only the names in apps.core.icons.ICON_NAMES are included, so phones on
slow data download a small subset instead of the full ~1 MB sprite.

    npm pack lucide-static@1.52.0   (then: tar -xzf lucide-static-1.52.0.tgz)
    python manage.py build_icon_sprite --source package/icons
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.icons import ICON_NAMES

SVG_BODY = re.compile(r'<svg\b[^>]*>(.*?)</svg>', re.S)
COMMENT = re.compile(r'<!--.*?-->', re.S)


class Command(BaseCommand):
    help = 'Build the Lucide subset sprite used by the {% icon %} template tag.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, help='Directory with lucide-static <name>.svg files')
        parser.add_argument('--output', default=None, help='Output path (default static/vendor/lucide/sprite.svg)')

    def handle(self, *args, **options):
        source = Path(options['source'])
        if not source.is_dir():
            raise CommandError(f'Source directory not found: {source}')
        output = Path(options['output'] or Path(settings.BASE_DIR) / 'static' / 'vendor' / 'lucide' / 'sprite.svg')

        symbols, missing = [], []
        for name in sorted(ICON_NAMES):
            path = source / f'{name}.svg'
            if not path.is_file():
                missing.append(name)
                continue
            match = SVG_BODY.search(COMMENT.sub('', path.read_text(encoding='utf-8')))
            if not match:
                raise CommandError(f'Unparseable SVG: {path}')
            body = ' '.join(line.strip() for line in match.group(1).strip().splitlines())
            symbols.append(
                f'<symbol id="lucide-{name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</symbol>'
            )
        if missing:
            raise CommandError('Icons not found in source: ' + ', '.join(missing))

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            '<!-- Lucide icons (lucide-static, ISC License). Subset built by build_icon_sprite. -->\n'
            '<svg xmlns="http://www.w3.org/2000/svg">\n'
            + '\n'.join(symbols) + '\n</svg>\n',
            encoding='utf-8',
        )
        self.stdout.write(self.style.SUCCESS(f'Wrote {len(symbols)} symbols to {output}'))
