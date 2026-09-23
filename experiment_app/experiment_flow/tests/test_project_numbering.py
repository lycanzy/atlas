from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth.models import User
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from experiment_flow.models import Project, ProjectCategory, ResearchGroup


class ProjectNumberingTests(TestCase):
    def setUp(self):
        self.team = ResearchGroup.objects.create(group_name='Numbering', team_code='PCA')
        self.owner = User.objects.create(username='numbering', is_staff=True)
        self.category = ProjectCategory.objects.create(
            group=self.team, project_name='Numbering', project_code='PCA',
        )

    def create_project(self):
        return Project.create_for_team(team=self.team, owner=self.owner)

    def test_middle_deletion_uses_maximum_not_count(self):
        projects = [self.create_project() for _ in range(3)]
        projects[1].delete()
        self.assertEqual(self.create_project().exp_name, 'PCA004')
        self.assertTrue(Project.objects.filter(pk=projects[2].pk, exp_name='PCA003').exists())

    def test_deleted_trailing_batch_can_be_reused(self):
        projects = [self.create_project() for _ in range(20)]
        Project.objects.filter(pk__in=[p.pk for p in projects[3:]]).delete()
        self.assertEqual(self.create_project().exp_name, 'PCA004')

    def test_delete_all_restarts_at_one(self):
        self.create_project().delete()
        self.assertEqual(self.create_project().exp_name, 'PCA001')

    def test_numeric_maximum_beyond_three_digits(self):
        for name in ('PCA999', 'PCA1000', 'PCA-note', 'PCA2000AA', 'OTHER9000'):
            Project.objects.create(exp_name=name, project=self.category, owner=self.owner)
        self.assertEqual(self.create_project().exp_name, 'PCA1001')

    def test_legacy_categories_share_numbering_prefix(self):
        other = ProjectCategory.objects.create(
            group=self.team, project_name='Legacy', project_code='OLD',
        )
        Project.objects.create(exp_name='PCA008', project=other, owner=self.owner)
        self.assertEqual(self.create_project().exp_name, 'PCA009')

    def test_other_teams_have_independent_sequences(self):
        self.create_project()
        other = ResearchGroup.objects.create(group_name='Other', team_code='PCB')
        self.assertEqual(Project.create_for_team(team=other, owner=self.owner).exp_name, 'PCB001')

    def test_database_rejects_duplicate_numbers(self):
        project = self.create_project()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Project.objects.create(exp_name=project.exp_name, project=self.category, owner=self.owner)

    def test_both_creation_views_after_deletion(self):
        self.client.force_login(self.owner)
        for endpoint in ('add_experiment', 'add_managed_project'):
            for deleted, expected in ((2, 'PCA004'), (3, 'PCA003'), (None, 'PCA001')):
                with self.subTest(endpoint=endpoint, deleted=deleted):
                    Project.objects.all().delete()
                    projects = [self.create_project() for _ in range(3)]
                    if deleted is None:
                        Project.objects.all().delete()
                    else:
                        projects[deleted - 1].delete()
                    response = self.client.post(reverse(endpoint), {
                        'team': self.team.pk, 'owner': self.owner.pk,
                        'exp_description': 'Created after deletion',
                    })
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(Project.objects.get(exp_description='Created after deletion').exp_name, expected)


class ConcurrentProjectNumberingTests(TransactionTestCase):
    def test_concurrent_first_projects_have_distinct_numbers(self):
        if connection.vendor == 'sqlite' and (
            ':memory:' in str(connection.settings_dict['NAME'])
            or 'mode=memory' in str(connection.settings_dict['NAME'])
        ):
            self.skipTest('SQLite shared-memory databases do not wait for write locks; use a file-backed test database.')
        team = ResearchGroup.objects.create(group_name='Concurrent', team_code='PCA')
        owner = User.objects.create(username='concurrent')
        barrier = Barrier(2)

        def create():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                with transaction.atomic():
                    return Project.create_for_team(team=team, owner=owner).exp_name
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(create) for _ in range(2)]
            names = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(names), ['PCA001', 'PCA002'])
        self.assertEqual(ProjectCategory.objects.filter(group=team).count(), 1)
