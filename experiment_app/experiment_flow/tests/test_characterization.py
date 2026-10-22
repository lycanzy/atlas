import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import Client, TestCase
from django.urls import reverse

from experiment_flow.characterization import TEST_TYPES
from experiment_flow.models import AuditLog
from .test_image_viewer import ImageViewerTests


class CharacterizationTests(TestCase):
    setUpTestData = classmethod(ImageViewerTests.setUpTestData.__func__)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        setting = self.settings(CHARACTERIZATION_DATA_ROOT=str(self.root))
        setting.enable()
        self.addCleanup(setting.disable)
        self.client.force_login(self.user)
        self.url = reverse('upload_characterization')

    def upload(self, paths=None, **extra):
        paths = ['result.dat'] if paths is None else paths
        payload = {
            'sample_id': self.samples[0].pk, 'test_type': TEST_TYPES[0], 'mode': 'files',
            'paths': json.dumps(paths),
            'files': [SimpleUploadedFile(f'file-{i}.dat', b'data-' + str(i).encode()) for i in range(len(paths))],
        }
        payload.update(extra)
        return self.client.post(self.url, payload)

    def destination(self, test_type=TEST_TYPES[0], sample=None):
        return self.root / test_type / (sample or self.samples[0]).sample_name

    def test_page_does_not_scan_or_load_samples(self):
        with patch('experiment_flow.characterization._root', side_effect=AssertionError), patch(
            'experiment_flow.characterization.accessible_samples_for_user', side_effect=AssertionError,
        ):
            response = self.client.get(reverse('characterization'))
        self.assertContains(response, '上传表征数据')
        for test_type in TEST_TYPES:
            self.assertContains(response, test_type)

    def test_authentication_post_and_csrf_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.user)
        self.assertEqual(secure_client.post(self.url, {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('characterization')).status_code, 302)
        self.assertEqual(self.upload().status_code, 302)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_single_files_all_types_and_audit(self):
        for test_type in TEST_TYPES:
            response = self.upload(['原始数据.raw', 'image.tiff'], test_type=test_type)
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual((self.destination(test_type) / '原始数据.raw').read_bytes(), b'data-0')
            self.assertEqual(response.json()['file_count'], 2)
        event = AuditLog.objects.filter(request_path=self.url).latest('id')
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.changes['sample_id'], self.samples[0].sample_name)
        self.assertEqual(event.changes['files'], ['原始数据.raw', 'image.tiff'])
        self.assertEqual(event.changes['total_bytes'], 12)

    def test_folder_replaces_outer_name_preserves_nested_names(self):
        response = self.upload(['Instrument export/a.raw', 'Instrument export/nested/b.csv'], mode='folder')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((self.destination() / 'nested/b.csv').read_bytes(), b'data-1')
        self.assertFalse((self.destination() / 'Instrument export').exists())

    def test_normal_user_cannot_upload_to_other_group_or_unknown_sample(self):
        for sample_id in (self.samples[2].pk, 999999):
            self.assertEqual(self.upload(sample_id=sample_id).status_code, 403)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_staff_and_explicit_project_access(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.upload(sample_id=self.samples[2].pk).status_code, 201)
        self.client.force_login(self.user)
        self.other_project.authorized_users.add(self.user)
        self.assertEqual(self.upload(['second.dat'], sample_id=self.samples[2].pk).status_code, 201)

    def test_search_is_scoped_and_blank_returns_no_catalog(self):
        url = reverse('search_linkable_samples')
        self.assertEqual(self.client.get(url).json()['results'], [])
        self.assertEqual(self.client.get(url, {'q': 'CAT'}).json()['results'], [])
        self.assertEqual(len(self.client.get(url, {'q': 'PCA'}).json()['results']), 2)

    def test_invalid_payloads_have_no_files(self):
        for payload in ({'test_type': '../SEM'}, {'sample_id': 'bad'}, {'mode': 'unknown'},
                        {'paths': 'bad'}, {'paths': '{}'}, {'paths': '[]'}, {'paths': '[null]'}):
            with self.subTest(payload=payload):
                self.assertEqual(self.upload(**payload).status_code, 400)
        self.assertEqual(self.upload([]).status_code, 400)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_traversal_and_unsafe_names_rejected_before_any_write(self):
        for path in ('../a', '/tmp/a', 'folder/../a', 'folder//a', 'folder/./a',
                     'folder/.hidden', 'folder/a\\b', 'folder/C:foo', 'folder/NUL.txt',
                     'folder/a.', 'folder/a\x00b'):
            with self.subTest(path=path):
                self.assertEqual(self.upload(['folder/good.raw', path], mode='folder').status_code, 400)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_folder_structure_and_file_mode(self):
        self.assertEqual(self.upload(['one/a', 'two/b'], mode='folder').status_code, 400)
        self.assertEqual(self.upload(['a'], mode='folder').status_code, 400)
        self.assertEqual(self.upload(['folder/a']).status_code, 400)

    def test_repeated_or_prefix_collisions_rejected(self):
        for paths in (['folder/a', 'folder/a'], ['folder/A', 'folder/a'], ['folder/a', 'folder/a/b']):
            self.assertEqual(self.upload(paths, mode='folder').status_code, 409)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_data_is_not_overwritten_and_batch_is_rejected(self):
        self.destination().mkdir(parents=True)
        existing = self.destination() / 'existing.raw'
        existing.write_bytes(b'original')
        response = self.upload(['new.raw', 'existing.raw'])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(existing.read_bytes(), b'original')
        self.assertFalse((self.destination() / 'new.raw').exists())
        self.assertFalse(AuditLog.objects.filter(request_path=self.url).exists())

    def test_symlinks_at_each_level_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            for parts in (('01 SEM',), ('01 SEM', self.samples[0].sample_name),
                          ('01 SEM', self.samples[0].sample_name, 'nested')):
                link = self.root.joinpath(*parts)
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                self.assertEqual(self.upload(['folder/nested/data.raw'], mode='folder').status_code, 409)
                self.assertEqual(list(Path(outside).iterdir()), [])
                link.unlink()

    def test_missing_unmounted_root_and_limits(self):
        with self.settings(CHARACTERIZATION_DATA_ROOT=''):
            self.assertEqual(self.upload().status_code, 503)
            self.assertContains(self.client.get(reverse('characterization')), '尚未配置数据存储目录')
        with self.settings(CHARACTERIZATION_DATA_ROOT=str(self.root / 'missing')):
            self.assertEqual(self.upload().status_code, 503)
            self.assertFalse((self.root / 'missing').exists())
        with self.settings(CHARACTERIZATION_UPLOAD_MAX_BYTES=5):
            self.assertEqual(self.upload().status_code, 413)
        with self.settings(DATA_UPLOAD_MAX_NUMBER_FILES=1):
            self.assertEqual(self.upload(['a', 'b']).status_code, 400)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_write_failure_rolls_back_new_files_preserves_existing(self):
        self.destination().mkdir(parents=True)
        existing = self.destination() / 'old.dat'
        existing.write_bytes(b'original')
        original_open = Path.open

        def failing_open(path, *args, **kwargs):
            if path.name == 'b.raw' and args == ('xb',):
                raise OSError('disk full')
            return original_open(path, *args, **kwargs)

        with patch.object(Path, 'open', failing_open), self.assertLogs('experiment_flow.characterization', level='ERROR'):
            response = self.upload(['folder/new/a.raw', 'folder/new/b.raw'], mode='folder')
        self.assertEqual(response.status_code, 503)
        self.assertFalse((self.destination() / 'new').exists())
        self.assertEqual(existing.read_bytes(), b'original')
        self.assertFalse(AuditLog.objects.filter(request_path=self.url).exists())

    def test_audit_failure_rolls_back_files(self):
        with patch('experiment_flow.characterization.record_audit_event', side_effect=DatabaseError), self.assertLogs(
            'experiment_flow.characterization', level='ERROR',
        ):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(list(self.root.iterdir()), [])
