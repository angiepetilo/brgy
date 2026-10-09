"""
Upload validation and file naming for identity documents.

validate_upload checks the extension AND the file's first bytes (magic
numbers), so a text file renamed to .jpg is rejected, and caps the size.
random_upload_to stores files as <prefix>/<uuid4hex>.<ext>, so the original
(possibly personal) file name is never kept on disk or in URLs.
"""
import os
import uuid

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# kind -> accepted extensions
_EXTENSIONS = {
    'jpg': ('.jpg', '.jpeg'),
    'png': ('.png',),
    'webp': ('.webp',),
    'pdf': ('.pdf',),
}
DEFAULT_KINDS = ('jpg', 'png', 'webp', 'pdf')


def sniff_kind(head):
    """File kind from its first bytes, or None."""
    if head.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if len(head) >= 12 and head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'webp'
    if head.startswith(b'%PDF-'):
        return 'pdf'
    return None


def _read_head(file_obj, size=16):
    pos = None
    try:
        pos = file_obj.tell()
    except (AttributeError, OSError, ValueError):
        pass
    try:
        file_obj.seek(0)
        head = file_obj.read(size) or b''
    finally:
        try:
            file_obj.seek(pos or 0)
        except (AttributeError, OSError, ValueError):
            pass
    return head if isinstance(head, bytes) else head.encode('latin-1', 'ignore')


@deconstructible
class UploadValidator:
    """Model/form validator: extension + magic bytes + size."""

    def __init__(self, allowed=DEFAULT_KINDS, max_bytes=MAX_UPLOAD_BYTES):
        self.allowed = tuple(allowed)
        self.max_bytes = max_bytes

    def __call__(self, file_obj):
        if not file_obj:
            return
        # A FieldFile that is already stored was validated when it was uploaded;
        # re-validating it on every full_clean() would re-read old files.
        if getattr(file_obj, '_committed', False):
            return
        allowed_exts = [ext for kind in self.allowed for ext in _EXTENSIONS[kind]]
        label = ', '.join(k.upper() for k in self.allowed)
        name = os.path.basename(getattr(file_obj, 'name', '') or '')
        ext = os.path.splitext(name)[1].lower()
        if ext not in allowed_exts:
            raise ValidationError(f'Unsupported file type. Upload a {label} file.', code='invalid_extension')
        size = getattr(file_obj, 'size', None)
        if size is not None and size > self.max_bytes:
            raise ValidationError(
                f'File is too large. The maximum size is {self.max_bytes // (1024 * 1024)} MB.',
                code='file_too_large',
            )
        kind = sniff_kind(_read_head(file_obj))
        if kind is None or kind not in self.allowed or ext not in _EXTENSIONS[kind]:
            raise ValidationError(
                f'The file content is not a valid {label} file, or does not match its extension.',
                code='invalid_content',
            )

    def __eq__(self, other):
        return isinstance(other, UploadValidator) and (self.allowed, self.max_bytes) == (other.allowed, other.max_bytes)


validate_upload = UploadValidator()


@deconstructible
class RandomUploadTo:
    """upload_to callable: '<prefix>/<uuid4 hex><original extension, lowercased>'."""

    def __init__(self, prefix):
        self.prefix = prefix.strip('/')

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename or '')[1].lower()
        if ext == '.jpeg':
            ext = '.jpg'
        name = f'{uuid.uuid4().hex}{ext}'
        return f'{self.prefix}/{name}' if self.prefix else name

    def __eq__(self, other):
        return isinstance(other, RandomUploadTo) and self.prefix == other.prefix


def random_upload_to(prefix):
    return RandomUploadTo(prefix)
