#!/usr/bin/env python3
"""Add the pending commit subject to CHANGELOG.md and stage the file."""
from pathlib import Path
import subprocess
import sys


SECTION = '### 提交记录'


def commit_subject(message_path):
    for raw_line in Path(message_path).read_text(encoding='utf-8').splitlines():
        subject = raw_line.strip()
        if subject and not subject.startswith('#'):
            return subject
    return ''


def add_entry(changelog_path, subject):
    text = changelog_path.read_text(encoding='utf-8')
    entry = f'- {subject}'
    if entry in text:
        return False

    lines = text.splitlines()
    try:
        unreleased_index = lines.index('## [Unreleased]')
    except ValueError as error:
        raise SystemExit('CHANGELOG.md 缺少 ## [Unreleased]。') from error

    next_release = next(
        (index for index in range(unreleased_index + 1, len(lines)) if lines[index].startswith('## ')),
        len(lines),
    )
    section_index = next(
        (index for index in range(unreleased_index + 1, next_release) if lines[index] == SECTION),
        None,
    )
    if section_index is None:
        insertion = next_release
        lines[insertion:insertion] = ['', SECTION, '', entry, '']
    else:
        insertion = section_index + 1
        while insertion < len(lines) and not lines[insertion].strip():
            insertion += 1
        lines.insert(insertion, entry)

    changelog_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    return True


def main():
    if len(sys.argv) != 2:
        print('usage: scripts/update_changelog_for_commit.py <commit-message-file>')
        return 2
    subject = commit_subject(sys.argv[1])
    if not subject or subject.startswith('Merge '):
        return 0

    repository_root = Path(__file__).resolve().parent.parent
    changelog_path = repository_root / 'CHANGELOG.md'
    if add_entry(changelog_path, subject):
        subprocess.run(['git', 'add', 'CHANGELOG.md'], cwd=repository_root, check=True)
        print(f'已写入 CHANGELOG.md：{subject}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
