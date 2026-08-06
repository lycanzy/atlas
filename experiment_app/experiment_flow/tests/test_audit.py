import json
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from experiment_flow.models import (
    AuditLog, Cell, Equipment, Experiment, ExperimentStep, Project, ProjectCategory,
    RawMaterial, RawMaterialType, ResearchGroup, StepNameTemplate, UserProfile,
)


class FullAuditTests(TestCase):
    def setUp(self):
        self.client = Client(REMOTE_ADDR='127.0.0.9')
        self.team = ResearchGroup.objects.create(group_name='Audit Lab', team_code='AUD')
        self.user = User.objects.create_user(username='auditor', password='old-password')
        UserProfile.objects.create(user=self.user, research_group=self.team)
        self.staff = User.objects.create_user(username='manager', password='password', is_staff=True)
        self.category = ProjectCategory.objects.create(
            project_name='Audit Lab', project_code='AUD', group=self.team,
        )
        self.project = Project.objects.create(exp_name='AUD001', project=self.category, owner=self.user)
        self.experiment = Experiment.objects.create(experiment_code='AA', project=self.project)
        StepNameTemplate.objects.create(step_code='AA', step_label='Parent')
        StepNameTemplate.objects.create(step_code='BB', step_label='Mixing')
        RawMaterialType.objects.create(name='Powder')

    def test_authentication_events_exclude_credentials(self):
        response = self.client.post(reverse('login'), {'username': 'auditor', 'password': 'old-password'})
        self.assertEqual(response.status_code, 302)
        login_log = AuditLog.objects.get(action='login')
        self.assertEqual(login_log.actor_username, 'auditor')
        self.assertEqual(login_log.ip_address, '127.0.0.9')
        self.assertNotIn('old-password', json.dumps(login_log.changes))

        self.client.get(reverse('logout'))
        self.assertTrue(AuditLog.objects.filter(action='logout', actor_username='auditor').exists())

        self.client.post(reverse('login'), {'username': 'auditor', 'password': 'wrong-secret'})
        failure = AuditLog.objects.get(action='login_failed')
        self.assertEqual(failure.outcome, 'failed')
        self.assertNotIn('wrong-secret', json.dumps(failure.changes))

    def test_equipment_create_and_update_record_only_changes(self):
        self.client.login(username='auditor', password='old-password')
        payload = {
            'equipment_name': 'Coater', 'equipment_id': 'EQ-01', 'owner': self.user.id,
            'location': 'Lab 1', 'description': 'Initial', 'size': '1m',
            'power_requirement': '5kW', 'voltage': '220V', 'current': '10A',
            'water_requirement': 'DI', 'gas_input': 'N2',
            'exhaust_requirement': '500 CFM', 'is_active': 'on',
        }
        self.client.post(reverse('add_equipment'), payload)
        equipment = Equipment.objects.get(equipment_id='EQ-01')
        created = AuditLog.objects.get(category='equipment', action='create')
        self.assertEqual(created.summary, '登记设备 Coater')
        self.assertEqual(created.changes['location']['after'], 'Lab 1')

        payload.update({'location': 'Lab 2', 'is_active': ''})
        self.client.post(reverse('edit_equipment', args=[equipment.id]), payload)
        updated = AuditLog.objects.get(category='equipment', action='update')
        self.assertEqual(set(updated.changes), {'location', 'is_active'})
        self.assertEqual(updated.changes['location'], {'before': 'Lab 1', 'after': 'Lab 2'})

    def test_raw_material_batch_regeneration_is_explicit(self):
        self.client.login(username='auditor', password='old-password')
        payload = {
            'material_code': 'rm01', 'received_date': '2026-07-01',
            'material_type': 'Powder', 'material_name': 'Salt', 'owner': self.user.id,
            'total_quantity': '500', 'total_unit': 'g',
            'supplier': 'Vendor', 'location': 'Shelf A', 'description': 'Initial',
            'notes': 'dry', 'is_active': 'on',
        }
        self.client.post(reverse('add_raw_material'), payload)
        material = RawMaterial.objects.get(material_code='RM01')
        self.assertEqual(material.batch_number, 'RM01-070126')
        created = AuditLog.objects.get(category='raw_material', action='create')
        self.assertEqual(created.changes['batch_number']['after'], 'RM01-070126')
        self.assertEqual(created.changes['total_quantity']['after'], '500')

        payload.update({'material_code': 'rm02', 'received_date': '2026-07-02', 'supplier': 'Vendor B', 'total_quantity': '450'})
        self.client.post(reverse('edit_raw_material', args=[material.id]), payload)
        updated = AuditLog.objects.get(category='raw_material', action='update')
        self.assertEqual(updated.changes['batch_number']['before'], 'RM01-070126')
        self.assertEqual(updated.changes['batch_number']['after'], 'RM02-070226')
        self.assertIn('supplier', updated.changes)
        self.assertEqual(updated.changes['total_quantity'], {'before': '500.0000', 'after': '450'})

    def test_step_audit_contains_samples_material_usage_and_parent(self):
        self.client.login(username='auditor', password='old-password')
        material = RawMaterial.objects.create(
            material_code='RM', received_date=date(2026, 7, 1), owner=self.user,
        )
        parent = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment)
        self.client.post(reverse('add_step', args=[self.project.id, self.experiment.id]), {
            'step_name': 'BB', 'step_description': 'Mix', 'status': 'Planned',
            'parents': [str(parent.id)], 'sample_count': 2,
            'cells_payload': json.dumps({
                'records': [{
                    'id': None, 'package_number': 'pkg-01', 'barcode': 'cell-001',
                }],
                'deleted_ids': [],
            }),
            'raw_material_usages': json.dumps([{
                'raw_material_id': material.id, 'quantity': '2.5', 'unit': 'g', 'notes': 'charge',
            }]),
        })
        log = AuditLog.objects.get(category='step', action='create')
        details = log.changes['after']
        self.assertEqual(details['sample_count'], 2)
        self.assertEqual(details['parents'], [parent.full_step])
        self.assertEqual(details['cell_count'], 1)
        self.assertEqual(details['cells'][0]['package_number'], 'PKG-01')
        self.assertEqual(details['cells'][0]['barcode'], 'CELL-001')
        self.assertEqual(details['raw_material_usages'][0]['batch_number'], material.batch_number)
        self.assertEqual(details['raw_material_usages'][0]['quantity'], '2.5000')

    def test_bulk_status_and_delete_each_write_one_event(self):
        self.client.login(username='auditor', password='old-password')
        steps = [ExperimentStep.objects.create(step_name='AA', experiment=self.experiment) for _ in range(2)]
        ids = [step.id for step in steps]
        self.client.post(
            reverse('bulk_update_status', args=[self.project.id]),
            json.dumps({'step_ids': ids, 'status': 'Completed'}), content_type='application/json',
        )
        self.assertEqual(AuditLog.objects.filter(category='step', action='status').count(), 1)
        self.client.post(
            reverse('delete_steps', args=[self.project.id]),
            json.dumps({'step_ids': ids}), content_type='application/json',
        )
        self.assertEqual(AuditLog.objects.filter(category='step', action='delete').count(), 1)

    def test_cell_correction_and_removal_are_recorded_in_step_audit(self):
        self.client.login(username='auditor', password='old-password')
        step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment)
        changed_cell = Cell.objects.create(
            step=step, package_number='PKG-01', barcode='CELL-001',
        )
        removed_cell = Cell.objects.create(
            step=step, package_number='PKG-01', barcode='CELL-002',
        )
        AuditLog.objects.all().delete()

        response = self.client.post(
            reverse('edit_step', args=[self.project.id, self.experiment.id, step.id]),
            {
                'step_name': 'AA', 'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [{
                        'id': changed_cell.id,
                        'package_number': 'PKG-02',
                        'barcode': 'CELL-001A',
                    }],
                    'deleted_ids': [removed_cell.id],
                }),
            },
        )

        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(category='step', action='update')
        self.assertIn('cells', log.changes)
        self.assertEqual(len(log.changes['cells']['before']), 2)
        self.assertEqual(log.changes['cells']['after'][0]['package_number'], 'PKG-02')
        self.assertEqual(log.changes['cells']['after'][0]['barcode'], 'CELL-001A')

    def test_deleted_actor_uses_username_snapshot(self):
        self.client.login(username='auditor', password='old-password')
        self.client.post(reverse('add_equipment'), {
            'equipment_name': 'Press', 'equipment_id': 'EQ-02', 'owner': self.user.id,
            'location': 'Lab', 'is_active': 'on',
        })
        log = AuditLog.objects.get(category='equipment')
        self.user.delete()
        log.refresh_from_db()
        self.assertIsNone(log.actor)
        self.assertEqual(log.actor_username, 'auditor')

    def test_management_audit_filters_and_paginates(self):
        for index in range(55):
            AuditLog.objects.create(
                actor_username='auditor', actor_team='Audit Lab (AUD)', category='equipment',
                action='update', outcome='success', entity_type='Equipment',
                object_repr=f'Equipment {index}', summary=f'修改设备 {index}',
            )
        self.client.login(username='manager', password='password')
        response = self.client.get(reverse('management_dashboard'), {
            'audit_actor': 'auditor', 'audit_category': 'equipment',
            'audit_outcome': 'success', 'audit_page': 2,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['audit_page_obj'].number, 2)
        self.assertEqual(len(response.context['audit_logs']), 5)
