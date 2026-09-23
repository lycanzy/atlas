"""Read-only image browsing for existing, authorized Atlas samples.

The configured root contains one directory per full Sample ID. This initial
local implementation scans metadata per request; image bytes are only opened
by the authenticated file endpoint. No filesystem paths come from settings
controlled by a browser request.
"""
import os
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse

from .views import accessible_samples_for_user

PAGE_SIZE = 15
IMAGE_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
               '.png': 'image/png', '.webp': 'image/webp'}


class ImageDirectoryUnavailable(Exception):
    pass


def _image_root():
    configured = getattr(settings, 'IMAGE_DATA_ROOT', '')
    if not configured:
        raise ImageDirectoryUnavailable('尚未配置图片数据目录。')
    try:
        root = Path(configured).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise OSError('Not a directory')
    except OSError as exc:
        raise ImageDirectoryUnavailable('图片数据目录暂不可用，请检查挂载和读取权限。') from exc
    return root


def _sample_directory(root, sample_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', sample_id):
        raise Http404('图片不存在')
    folder = root / sample_id
    if folder.is_symlink():
        raise Http404('图片不存在')
    return folder


def _safe_file(root, sample_id, relative_path):
    """Reject traversal and every symlink, including links between samples."""
    folder = _sample_directory(root, sample_id)
    parts = PurePosixPath(relative_path).parts
    if not parts or PurePosixPath(relative_path).is_absolute() or '\\' in relative_path:
        raise Http404('图片不存在')
    candidate = folder
    for part in parts:
        if part in ('.', '..') or part.startswith('.'):
            raise Http404('图片不存在')
        candidate = candidate / part
        if candidate.is_symlink():
            raise Http404('图片不存在')
    try:
        candidate.resolve(strict=True).relative_to(folder.resolve(strict=True))
        if not candidate.is_file() or candidate.suffix.lower() not in IMAGE_TYPES:
            raise Http404('图片不存在')
    except (OSError, ValueError):
        raise Http404('图片不存在')
    return candidate


def _matching_images(user, query, root):
    names = accessible_samples_for_user(user).filter(
        sample_name__istartswith=query,
    ).order_by('sample_name').values_list('sample_name', flat=True).distinct()
    images = []

    def scan_error(error):
        raise error

    try:
        # Check root readability even when there are no matching sample folders.
        with os.scandir(root):
            pass
        for sample_id in names:
            try:
                folder = _sample_directory(root, sample_id)
            except Http404:
                continue
            if not folder.is_dir():
                continue
            paths = []
            for directory, dirs, files in os.walk(folder, followlinks=False, onerror=scan_error):
                dirs[:] = sorted(d for d in dirs if not d.startswith('.')
                                 and not (Path(directory) / d).is_symlink())
                for filename in files:
                    path = Path(directory) / filename
                    if filename.startswith('.') or path.suffix.lower() not in IMAGE_TYPES:
                        continue
                    relative = path.relative_to(folder).as_posix()
                    try:
                        _safe_file(root, sample_id, relative)
                    except Http404:
                        continue
                    paths.append(relative)
            for number, relative in enumerate(sorted(paths), 1):
                images.append({
                    'sample_id': sample_id, 'number': number,
                    'filename': relative,
                    'is_demo': Path(relative).name.startswith('DEMO_'),
                    'url': reverse('image_file', kwargs={
                        'sample_id': sample_id, 'relative_path': relative,
                    }),
                })
    except OSError as exc:
        raise ImageDirectoryUnavailable('图片目录读取失败，请检查挂载和读取权限。') from exc
    return tuple(images)


@login_required
def image_gallery(request):
    query = request.GET.get('sample_id', '').strip().upper()
    error = None
    matches = ()
    searched = bool(query)
    # Initial/blank visits must not touch the image directory or sample catalog.
    if searched:
        try:
            matches = _matching_images(request.user, query, _image_root())
        except ImageDirectoryUnavailable as exc:
            error = str(exc)
    page = Paginator(matches, PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'experiment_flow/image_gallery.html', {
        'query': query, 'searched': searched, 'images': page.object_list, 'page_obj': page,
        'sample_count': len({image['sample_id'] for image in matches}),
        'page_size': PAGE_SIZE, 'directory_error': error,
        'search_query': urlencode({'sample_id': query}),
    }, status=503 if error else 200)


@login_required
def image_detail(request, sample_id, image_number):
    if not accessible_samples_for_user(request.user).filter(sample_name=sample_id).exists():
        raise Http404('未找到图片')
    try:
        catalog = _matching_images(request.user, '', _image_root())
    except ImageDirectoryUnavailable as exc:
        return HttpResponse(str(exc), status=503, content_type='text/plain; charset=utf-8')
    images = tuple(image for image in catalog if image['sample_id'] == sample_id)
    if not 1 <= image_number <= len(images):
        raise Http404('未找到图片')
    image = images[image_number - 1]
    query = request.GET.get('sample_id', sample_id).strip().upper()
    matches = tuple(image for image in catalog if image['sample_id'].startswith(query))
    if image not in matches:
        query, matches = sample_id, images
    page_number = matches.index(image) // PAGE_SIZE + 1
    return render(request, 'experiment_flow/image_detail.html', {
        'sample_id': sample_id, 'image': image, 'image_count': len(images),
        'previous_number': image_number - 1 if image_number > 1 else None,
        'next_number': image_number + 1 if image_number < len(images) else None,
        'search_query': urlencode({'sample_id': query}),
        'return_query': urlencode({'sample_id': query, 'page': page_number}),
    })


@login_required
def image_file(request, sample_id, relative_path):
    if not accessible_samples_for_user(request.user).filter(sample_name=sample_id).exists():
        raise Http404('图片不存在')
    try:
        path = _safe_file(_image_root(), sample_id, relative_path)
        handle = path.open('rb')
    except ImageDirectoryUnavailable as exc:
        return HttpResponse(str(exc), status=503, content_type='text/plain; charset=utf-8')
    except OSError:
        raise Http404('图片不存在')
    response = FileResponse(handle, content_type=IMAGE_TYPES[path.suffix.lower()])
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
