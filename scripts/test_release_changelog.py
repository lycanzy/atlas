import unittest

from scripts.release_changelog import add_commit_subjects, freeze_unreleased, next_patch_version


class ReleaseChangelogTests(unittest.TestCase):
    def test_uses_latest_changelog_version_and_preserves_prerelease_suffix(self):
        text = """# 更新日志

## [Unreleased]

### 新增

- 新功能

## [v0.1.2-alpha] - 2026-09-01

### 修复

- 旧修复
"""

        version = next_patch_version(text, 'v0.1.1-alpha')
        released, changed = freeze_unreleased(text, version, '2026-09-02')

        self.assertEqual(version, 'v0.1.3-alpha')
        self.assertTrue(changed)
        self.assertIn('## [Unreleased]\n\n## [v0.1.3-alpha] - 2026-09-02', released)
        self.assertIn('- 新功能', released)
        self.assertIn('## [v0.1.2-alpha] - 2026-09-01', released)

    def test_uses_repository_tag_as_initial_version(self):
        text = """# 更新日志

## [Unreleased]

### 变更

- 一项变更
"""

        self.assertEqual(next_patch_version(text, 'v0.1.1-alpha'), 'v0.1.2-alpha')

    def test_empty_unreleased_section_is_not_released(self):
        text = """# 更新日志

## [Unreleased]

## [v0.1.2-alpha] - 2026-09-02

### 新增

- 已发布功能
"""

        released, changed = freeze_unreleased(text, 'v0.1.3-alpha', '2026-09-03')

        self.assertFalse(changed)
        self.assertEqual(released, text)

    def test_adds_unique_push_commit_subjects_to_unreleased(self):
        text = """# 更新日志

## [Unreleased]

### 提交记录

- Existing change
"""

        updated = add_commit_subjects(text, ['New change', 'New change', 'Existing change'])

        self.assertIn('### 提交记录\n\n- New change\n- Existing change', updated)
        self.assertEqual(updated.count('- New change'), 1)
        self.assertEqual(updated.count('- Existing change'), 1)


if __name__ == '__main__':
    unittest.main()
