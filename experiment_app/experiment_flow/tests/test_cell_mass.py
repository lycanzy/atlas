import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.urls import reverse

from experiment_flow.audit import step_snapshot
from experiment_flow.models import Cell, ExperimentStep
from experiment_flow.views import save_step_cells
from django.test import TestCase
from . import test_views


class CellMassTests(TestCase):
    setUp = test_views.ViewTests.setUp
    def test_mass_create_edit_clear_and_legacy_payload(self):
        step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment1_item)
        record = {'test_order_number': 'TEST-1', 'barcode': 'CELL-MASS', 'active_material_mass_g': '0.012345'}
        def save():
            save_step_cells(step, json.dumps({'records': [record]}))
        save()
        cell = step.cells.get()
        self.assertEqual(cell.active_material_mass_g, Decimal('0.012345'))
        self.assertEqual(step_snapshot(step)['cells'][0]['active_material_mass_g'], '0.012345')
        record['id'] = cell.id
        record.pop('active_material_mass_g')
        save()
        cell.refresh_from_db()
        self.assertEqual(cell.active_material_mass_g, Decimal('0.012345'))
        record['active_material_mass_g'] = '0.023456'
        save()
        cell.refresh_from_db()
        self.assertEqual(cell.active_material_mass_g, Decimal('0.023456'))
        self.client.force_login(self.user1)
        response = self.client.get(reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]))
        self.assertContains(response, 'value="0.023456"')
        self.assertContains(response, '活性物质量 (g)')
        record['active_material_mass_g'] = ''
        save()
        cell.refresh_from_db()
        self.assertIsNone(cell.active_material_mass_g)

    def test_invalid_mass_rejects_entire_batch(self):
        step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment1_item)
        for value in ['-1', '0', 'NaN', 'Infinity', 'abc', '0.0000001', '100000000']:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    save_step_cells(step, json.dumps({'records': [
                        {'test_order_number': 'T1', 'barcode': 'GOOD', 'active_material_mass_g': '0.1'},
                        {'test_order_number': 'T1', 'barcode': 'BAD', 'active_material_mass_g': value},
                    ]}))
                self.assertFalse(step.cells.exists())
