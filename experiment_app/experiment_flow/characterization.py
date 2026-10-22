"""Permission-scoped characterization uploads into an administrator-configured root."""
import json
import logging
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import TooManyFilesSent
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .audit import record_audit_event
from .views import accessible_samples_for_user

logger = logging.getLogger(__name__)
TEST_TYPES = ('01 SEM', '02 CP-SEM', '03 FIB-SEM', '04 xCT', '05 XRD')


class UploadError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _root():
    configured = settings.CHARACTERIZATION_DATA_ROOT
    if not configured:
        raise UploadError('尚未配置表征数据目录，请联系管理员配置后再上传。', 503)
    try:
        root = Path(configured).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise OSError('Not a directory')
    except OSError as exc:
        raise UploadError('表征数据目录不可用，请联系管理员检查挂载和写入权限。', 503) from exc
    return root


def _path_parts(value):
    # Validate the original string before Path can normalize traversal/empty parts.
    if not isinstance(value, str) or not value or len(value) > 1000:
        raise UploadError('文件路径无效。')
    parts = value.split('/')
    for part in parts:
        if (not part or part.startswith('.') or part.endswith((' ', '.'))
                or len(part.encode('utf-8')) > 255
                or any(ord(char) < 32 or char in '\\:*?"<>|' for char in part)
                or part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                                *[f'COM{i}' for i in range(1, 10)],
                                                *[f'LPT{i}' for i in range(1, 10)]}):
            raise UploadError('文件名或路径无效：不支持隐藏文件、路径跳转或系统保留名称。')
    return tuple(parts)


def _target(root, parts):
    target = root
    for index, part in enumerate(parts):
        target = target / part
        if target.is_symlink():
            raise UploadError('目标路径包含符号链接，无法上传。', 409)
        if target.exists() and (index == len(parts) - 1 or not target.is_dir()):
            raise UploadError(f'目标已存在或路径冲突：{"/".join(parts[2:])}。请调整文件名后重试。', 409)
    return target


@login_required
@require_GET
def characterization_page(request):
    return render(request, 'experiment_flow/characterization.html', {
        'test_types': TEST_TYPES,
        'upload_configured': bool(settings.CHARACTERIZATION_DATA_ROOT),
        'max_files': settings.DATA_UPLOAD_MAX_NUMBER_FILES,
        'max_bytes': settings.CHARACTERIZATION_UPLOAD_MAX_BYTES,
    })


@login_required
@require_POST
def upload_characterization(request):
    published = []
    created_dirs = []
    try:
        try:
            files = request.FILES.getlist('files')
            sample_pk = int(request.POST.get('sample_id', ''))
        except TooManyFilesSent as exc:
            raise UploadError('文件数量超过单次上传限制，请分批上传。') from exc
        except (ValueError, TypeError) as exc:
            raise UploadError('请搜索并选择一个有效的 Sample。') from exc
        sample = accessible_samples_for_user(request.user).filter(pk=sample_pk).first()
        if sample is None:
            raise UploadError('Sample 不存在或你没有访问权限。', 403)
        sample_id = sample.sample_name
        if not re.fullmatch(r'[A-Za-z0-9_-]+', sample_id):
            raise UploadError('该 Sample ID 无法用于数据目录，请联系管理员。')
        test_type = request.POST.get('test_type')
        if test_type not in TEST_TYPES:
            raise UploadError('请选择有效的测试项目。')
        mode = request.POST.get('mode', 'files')
        if mode not in ('files', 'folder'):
            raise UploadError('上传方式无效。')
        if not files:
            raise UploadError('请选择文件或包含数据的文件夹。')
        if len(files) > settings.DATA_UPLOAD_MAX_NUMBER_FILES:
            raise UploadError('文件数量超过单次上传限制，请分批上传。')
        total_bytes = sum(file.size for file in files)
        if total_bytes > settings.CHARACTERIZATION_UPLOAD_MAX_BYTES:
            raise UploadError('数据大小超过单次上传限制，请分批上传。', 413)
        try:
            paths = json.loads(request.POST.get('paths', '[]'))
        except (ValueError, TypeError) as exc:
            raise UploadError('文件路径清单无效。') from exc
        if not isinstance(paths, list) or len(paths) != len(files):
            raise UploadError('文件与路径清单不一致，请重新选择。')
        paths = [_path_parts(path) for path in paths]
        if mode == 'folder':
            if any(len(path) < 2 for path in paths) or len({path[0] for path in paths}) != 1:
                raise UploadError('请一次选择一个完整文件夹。')
            paths = [path[1:] for path in paths]
        elif any(len(path) != 1 for path in paths):
            raise UploadError('单文件上传不能包含目录路径。')
        # Reject collisions, including file-vs-directory and case-insensitive filesystems.
        keys = [tuple(part.casefold() for part in path) for path in paths]
        key_set = set(keys)
        if len(key_set) != len(keys) or any(key[:i] in key_set for key in keys for i in range(1, len(key))):
            raise UploadError('本次上传存在重名文件或文件与目录冲突，请调整后重试。', 409)
        root = _root()
        destinations = [(test_type, sample_id, *path) for path in paths]
        for parts in destinations:
            _target(root, parts)

        # Exclusive creation prevents overwrites, including simultaneous uploads.
        with transaction.atomic():
            for file, parts in zip(files, destinations):
                target = _target(root, parts)
                parent = root
                for part in parts[:-1]:
                    parent = parent / part
                    try:
                        parent.mkdir()
                        created_dirs.append(parent)
                    except FileExistsError:
                        if parent.is_symlink() or not parent.is_dir():
                            raise UploadError('目标目录冲突，请联系管理员。', 409)
                try:
                    with target.open('xb') as output:
                        published.append(target)
                        for chunk in file.chunks():
                            output.write(chunk)
                except FileExistsError as exc:
                    raise UploadError('同名文件已存在，本次上传未保存。请调整文件名后重试。', 409) from exc
            record_audit_event(
                request, 'update', 'step', f'上传表征数据：{sample_id} / {test_type}（{len(files)} 个文件）',
                instance=sample.step,
                changes={'sample_id': sample_id, 'test_type': test_type,
                         'files': ['/'.join(path) for path in paths], 'total_bytes': total_bytes},
            )
        return JsonResponse({'sample_id': sample_id, 'test_type': test_type,
                             'file_count': len(files), 'destination': f'{test_type}/{sample_id}'}, status=201)
    except Exception as exc:
        # Remove only files/directories created by this request; preserve prior data.
        for path in reversed(published):
            try:
                path.unlink()
            except OSError:
                logger.exception('Unable to roll back uploaded file')
        for path in reversed(created_dirs):
            try:
                path.rmdir()
            except OSError:
                pass
        if isinstance(exc, UploadError):
            return JsonResponse({'error': str(exc)}, status=exc.status)
        logger.exception('Characterization upload failed')
        return JsonResponse({'error': '上传未完成，请联系管理员检查数据目录、剩余空间和写入权限。'}, status=503)
