from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from experiment_flow.views import parse_changelog


class ChangelogParserTests(SimpleTestCase):
    def test_hides_empty_unreleased_and_keeps_released_version(self):
        changelog = """# 更新日志

## [Unreleased]

## [v0.1.2-alpha] - 2026-09-02

### 新增

- 已发布功能
"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'CHANGELOG.md'
            path.write_text(changelog, encoding='utf-8')

            releases = parse_changelog(path)

        self.assertEqual([release['title'] for release in releases], ['[v0.1.2-alpha] - 2026-09-02'])

    def test_shows_unreleased_after_new_items_are_added(self):
        changelog = """# 更新日志

## [Unreleased]

### 修复

- 新修复
"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'CHANGELOG.md'
            path.write_text(changelog, encoding='utf-8')

            releases = parse_changelog(path)

        self.assertEqual(releases[0]['title'], '[Unreleased]')
        self.assertEqual(releases[0]['groups'][0]['items'], ['新修复'])
