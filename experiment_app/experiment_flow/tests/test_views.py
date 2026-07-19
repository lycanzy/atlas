from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date
from experiment_flow.models import (
    AuditLog, Cell, ResearchGroup, UserProfile, ProjectCategory, Project, Experiment, ExperimentStep, Sample, StepNameTemplate,
    RawMaterial, StepRawMaterialUsage
)
import json

class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Setup users and groups
        self.group1 = ResearchGroup.objects.create(group_name="Group 1", team_code="PRA")
        self.group2 = ResearchGroup.objects.create(group_name="Group 2", team_code="PRB")
        
        self.user1 = User.objects.create_user(username="user1", password="password")
        UserProfile.objects.create(user=self.user1, research_group=self.group1)
        
        self.user2 = User.objects.create_user(username="user2", password="password")
        UserProfile.objects.create(user=self.user2, research_group=self.group2)
        
        self.staff_user = User.objects.create_user(username="staff", password="password", is_staff=True)
        
        # Setup data for Group 1
        self.project1 = ProjectCategory.objects.create(project_name="P1", project_code="PRA", group=self.group1)
        self.exp1 = Project.objects.create(exp_name="PRA001", project=self.project1, owner=self.user1)
        self.experiment1_item = Experiment.objects.create(experiment_code="AA", project=self.exp1)
        
        # Setup data for Group 2
        self.project2 = ProjectCategory.objects.create(project_name="P2", project_code="PRB", group=self.group2)
        self.exp2 = Project.objects.create(exp_name="PRB001", project=self.project2, owner=self.user2)

        # Setup templates
        StepNameTemplate.objects.create(step_code="AA", step_label="Step A")
        self.raw_material = RawMaterial.objects.create(
            material_code="RM001",
            received_date=date(2026, 6, 19),
            material_type="Powder",
            material_name="Test Powder",
            owner=self.user1,
            supplier="Vendor A",
            location="Shelf 1"
        )

    def test_index_view_permissions(self):
        # User 1 should see Project 1 but not Project 2
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRA001")
        self.assertNotContains(response, "PRB001")
        
        # User 2 should see Project 2 but not Project 1
        self.client.login(username="user2", password="password")
        response = self.client.get(reverse('index'))
        self.assertContains(response, "PRB001")
        self.assertNotContains(response, "PRA001")
        
        # Staff should see both
        self.client.login(username="staff", password="password")
        response = self.client.get(reverse('index'))
        self.assertContains(response, "PRA001")
        self.assertContains(response, "PRB001")

    def test_experiment_detail_permissions(self):
        # User 1 accessing Project 1 -> OK
        self.exp1.exp_description = "Project one description"
        self.exp1.save()
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project one description")
        self.assertNotContains(response, "序号")
        
        # User 1 accessing Project 2 -> Redirect/Error
        response = self.client.get(reverse('experiment_detail', args=[self.exp2.id]))
        self.assertEqual(response.status_code, 302) # Redirects to index
        
        # Staff accessing Project 2 -> OK
        self.client.login(username="staff", password="password")
        response = self.client.get(reverse('experiment_detail', args=[self.exp2.id]))
        self.assertEqual(response.status_code, 200)

    def test_add_experiment(self):
        self.client.login(username="user1", password="password")
        
        # Post valid data
        response = self.client.post(reverse('add_experiment'), {
            'team': self.group1.id,
            'exp_description': 'New Project'
        })
        self.assertEqual(response.status_code, 302) # Redirects to index
        
        # Check created
        self.assertTrue(Project.objects.filter(exp_name="PRA002").exists())
        
        # Try to add to team 2 (not in group)
        response = self.client.post(reverse('add_experiment'), {
            'team': self.group2.id,
            'exp_description': 'Hacked Project'
        })
        # Should fail (likely 404 or validation error caught in view)
        # The view catches ResearchGroup.DoesNotExist if filtered by group
        self.assertEqual(response.status_code, 200) # Renders form with error
        self.assertContains(response, "Selected team not found")

    def test_add_project_experiment(self):
        self.client.login(username="user1", password="password")
        
        # Add project_experiment to Project 1
        response = self.client.post(reverse('add_project_experiment', args=[self.exp1.id]), {
            'experiment_code': 'BB'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Experiment.objects.filter(full_experiment_code="PRA001BB").exists())
        
        # Try to add project_experiment to Project 2
        response = self.client.post(reverse('add_project_experiment', args=[self.exp2.id]), {
            'experiment_code': 'BB'
        })
        self.assertEqual(response.status_code, 302) # Redirects to index due to permission
        self.assertFalse(Experiment.objects.filter(full_experiment_code="PRB001BB").exists())

    def test_add_step(self):
        self.client.login(username="user1", password="password")
        
        # Add step to Experiment 1
        response = self.client.post(reverse('add_step', args=[self.exp1.id, self.experiment1_item.id]), {
            'step_name': 'AA',
            'step_description': 'Test Step',
            'status': 'Planned',
            'sample_count': 3,
            'raw_material_usages': json.dumps([
                {
                    'raw_material_id': self.raw_material.id,
                    'quantity': '2.5',
                    'unit': 'g',
                    'notes': 'first batch'
                }
            ])
        })
        self.assertEqual(response.status_code, 302)
        step = ExperimentStep.objects.get(full_step="PRA001AA-AA00")
        usage = StepRawMaterialUsage.objects.get(step=step)
        self.assertEqual(usage.raw_material, self.raw_material)
        self.assertEqual(usage.unit, 'g')
        self.assertEqual(step.samples.count(), 3)
        self.assertEqual(
            list(step.samples.values_list('sample_name', flat=True)),
            ['PRA001AA-AA00-01', 'PRA001AA-AA00-02', 'PRA001AA-AA00-03'],
        )

    def test_add_step_renders_step_cell_and_sample_tabs(self):
        self.client.login(username="user1", password="password")

        response = self.client.get(
            reverse('add_step', args=[self.exp1.id, self.experiment1_item.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-target="#step-details-pane"')
        self.assertContains(response, 'data-bs-target="#step-cells-pane"')
        self.assertContains(response, 'data-bs-target="#step-samples-pane"')
        self.assertContains(response, '实验步骤')
        self.assertContains(response, '连续扫码，或每行粘贴一个 Barcode')
        self.assertContains(response, '填写样品数量并保存步骤后，将自动生成样品编号。')

    def test_add_step_with_cells(self):
        self.client.login(username="user1", password="password")
        response = self.client.post(
            reverse('add_step', args=[self.exp1.id, self.experiment1_item.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [
                        {'id': None, 'package_number': ' pkg-01 ', 'barcode': ' cell-001 '},
                        {'id': None, 'package_number': 'PKG-01', 'barcode': 'CELL-002'},
                    ],
                    'deleted_ids': [],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        step = ExperimentStep.objects.get(full_step="PRA001AA-AA00")
        self.assertEqual(
            list(step.cells.values_list('package_number', 'barcode')),
            [('PKG-01', 'CELL-001'), ('PKG-01', 'CELL-002')],
        )

    def test_edit_step_reconciles_cells_and_removed_barcode_can_be_reused(self):
        self.client.login(username="user1", password="password")
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        retained = Cell.objects.create(step=step, package_number="PKG-01", barcode="CELL-001")
        removed = Cell.objects.create(step=step, package_number="PKG-01", barcode="CELL-002")

        response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [
                        {'id': retained.id, 'package_number': 'PKG-02', 'barcode': 'CELL-001A'},
                        {'id': None, 'package_number': 'PKG-02', 'barcode': 'CELL-003'},
                    ],
                    'deleted_ids': [removed.id],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(step.cells.values_list('package_number', 'barcode')),
            [('PKG-02', 'CELL-001A'), ('PKG-02', 'CELL-003')],
        )
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        rebound = Cell.objects.create(
            step=other_step,
            package_number="PKG-03",
            barcode="CELL-002",
        )
        self.assertEqual(rebound.step, other_step)

    def test_duplicate_cell_barcode_rolls_back_step_edit(self):
        self.client.login(username="user1", password="password")
        step = ExperimentStep.objects.create(
            step_name="AA",
            experiment=self.experiment1_item,
            step_description="Before",
        )
        existing = Cell.objects.create(step=step, package_number="PKG-01", barcode="CELL-001")
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        Cell.objects.create(step=other_step, package_number="PKG-02", barcode="DUPLICATE")

        response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            {
                'step_name': 'AA',
                'step_description': 'After',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [
                        {'id': existing.id, 'package_number': 'PKG-01', 'barcode': 'CELL-001'},
                        {'id': None, 'package_number': 'PKG-01', 'barcode': 'DUPLICATE'},
                    ],
                    'deleted_ids': [],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('cells', response.json()['errors'])
        step.refresh_from_db()
        self.assertEqual(step.step_description, 'Before')
        self.assertEqual(list(step.cells.values_list('barcode', flat=True)), ['CELL-001'])

    def test_other_team_cannot_edit_step_cells(self):
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        cell = Cell.objects.create(step=step, package_number="PKG-01", barcode="CELL-001")
        self.client.login(username="user2", password="password")

        response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [],
                    'deleted_ids': [cell.id],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Cell.objects.filter(id=cell.id).exists())

    def test_cell_search_respects_team_access_and_barcode_redirects(self):
        own_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        own_cell = Cell.objects.create(
            step=own_step,
            package_number="PKG-SHARED",
            barcode="OWN-CELL",
        )
        group2_experiment = Experiment.objects.create(experiment_code="AA", project=self.exp2)
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=group2_experiment)
        Cell.objects.create(
            step=other_step,
            package_number="PKG-SHARED",
            barcode="OTHER-CELL",
        )

        self.client.login(username="user1", password="password")
        barcode_response = self.client.get(reverse('global_search'), {'q': 'own-cell'})
        self.assertEqual(barcode_response.status_code, 302)
        self.assertIn(f'highlight_cell={own_cell.id}', barcode_response.url)
        self.assertIn(f'expanded_cells={own_step.id}', barcode_response.url)

        package_response = self.client.get(reverse('global_search'), {'q': 'pkg-shared'})
        self.assertEqual(package_response.status_code, 200)
        self.assertContains(package_response, 'OWN-CELL')
        self.assertNotContains(package_response, 'OTHER-CELL')

        hidden_response = self.client.get(reverse('global_search'), {'q': 'OTHER-CELL'})
        self.assertEqual(hidden_response.status_code, 302)
        self.assertEqual(hidden_response.url, reverse('index'))

        self.client.login(username="staff", password="password")
        staff_response = self.client.get(reverse('global_search'), {'q': 'PKG-SHARED'})
        self.assertContains(staff_response, 'OWN-CELL')
        self.assertContains(staff_response, 'OTHER-CELL')

    def test_cell_details_render_in_experiment_and_genealogy(self):
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        Cell.objects.create(step=step, package_number="PKG-01", barcode="CELL-001")
        self.client.login(username="user1", password="password")

        detail_response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))
        self.assertContains(detail_response, '电芯')
        self.assertContains(detail_response, 'PKG-01')
        self.assertContains(detail_response, 'CELL-001')

        genealogy_response = self.client.get(reverse('step_genealogy', args=[step.id]))
        self.assertContains(genealogy_response, '当前步骤电芯')
        self.assertContains(genealogy_response, 'PKG-01')
        self.assertContains(genealogy_response, 'CELL-001')

    def test_edit_step_renders_step_cell_and_sample_tabs(self):
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        Cell.objects.create(step=step, package_number="PKG-01", barcode="CELL-001")
        Sample.sync_for_step(step, 2)
        self.client.login(username="user1", password="password")

        response = self.client.get(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-target="#step-details-pane"')
        self.assertContains(response, 'data-bs-target="#step-cells-pane"')
        self.assertContains(response, 'data-bs-target="#step-samples-pane"')
        self.assertContains(response, '实验步骤')
        self.assertContains(response, 'CELL-001')
        self.assertContains(response, f'{step.full_step}-01')
        self.assertContains(response, f'{step.full_step}-02')

    def test_add_step_with_multiple_parents(self):
        self.client.login(username="user1", password="password")

        parent_a = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        parent_b = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)

        response = self.client.post(reverse('add_step', args=[self.exp1.id, self.experiment1_item.id]), {
            'step_name': 'AA',
            'step_description': 'Combined slurry',
            'status': 'Planned',
            'parents': [str(parent_a.id), str(parent_b.id)],
        })

        self.assertEqual(response.status_code, 302)
        step = ExperimentStep.objects.get(step_description="Combined slurry")
        self.assertEqual(set(step.parents.all()), {parent_a, parent_b})
        self.assertEqual(step.parent, parent_a)

    def test_edit_step_replaces_parents(self):
        self.client.login(username="user1", password="password")

        parent_a = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        parent_b = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item, step_description="Before")
        step.parents.set([parent_a])

        response = self.client.post(reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]), {
            'step_name': 'AA',
            'step_description': 'After',
            'status': 'Planned',
            'parents': [str(parent_b.id)],
        })

        self.assertEqual(response.status_code, 302)
        step.refresh_from_db()
        self.assertEqual(step.step_description, "After")
        self.assertEqual(list(step.parents.all()), [parent_b])
        self.assertEqual(step.parent, parent_b)

    def test_delete_step_blocks_step_with_downstream_link(self):
        self.client.login(username="user1", password="password")

        parent = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        child = ExperimentStep.objects.create(step_name="BB", experiment=self.experiment1_item)
        child.parents.set([parent])

        response = self.client.get(reverse('delete_step', args=[self.exp1.id, self.experiment1_item.id, parent.id]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(ExperimentStep.objects.filter(id=parent.id).exists())
        self.assertTrue(ExperimentStep.objects.filter(id=child.id).exists())

    def test_delete_steps_blocks_step_with_legacy_downstream_child(self):
        self.client.login(username="user1", password="password")

        parent = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        child = ExperimentStep.objects.create(step_name="BB", experiment=self.experiment1_item, parent=parent)

        response = self.client.post(
            reverse('delete_steps', args=[self.exp1.id]),
            json.dumps({'step_ids': [parent.id]}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], False)
        self.assertIn(parent.full_step, response.json()['error'])
        self.assertTrue(ExperimentStep.objects.filter(id=parent.id).exists())
        self.assertTrue(ExperimentStep.objects.filter(id=child.id).exists())

    def test_ajax_update_status(self):
        self.client.login(username="user1", password="password")
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        
        url = reverse('update_step_status', args=[step.id])
        data = {'status': 'Completed'}
        
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
        
        step.refresh_from_db()
        self.assertEqual(step.status, 'Completed')
        self.assertIsNotNone(step.completed_on)

    def test_copy_steps(self):
        self.client.login(username="user1", password="password")
        
        # Create source step
        step1 = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item, step_description="Source")
        StepRawMaterialUsage.objects.create(
            step=step1,
            raw_material=self.raw_material,
            quantity="3.0000",
            unit="ml"
        )
        
        # Create target project_experiment
        experiment2 = Experiment.objects.create(experiment_code="BB", project=self.exp1)
        
        url = reverse('copy_steps', args=[self.exp1.id])
        data = {
            'step_ids': [step1.id],
            'target_experiment_code': experiment2.full_experiment_code
        }
        
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
        
        # Verify copy
        copied_step = ExperimentStep.objects.get(experiment=experiment2, step_name="AA", step_description="Source")
        copied_usage = StepRawMaterialUsage.objects.get(step=copied_step)
        self.assertEqual(copied_usage.raw_material, self.raw_material)
        self.assertEqual(copied_usage.unit, "ml")

    def test_raw_material_views_and_search(self):
        self.client.login(username="user1", password="password")

        list_response = self.client.get(reverse('raw_material_list'), {'search': 'Vendor A'})
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "RM001")
        self.assertContains(list_response, "Test Powder")

        detail_response = self.client.get(reverse('raw_material_detail', args=[self.raw_material.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "RM001-061926")

        add_response = self.client.post(reverse('add_raw_material'), {
            'material_code': 'RM002',
            'received_date': '2026-06-20',
            'material_type': 'Liquid',
            'material_name': '',
            'owner': self.user1.id,
            'supplier': 'Vendor B',
            'location': 'Cabinet 2',
            'is_active': 'on'
        })
        self.assertEqual(add_response.status_code, 302)
        self.assertTrue(RawMaterial.objects.filter(material_code="RM002", batch_number="RM002-062026", material_name__isnull=True).exists())

        edit_response = self.client.post(reverse('edit_raw_material', args=[self.raw_material.id]), {
            'material_code': 'RM001',
            'received_date': '2026-06-21',
            'material_type': 'Powder',
            'material_name': '',
            'owner': self.user1.id,
            'supplier': 'Vendor A',
            'location': 'Shelf 2',
            'is_active': 'on'
        })
        self.assertEqual(edit_response.status_code, 302)
        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.batch_number, "RM001-062126")
        self.assertIsNone(self.raw_material.material_name)

    def test_management_dashboard_requires_staff(self):
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse('management_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url.split('?')[0], reverse('index'))

    def test_management_cells_tab_lists_and_filters_cells_across_teams(self):
        own_step = ExperimentStep.objects.create(
            step_name="AA",
            experiment=self.experiment1_item,
        )
        own_cell = Cell.objects.create(
            step=own_step,
            package_number="PKG-MANAGEMENT-A",
            barcode="CELL-MANAGEMENT-A",
        )
        other_experiment = Experiment.objects.create(experiment_code="AA", project=self.exp2)
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=other_experiment)
        Cell.objects.create(
            step=other_step,
            package_number="PKG-MANAGEMENT-B",
            barcode="CELL-MANAGEMENT-B",
        )
        self.client.login(username="staff", password="password")

        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-target="#cells"')
        self.assertContains(response, 'PKG-MANAGEMENT-A')
        self.assertContains(response, 'CELL-MANAGEMENT-A')
        self.assertContains(response, 'CELL-MANAGEMENT-B')
        self.assertContains(response, self.experiment1_item.full_experiment_code)
        self.assertContains(response, own_step.full_step)
        self.assertContains(response, f'highlight_cell={own_cell.id}')
        self.assertEqual(response.context['cell_page_obj'].paginator.count, 2)

        filtered_response = self.client.get(
            reverse('management_dashboard'),
            {'cell_q': 'CELL-MANAGEMENT-A'},
        )
        self.assertContains(filtered_response, 'CELL-MANAGEMENT-A')
        self.assertNotContains(filtered_response, 'CELL-MANAGEMENT-B')
        self.assertEqual(filtered_response.context['cell_page_obj'].paginator.count, 1)

    def test_staff_can_create_team_and_assign_member(self):
        self.client.login(username="staff", password="password")
        response = self.client.post(reverse('add_team'), {
            'group_name': 'New Team',
            'team_code': 'NEW',
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#teams')
        team = ResearchGroup.objects.get(team_code='NEW')
        self.assertTrue(ProjectCategory.objects.filter(group=team, project_code='NEW').exists())

        response = self.client.post(reverse('assign_member_team', args=[self.user1.id]), {
            'research_group': team.id,
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#members')
        self.user1.profile.refresh_from_db()
        self.assertEqual(self.user1.profile.research_group, team)

    def test_project_owner_must_belong_to_project_team(self):
        self.client.login(username="staff", password="password")
        response = self.client.post(reverse('edit_managed_project', args=[self.exp1.id]), {
            'exp_description': 'Updated centrally',
            'owner': self.user2.id,
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#projects')
        self.exp1.refresh_from_db()
        self.assertEqual(self.exp1.owner, self.user1)

        response = self.client.post(reverse('edit_managed_project', args=[self.exp1.id]), {
            'exp_description': 'Updated centrally',
            'owner': self.staff_user.id,
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#projects')
        self.exp1.refresh_from_db()
        self.assertEqual(self.exp1.owner, self.staff_user)
        self.assertEqual(self.exp1.exp_description, 'Updated centrally')

    def test_management_crud_for_projects_members_and_step_templates(self):
        self.client.login(username="staff", password="password")

        response = self.client.post(reverse('add_managed_user'), {
            'username': 'new_member', 'email': 'new@example.com',
            'password': 'secure-pass-123', 'research_group': self.group1.id,
            'is_active': 'on',
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#members')
        member = User.objects.get(username='new_member')
        self.assertEqual(member.profile.research_group, self.group1)

        response = self.client.post(reverse('add_managed_project'), {
            'team': self.group1.id, 'owner': member.id, 'exp_description': 'Managed project',
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#projects')
        project = Project.objects.get(owner=member, exp_description='Managed project')
        self.assertTrue(project.exp_name.startswith('PRA'))

        response = self.client.post(reverse('add_step_template'), {
            'step_code': 'ZZ', 'step_label': 'Managed Step',
            'category': 'Test', 'default_description': 'Template description',
            'is_active': 'on',
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#steps')
        template = StepNameTemplate.objects.get(step_code='ZZ')

        self.client.post(reverse('delete_step_template', args=[template.id]))
        self.assertFalse(StepNameTemplate.objects.filter(id=template.id).exists())
        self.client.post(reverse('delete_managed_project', args=[project.id]))
        self.assertFalse(Project.objects.filter(id=project.id).exists())
        self.client.post(reverse('delete_managed_user', args=[member.id]))
        self.assertFalse(User.objects.filter(id=member.id).exists())

    def test_management_actions_create_persistent_audit_logs(self):
        self.client.login(username="staff", password="password")

        self.client.post(reverse('add_team'), {
            'group_name': 'Audit Team',
            'team_code': 'AUD',
        })
        team = ResearchGroup.objects.get(team_code='AUD')
        create_log = AuditLog.objects.get(action='create', entity_type='Team', object_id=str(team.id))
        self.assertEqual(create_log.actor, self.staff_user)
        self.assertEqual(create_log.changes['team_code']['after'], 'AUD')

        self.client.post(reverse('edit_team', args=[team.id]), {
            'group_name': 'Audited Team',
            'team_code': 'AUD',
        })
        update_log = AuditLog.objects.get(action='update', entity_type='Team', object_id=str(team.id))
        self.assertEqual(update_log.changes['group_name']['before'], 'Audit Team')
        self.assertEqual(update_log.changes['group_name']['after'], 'Audited Team')

        response = self.client.get(reverse('management_dashboard'))
        self.assertContains(response, '审计日志')
        self.assertContains(response, '修改 Team Audited Team (AUD)')

        self.client.post(reverse('delete_team', args=[team.id]))
        self.assertFalse(ResearchGroup.objects.filter(id=team.id).exists())
        delete_log = AuditLog.objects.get(action='delete', entity_type='Team', object_id=str(team.id))
        self.assertEqual(delete_log.object_repr, 'Audited Team (AUD)')

    def test_copy_step_preserves_external_parent(self):
        self.client.login(username="user1", password="password")

        parent = ExperimentStep.objects.create(step_name="MX", experiment=self.experiment1_item)
        child = ExperimentStep.objects.create(step_name="CA", experiment=self.experiment1_item, parent=parent)
        experiment2 = Experiment.objects.create(experiment_code="BB", project=self.exp1)

        response = self.client.post(
            reverse('copy_steps', args=[self.exp1.id]),
            json.dumps({
                'step_ids': [child.id],
                'target_experiment_code': experiment2.full_experiment_code
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)

        copied_child = ExperimentStep.objects.get(experiment=experiment2, step_name="CA")
        self.assertEqual(copied_child.parent, parent)
        self.assertEqual(list(copied_child.parents.all()), [parent])

    def test_copy_steps_remaps_parent_when_parent_is_copied(self):
        self.client.login(username="user1", password="password")

        parent = ExperimentStep.objects.create(step_name="MX", experiment=self.experiment1_item)
        child = ExperimentStep.objects.create(step_name="CA", experiment=self.experiment1_item, parent=parent)
        experiment2 = Experiment.objects.create(experiment_code="BB", project=self.exp1)

        response = self.client.post(
            reverse('copy_steps', args=[self.exp1.id]),
            json.dumps({
                'step_ids': [parent.id, child.id],
                'target_experiment_code': experiment2.full_experiment_code
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)

        copied_parent = ExperimentStep.objects.get(experiment=experiment2, step_name="MX")
        copied_child = ExperimentStep.objects.get(experiment=experiment2, step_name="CA")
        self.assertEqual(copied_child.parent, copied_parent)
        self.assertEqual(list(copied_child.parents.all()), [copied_parent])

    def test_copy_step_preserves_multiple_parent_links(self):
        self.client.login(username="user1", password="password")

        parent_a = ExperimentStep.objects.create(step_name="MX", experiment=self.experiment1_item)
        parent_b = ExperimentStep.objects.create(step_name="MY", experiment=self.experiment1_item)
        child = ExperimentStep.objects.create(step_name="CA", experiment=self.experiment1_item)
        child.parents.set([parent_a, parent_b])
        experiment2 = Experiment.objects.create(experiment_code="BB", project=self.exp1)

        response = self.client.post(
            reverse('copy_steps', args=[self.exp1.id]),
            json.dumps({
                'step_ids': [child.id],
                'target_experiment_code': experiment2.full_experiment_code
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)

        copied_child = ExperimentStep.objects.get(experiment=experiment2, step_name="CA")
        self.assertEqual(set(copied_child.parents.all()), {parent_a, parent_b})

    def test_step_genealogy_view_shows_lineage_descendants_and_materials(self):
        self.client.login(username="user1", password="password")

        root = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item, step_description="Root step")
        current = ExperimentStep.objects.create(step_name="BB", experiment=self.experiment1_item, recipe="R1")
        current.parents.set([root])
        child = ExperimentStep.objects.create(step_name="CC", experiment=self.experiment1_item)
        child.parents.set([current])
        StepRawMaterialUsage.objects.create(
            step=current,
            raw_material=self.raw_material,
            quantity="2.0000",
            unit="g"
        )

        response = self.client.get(reverse('step_genealogy', args=[current.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, root.full_step)
        self.assertContains(response, current.full_step)
        self.assertContains(response, child.full_step)
        self.assertContains(response, self.raw_material.batch_number)
        self.assertContains(response, "R1")

    def test_step_genealogy_view_shows_multiple_upstream_steps(self):
        self.client.login(username="user1", password="password")

        slurry_a = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        slurry_b = ExperimentStep.objects.create(step_name="BB", experiment=self.experiment1_item)
        final_mix = ExperimentStep.objects.create(step_name="MX", experiment=self.experiment1_item)
        final_mix.parents.set([slurry_a, slurry_b])

        response = self.client.get(reverse('step_genealogy', args=[final_mix.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, slurry_a.full_step)
        self.assertContains(response, slurry_b.full_step)
        self.assertContains(response, final_mix.full_step)

    def test_step_genealogy_view_respects_group_access(self):
        self.client.login(username="user1", password="password")
        experiment2 = Experiment.objects.create(experiment_code="AA", project=self.exp2)
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=experiment2)

        response = self.client.get(reverse('step_genealogy', args=[other_step.id]))

        self.assertEqual(response.status_code, 302)
