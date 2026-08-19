import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from experiment_flow.inventory import attach_inventory_summaries
from experiment_flow.models import (
    Experiment, ExperimentStep, Project, ProjectCategory, RawMaterial,
    RawMaterialType, ResearchGroup, StepRawMaterialUsage, UserProfile,
    StepNameTemplate,
)


class InventoryTests(TestCase):
    def setUp(self):
        self.group = ResearchGroup.objects.create(group_name='Inventory', team_code='INV')
        self.user = User.objects.create_user(username='owner', password='password')
        self.other = User.objects.create_user(username='other', password='password')
        UserProfile.objects.create(user=self.user, research_group=self.group)
        UserProfile.objects.create(user=self.other, research_group=self.group)
        category = ProjectCategory.objects.create(
            project_name='Inventory project', project_code='INV', group=self.group,
        )
        self.project = Project.objects.create(exp_name='INV001', project=category, owner=self.user)
        self.experiment = Experiment.objects.create(experiment_code='AA', project=self.project)
        RawMaterialType.objects.create(name='Powder')
        StepNameTemplate.objects.create(step_code='AA', step_label='Mixing')
        self.material = RawMaterial.objects.create(
            material_code='RM01', received_date=date(2026, 8, 20),
            material_type='Powder', total_quantity='10', total_unit='g', owner=self.user,
        )
        self.client.login(username='owner', password='password')

    def usage(self, status, quantity, step_name='AA'):
        step = ExperimentStep.objects.create(
            step_name=step_name, experiment=self.experiment, status=status,
        )
        StepRawMaterialUsage.objects.create(
            step=step, raw_material=self.material, quantity=quantity, unit='g',
        )
        return step

    def test_inventory_summary_separates_completed_planned_and_canceled(self):
        self.usage('Completed', '6', 'AA')
        self.usage('Planned', '2', 'BB')
        self.usage('Canceled', '9', 'CC')

        material = attach_inventory_summaries([self.material])[0]

        self.assertEqual(material.completed_quantity, Decimal('6'))
        self.assertEqual(material.planned_quantity, Decimal('2'))
        self.assertEqual(material.remaining_quantity, Decimal('4'))
        self.assertEqual(material.projected_remaining_quantity, Decimal('2'))
        self.assertEqual(material.inventory_state, 'normal')

    def test_status_completion_requires_confirmation_before_negative_inventory(self):
        step = self.usage('Planned', '12')
        url = reverse('update_step_status', args=[step.id])

        response = self.client.post(
            url, json.dumps({'status': 'Completed'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()['requires_confirmation'])
        step.refresh_from_db()
        self.assertEqual(step.status, 'Planned')

        response = self.client.post(
            url,
            json.dumps({'status': 'Completed', 'allow_negative': True}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        step.refresh_from_db()
        self.assertEqual(step.status, 'Completed')
        material = attach_inventory_summaries([self.material])[0]
        self.assertEqual(material.remaining_quantity, Decimal('-2'))
        self.assertEqual(material.inventory_state, 'critical')

    def test_bulk_completion_is_all_or_nothing(self):
        first = self.usage('Planned', '6', 'AA')
        second = self.usage('Planned', '6', 'BB')
        url = reverse('bulk_update_status', args=[self.project.id])
        payload = {'step_ids': [first.id, second.id], 'status': 'Completed'}

        response = self.client.post(url, json.dumps(payload), content_type='application/json')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            set(ExperimentStep.objects.filter(id__in=[first.id, second.id]).values_list('status', flat=True)),
            {'Planned'},
        )

    def test_editing_completed_usage_recalculates_and_confirms_shortage(self):
        step = self.usage('Completed', '8')
        payload = {
            'step_name': step.step_name, 'status': 'Completed', 'sample_count': 0,
            'raw_material_usages': json.dumps([{
                'raw_material_id': self.material.id,
                'quantity': '12', 'unit': 'g', 'notes': 'adjusted',
            }]),
        }
        url = reverse('edit_step', args=[self.project.id, self.experiment.id, step.id])

        response = self.client.post(url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(step.raw_material_usages.get().quantity, Decimal('8'))

        payload['allow_negative'] = '1'
        response = self.client.post(url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(step.raw_material_usages.get().quantity, Decimal('12'))

    def test_returning_negative_completed_step_to_planned_does_not_warn(self):
        step = self.usage('Completed', '12')

        response = self.client.post(
            reverse('update_step_status', args=[step.id]),
            json.dumps({'status': 'Planned'}), content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        step.refresh_from_db()
        self.assertEqual(step.status, 'Planned')

    def test_api_adds_inventory_fields_without_removing_existing_fields(self):
        self.usage('Completed', '3')
        response = self.client.get(reverse('get_raw_materials'))

        material = response.json()['raw_materials'][0]
        self.assertEqual(material['material_code'], 'RM01')
        self.assertEqual(material['total_quantity'], '10.0000')
        self.assertEqual(material['completed_quantity'], '3')
        self.assertEqual(material['remaining_quantity'], '7.0000')
        self.assertEqual(material['inventory_state'], 'normal')
        self.assertTrue(material['inventory_ready'])

    def test_only_owner_or_admin_can_edit_material(self):
        self.client.logout()
        self.client.login(username='other', password='password')

        response = self.client.get(reverse('edit_raw_material', args=[self.material.id]))

        self.assertEqual(response.status_code, 403)

    def test_lowering_total_below_completed_usage_requires_confirmation(self):
        self.usage('Completed', '8')
        payload = {
            'material_code': 'RM01', 'received_date': '2026-08-20',
            'material_type': 'Powder', 'material_name': '',
            'total_quantity': '5', 'total_unit': 'g', 'owner': self.user.id,
            'supplier': '', 'location': '', 'description': '', 'notes': '',
            'is_active': 'on',
        }
        url = reverse('edit_raw_material', args=[self.material.id])

        response = self.client.post(url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 409)
        self.material.refresh_from_db()
        self.assertEqual(self.material.total_quantity, Decimal('10'))

        payload['allow_negative'] = '1'
        response = self.client.post(url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 302)
        self.material.refresh_from_db()
        self.assertEqual(self.material.total_quantity, Decimal('5'))

    def test_incomplete_legacy_material_is_inventory_unknown_and_not_selectable(self):
        legacy = RawMaterial.objects.create(
            material_code='OLD', received_date=date(2026, 8, 19), owner=self.user,
        )
        response = self.client.get(reverse('get_raw_materials'))
        api_material = next(item for item in response.json()['raw_materials'] if item['id'] == legacy.id)
        self.assertFalse(api_material['inventory_ready'])
        self.assertEqual(api_material['inventory_state'], 'unknown')

        response = self.client.post(reverse('add_step', args=[self.project.id, self.experiment.id]), {
            'step_name': 'AA', 'status': 'Planned', 'sample_count': 0,
            'raw_material_usages': json.dumps([{
                'raw_material_id': legacy.id, 'quantity': '1', 'unit': 'g',
            }]),
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ExperimentStep.objects.filter(raw_material_usages__raw_material=legacy).exists())
