"""
Stage D: every rendered Lucide icon is paired with a text label.

An <svg class="icon"> passes when its parent (or, for an icon in its own
wrapper, its grandparent) has text other than the svg, or the parent or
grandparent carries aria-label/title. sr-only text counts as a label for
screen readers; icon-only controls must have an aria-label.
"""
from html.parser import HTMLParser

from django.test import TestCase

from tests.base import make_admin, make_resident_user
from tests.ui.pages import ADMIN_PAGES, ANONYMOUS_PAGES, RESIDENT_PAGES, urls

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr', 'use'}


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.text = [], []

    def all_text(self, skip_svg=True):
        if skip_svg and self.tag == 'svg':
            return ''
        parts = list(self.text)
        for child in self.children:
            parts.append(child.all_text(skip_svg))
        return ''.join(parts)


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root', [], None)
        self.current = self.root
        self.icons = []

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag == 'svg' and 'icon' in (node.attrs.get('class') or '').split():
            self.icons.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.current = node.parent

    def handle_data(self, data):
        self.current.text.append(data)


def unlabelled_icons(html):
    builder = TreeBuilder()
    builder.feed(html)
    problems = []
    for svg in builder.icons:
        parent = svg.parent
        grand = parent.parent if parent else None
        # Visible text in the parent, or in the grandparent when the icon sits in its
        # own wrapper next to the label (e.g. <a><span>icon</span><span>Label</span></a>).
        if parent.all_text().strip() or (grand is not None and grand.tag != 'root' and grand.all_text().strip()):
            continue
        if any(n is not None and (n.attrs.get('aria-label') or n.attrs.get('title')) for n in (parent, grand)):
            continue
        problems.append(f"<{parent.tag} class='{parent.attrs.get('class', '')}'> icon {svg.attrs.get('class')}")
    return problems


class IconLabelTests(TestCase):

    def check(self, page_urls):
        for url in page_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(unlabelled_icons(response.content.decode()), [])

    def test_anonymous_pages(self):
        self.check(urls(ANONYMOUS_PAGES))

    def test_resident_pages(self):
        self.client.force_login(make_resident_user())
        self.check(urls(RESIDENT_PAGES))

    def test_admin_pages(self):
        self.client.force_login(make_admin())
        self.check(urls(ADMIN_PAGES))

    def test_checker_flags_bare_icons(self):
        bare = '<button><svg class="icon icon-x" aria-hidden="true"><use href="#x"></use></svg></button>'
        self.assertEqual(len(unlabelled_icons(bare)), 1)
        ok = ('<button aria-label="Close"><svg class="icon"><use href="#x"></use></svg></button>'
              '<a><svg class="icon"><use href="#y"></use></svg> Home</a>')
        self.assertEqual(unlabelled_icons(ok), [])
