#!/usr/bin/env python3
"""Freeze a non-empty Unreleased changelog section as the next patch release."""

import argparse
from datetime import date
from pathlib import Path
import re


UNRELEASED_HEADING = '## [Unreleased]'
RELEASE_HEADING_RE = re.compile(
    r'^## \[(v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)\](?: - \d{4}-\d{2}-\d{2})?$'
)
VERSION_RE = re.compile(r'^(v?)(\d+)\.(\d+)\.(\d+)(-[0-9A-Za-z.-]+)?$')


def trim_blank_lines(lines):
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def version_key(version):
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError(f'无效版本号：{version}')
    return tuple(int(match.group(index)) for index in (2, 3, 4))


def next_patch_version(changelog_text, fallback_version='v0.1.0-alpha'):
    versions = []
    for line in changelog_text.splitlines():
        match = RELEASE_HEADING_RE.fullmatch(line.strip())
        if match:
            versions.append(match.group(1))
    if fallback_version:
        VERSION_RE.fullmatch(fallback_version) or version_key(fallback_version)
        versions.append(fallback_version)

    latest = max(versions, key=version_key)
    match = VERSION_RE.fullmatch(latest)
    prefix, major, minor, patch, suffix = match.groups()
    return f'{prefix}{major}.{minor}.{int(patch) + 1}{suffix or ""}'


def add_commit_subjects(changelog_text, subjects):
    subjects = [subject.strip() for subject in subjects if subject.strip()]
    if not subjects:
        return changelog_text

    lines = changelog_text.splitlines()
    try:
        unreleased_index = lines.index(UNRELEASED_HEADING)
    except ValueError as error:
        raise ValueError('CHANGELOG.md 缺少 ## [Unreleased]。') from error

    next_release_index = next(
        (index for index in range(unreleased_index + 1, len(lines)) if lines[index].startswith('## ')),
        len(lines),
    )
    existing_entries = {
        line[2:].strip()
        for line in lines[unreleased_index + 1:next_release_index]
        if line.strip().startswith('- ')
    }
    new_entries = []
    seen_entries = set(existing_entries)
    for subject in subjects:
        if subject not in seen_entries:
            new_entries.append(f'- {subject}')
            seen_entries.add(subject)
    if not new_entries:
        return changelog_text

    section_index = next(
        (
            index for index in range(unreleased_index + 1, next_release_index)
            if lines[index].strip() == '### 提交记录'
        ),
        None,
    )
    if section_index is None:
        lines[next_release_index:next_release_index] = ['', '### 提交记录', '', *new_entries]
    else:
        insertion = section_index + 1
        while insertion < next_release_index and not lines[insertion].strip():
            insertion += 1
        lines[insertion:insertion] = new_entries
    return '\n'.join(lines).rstrip() + '\n'


def freeze_unreleased(changelog_text, version, release_date):
    lines = changelog_text.splitlines()
    try:
        unreleased_index = lines.index(UNRELEASED_HEADING)
    except ValueError as error:
        raise ValueError('CHANGELOG.md 缺少 ## [Unreleased]。') from error

    next_release_index = next(
        (index for index in range(unreleased_index + 1, len(lines)) if lines[index].startswith('## ')),
        len(lines),
    )
    unreleased_body = trim_blank_lines(lines[unreleased_index + 1:next_release_index])
    if not any(line.strip().startswith('- ') for line in unreleased_body):
        return changelog_text, False

    prefix = lines[:unreleased_index]
    suffix = trim_blank_lines(lines[next_release_index:])
    released_lines = [
        *prefix,
        UNRELEASED_HEADING,
        '',
        f'## [{version}] - {release_date}',
        '',
        *unreleased_body,
    ]
    if suffix:
        released_lines.extend(['', *suffix])
    return '\n'.join(released_lines).rstrip() + '\n', True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    repository_root = Path(__file__).resolve().parent.parent
    parser.add_argument('--changelog', type=Path, default=repository_root / 'CHANGELOG.md')
    parser.add_argument('--fallback-version', default='v0.1.0-alpha')
    parser.add_argument('--date', default=date.today().isoformat())
    parser.add_argument('--commit-subject', action='append', default=[])
    args = parser.parse_args()

    changelog_text = args.changelog.read_text(encoding='utf-8')
    changelog_text = add_commit_subjects(changelog_text, args.commit_subject)
    version = next_patch_version(changelog_text, args.fallback_version)
    released_text, changed = freeze_unreleased(changelog_text, version, args.date)
    if not changed:
        return 0

    args.changelog.write_text(released_text, encoding='utf-8')
    print(version)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
