"""
Private file storage rooted at settings.PRIVATE_MEDIA_ROOT.

Files here are never served by the web server or by /media/. They are
streamed only by permission-checked views (FileResponse). The root is read
from settings on every access, so override_settings(PRIVATE_MEDIA_ROOT=...)
works in tests.
"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible(path='apps.core.storage.PrivateMediaStorage')
class PrivateMediaStorage(FileSystemStorage):
    def __init__(self, subdir=''):
        self.subdir = subdir.strip('/\\')
        super().__init__()

    @property
    def base_location(self):
        root = str(settings.PRIVATE_MEDIA_ROOT)
        return os.path.join(root, self.subdir) if self.subdir else root

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        # No public URL exists; callers must link to the permission-checked view.
        raise ValueError('Private files have no public URL; use the permission-checked view.')
