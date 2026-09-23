import base64
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from experiment_flow.models import (
    Experiment, ExperimentStep, Project, ProjectCategory,
    ResearchGroup, Sample, UserProfile,
)

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6l9sAAAAASUVORK5CYII=')


class ImageViewerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='viewer')
        cls.other = User.objects.create_user(username='other')
        cls.staff = User.objects.create_user(username='staff', is_staff=True)
        cls.samples = []
        for owner, code in ((cls.user, 'PCA'), (cls.other, 'CAT')):
            team = ResearchGroup.objects.create(group_name=code, team_code=code)
            UserProfile.objects.create(user=owner, research_group=team)
            category = ProjectCategory.objects.create(project_name=code, project_code=code, group=team)
            project = Project.objects.create(exp_name=f'{code}001', project=category, owner=owner)
            experiment = Experiment.objects.create(experiment_code='AA', project=project)
            step = ExperimentStep.objects.create(experiment=experiment, step_name='MX')
            Sample.sync_for_step(step, 2 if code == 'PCA' else 1)
            cls.samples.extend(Sample.objects.filter(step=step).order_by('sample_name'))
            if code == 'CAT':
                cls.other_project = project

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        setting = self.settings(IMAGE_DATA_ROOT=str(self.root))
        setting.enable()
        self.addCleanup(setting.disable)
        for sample, count in zip(self.samples, (16, 3, 1)):
            folder = self.root / sample.sample_name / 'SEM'
            folder.mkdir(parents=True)
            for n in range(1, count + 1):
                (folder / f'DEMO_{n:03d}.png').write_bytes(PNG)
        self.client.force_login(self.user)

    def detail_url(self, sample=None, number=1):
        return reverse('image_detail', args=[(sample or self.samples[0]).sample_name, number])

    def file_url(self, sample=None, relative='SEM/DEMO_001.png'):
        return reverse('image_file', args=[(sample or self.samples[0]).sample_name, relative])

    def test_authentication_required_on_pages_and_file(self):
        self.client.logout()
        for url in (reverse('image_gallery'), self.detail_url(), self.file_url()):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response.url)

    def test_prefix_pagination_groups_and_case_normalization(self):
        first = self.client.get(reverse('image_gallery'), {'sample_id': ' pca '})
        self.assertEqual(first.context['query'], 'PCA')
        self.assertEqual(first.context['sample_count'], 2)
        self.assertEqual(first.context['page_obj'].paginator.count, 19)
        self.assertEqual(len(first.context['images']), 15)
        self.assertNotContains(first, self.samples[2].sample_name)
        second = self.client.get(reverse('image_gallery'), {'sample_id': 'pca', 'page': 2})
        self.assertEqual(len(second.context['images']), 4)
        self.assertEqual(len({image['sample_id'] for image in second.context['images']}), 2)
        self.assertContains(second, 'aria-label="搜索样品编号前缀"')

    def test_return_page_after_switching_across_page_boundary(self):
        response = self.client.get(self.detail_url(number=16), {'sample_id': 'pca'})
        self.assertContains(response, 'sample_id=PCA&amp;page=2')
        self.assertContains(response, f'#image-{self.samples[0].sample_name}-16')
        self.assertIsNone(response.context['next_number'])
        self.assertEqual(response.context['previous_number'], 15)
        self.assertContains(response, 'SEM/DEMO_016.png')
        self.assertIsNone(self.client.get(self.detail_url()).context['previous_number'])

    def test_file_endpoint_returns_exact_bytes_and_private_headers(self):
        response = self.client.get(self.file_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(b''.join(response.streaming_content), PNG)
        response.close()

    def test_other_group_hidden_even_via_direct_url(self):
        sample = self.samples[2]
        for url in (self.detail_url(sample), self.file_url(sample)):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse('image_gallery'), {'sample_id': 'CAT'}).context['sample_count'], 0)
        self.other_project.authorized_users.add(self.user)
        response = self.client.get(self.file_url(sample))
        self.assertEqual(response.status_code, 200)
        response.close()
        self.other_project.authorized_users.remove(self.user)
        self.assertEqual(self.client.get(self.file_url(sample)).status_code, 404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('image_gallery'), {'sample_id': 'C'}).context['sample_count'], 1)

    def test_unsupported_hidden_and_unregistered_files_ignored(self):
        folder = self.root / self.samples[0].sample_name
        for name in ('notes.txt', 'raw.tif', 'page.svg', '.hidden.png'):
            (folder / name).write_bytes(PNG)
        unknown = self.root / 'UNKNOWN'
        unknown.mkdir()
        (unknown / 'data.png').write_bytes(PNG)
        response = self.client.get(reverse('image_gallery'), {'sample_id': 'PCA'})
        self.assertEqual(response.context['page_obj'].paginator.count, 19)
        self.assertEqual(self.client.get(self.file_url(relative='page.svg')).status_code, 404)

    def test_traversal_and_symlinks_are_rejected(self):
        folder = self.root / self.samples[0].sample_name
        (self.root / 'outside.png').write_bytes(PNG)
        (folder / 'link.png').symlink_to(self.root / 'outside.png')
        (folder / 'linked-dir').symlink_to(self.root / self.samples[2].sample_name, target_is_directory=True)
        for relative in ('../outside.png', 'link.png', 'linked-dir/SEM/DEMO_001.png'):
            self.assertEqual(self.client.get(self.file_url(relative=relative)).status_code, 404)
        self.assertEqual(self.client.get(reverse('image_gallery'), {'sample_id': 'PCA'}).context['page_obj'].paginator.count, 19)

    def test_refresh_discovers_new_file_and_missing_file_is_404(self):
        file = self.root / self.samples[0].sample_name / 'SEM' / 'new.png'
        file.write_bytes(PNG)
        self.assertEqual(self.client.get(reverse('image_gallery'), {'sample_id': 'PCA'}).context['page_obj'].paginator.count, 20)
        file.unlink()
        self.assertEqual(self.client.get(self.file_url(relative='SEM/new.png')).status_code, 404)

    def test_missing_or_unreadable_root_has_explicit_error(self):
        with self.settings(IMAGE_DATA_ROOT=str(self.root / 'missing')):
            response = self.client.get(reverse('image_gallery'), {'sample_id': 'PCA'})
            self.assertContains(response, '图片目录暂不可用', status_code=503)
        with patch('experiment_flow.image_viewer.os.scandir', side_effect=PermissionError):
            response = self.client.get(reverse('image_gallery'), {'sample_id': 'PCA'})
            self.assertContains(response, '图片目录读取失败', status_code=503)

    def test_empty_search_invalid_pages_and_indices(self):
        for page in ('999', '-1', 'invalid'):
            response = self.client.get(reverse('image_gallery'), {'sample_id': 'PCA', 'page': page})
            self.assertEqual(response.status_code, 200)
            self.assertLessEqual(len(response.context['images']), 15)
        self.assertEqual(self.client.get(reverse('image_gallery'), {'sample_id': 'CA'}).context['sample_count'], 0)
        self.assertEqual(self.client.get(self.detail_url(number=0)).status_code, 404)
        self.assertEqual(self.client.get(self.detail_url(number=17)).status_code, 404)

    def test_initial_and_blank_search_do_not_touch_image_source(self):
        with patch('experiment_flow.image_viewer._image_root') as root, \
                patch('experiment_flow.image_viewer._matching_images') as scan:
            for params in ({}, {'sample_id': ''}, {'sample_id': '   '}, {'page': '2'}):
                response = self.client.get(reverse('image_gallery'), params)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context['searched'])
                self.assertFalse(response.context['images'])
                self.assertContains(response, '点击搜索后显示匹配的图片')
                self.assertNotContains(response, '<img ')
                self.assertNotContains(response, '图片结果分页')
            root.assert_not_called()
            scan.assert_not_called()

    def test_initial_page_works_even_if_image_root_is_missing(self):
        with self.settings(IMAGE_DATA_ROOT=str(self.root / 'missing')):
            response = self.client.get(reverse('image_gallery'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '搜索样品图像')
