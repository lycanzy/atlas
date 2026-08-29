#!/usr/bin/env python3
"""Fail when a non-merge commit does not include a CHANGELOG.md update."""
import subprocess
import sys


def changed_files(base, head):
    result = subprocess.run(
        ['git', 'diff', '--name-only', base, head],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def commits_between(base, head):
    result = subprocess.run(
        ['git', 'rev-list', '--reverse', '--no-merges', f'{base}..{head}'],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main():
    if len(sys.argv) != 3:
        print('usage: scripts/check_changelog.py <base-ref> <head-ref>')
        return 2
    missing = []
    for commit in commits_between(sys.argv[1], sys.argv[2]):
        files = changed_files(f'{commit}^', commit)
        if 'CHANGELOG.md' not in files:
            subject = subprocess.run(
                ['git', 'show', '-s', '--format=%s', commit],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            missing.append(f'{commit[:8]} {subject}')
    if missing:
        print('以下 commit 没有包含 CHANGELOG.md 更新：')
        for commit in missing:
            print(f'- {commit}')
        print('请启用仓库 hooks，或手动为每个 commit 添加提交记录。')
        return 1
    print('Changelog check passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
