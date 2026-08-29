import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from experiment_flow.models import (
    Cell,
    CellTestItem,
    Experiment,
    ExperimentStep,
    Project,
    ProjectCategory,
    ResearchGroup,
    StepNameTemplate,
    UserProfile,
)


class CellTestItemTests(TestCase):
    def setUp(self):
        self.group = ResearchGroup.objects.create(group_name='Test Team', team_code='TST')
        self.user = User.objects.create_user(username='member', password='password')
        UserProfile.objects.create(user=self.user, research_group=self.group)
        self.staff = User.objects.create_user(
            username='staff-test-items', password='password', is_staff=True,
        )
        category = ProjectCategory.objects.create(
            project_name='Test Project', project_code='TST', group=self.group,
        )
        self.project = Project.objects.create(
            exp_name='TST001', project=category, owner=self.user,
        )
        self.experiment = Experiment.objects.create(experiment_code='AA', project=self.project)
        StepNameTemplate.objects.create(step_code='AA', step_label='Assembly')

    def test_staff_can_manage_test_items_and_used_item_cannot_be_deleted(self):
        self.client.login(username=self.staff.username, password='password')

        response = self.client.post(reverse('add_cell_test_item'), {
            'name': 'Cycle Life', 'description': 'Long-cycle test', 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#cell-test-items')
        test_item = CellTestItem.objects.get(name='Cycle Life')

        response = self.client.post(reverse('edit_cell_test_item', args=[test_item.id]), {
            'name': 'Cycle Performance', 'description': 'Updated',
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#cell-test-items')
        test_item.refresh_from_db()
        self.assertEqual(test_item.name, 'Cycle Performance')
        self.assertFalse(test_item.is_active)

        step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment)
        Cell.objects.create(
            step=step, test_order_number='PKG-01', barcode='CELL-001', test_item=test_item,
        )
        self.client.post(reverse('delete_cell_test_item', args=[test_item.id]))
        self.assertTrue(CellTestItem.objects.filter(id=test_item.id).exists())

    def test_cell_payload_saves_test_item_and_rejects_unknown_item(self):
        test_item = CellTestItem.objects.create(name='Formation')
        self.client.login(username=self.user.username, password='password')

        response = self.client.post(
            reverse('add_step', args=[self.project.id, self.experiment.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [{
                        'id': None,
                        'test_order_number': 'PKG-01',
                        'barcode': 'CELL-001',
                        'test_item_id': test_item.id,
                    }],
                    'deleted_ids': [],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Cell.objects.get(barcode='CELL-001').test_item, test_item)

        response = self.client.post(
            reverse('add_step', args=[self.project.id, self.experiment.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [{
                        'id': None,
                        'test_order_number': 'PKG-02',
                        'barcode': 'CELL-002',
                        'test_item_id': 999999,
                    }],
                    'deleted_ids': [],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Cell.objects.filter(barcode='CELL-002').exists())

    def test_management_and_cell_editor_show_test_items(self):
        active = CellTestItem.objects.create(name='Rate Capability')
        inactive = CellTestItem.objects.create(name='Retired Protocol', is_active=False)
        step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment)
        Cell.objects.create(
            step=step, test_order_number='PKG-01', barcode='CELL-001', test_item=active,
        )

        self.client.login(username=self.staff.username, password='password')
        management = self.client.get(reverse('management_dashboard'))
        self.assertContains(management, 'data-bs-target="#cell-test-items"')
        self.assertContains(management, 'Rate Capability')
        self.assertContains(management, 'CELL-001')

        self.client.login(username=self.user.username, password='password')
        editor = self.client.get(reverse('add_step', args=[self.project.id, self.experiment.id]))
        self.assertContains(editor, 'Rate Capability')
        self.assertNotContains(editor, 'Retired Protocol')
