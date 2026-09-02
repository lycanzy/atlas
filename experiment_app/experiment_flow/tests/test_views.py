from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date, datetime
from decimal import Decimal
from django.utils import timezone
from experiment_flow.models import (
    AuditLog, Cell, CellSampleLink, ResearchGroup, UserProfile, ProjectCategory, Project, Experiment, ExperimentStep, Sample, StepNameTemplate,
    RawMaterial, RawMaterialType, StepRawMaterialUsage
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
        RawMaterialType.objects.create(name="Powder")
        RawMaterialType.objects.create(name="Liquid")
        self.raw_material = RawMaterial.objects.create(
            material_code="RM001",
            batch_number="RM001-061926",
            received_date=date(2026, 6, 19),
            material_type="Powder",
            material_name="Test Powder",
            total_quantity="1000.0000",
            total_unit="g",
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

    def test_index_cell_count_follows_visible_projects(self):
        group1_step = ExperimentStep.objects.create(
            step_name="AA", experiment=self.experiment1_item,
        )
        group2_experiment = Experiment.objects.create(
            experiment_code="AA", project=self.exp2,
        )
        group2_step = ExperimentStep.objects.create(
            step_name="AA", experiment=group2_experiment,
        )
        Cell.objects.create(step=group1_step, test_order_number="PKG-1", barcode="CELL-1")
        Cell.objects.create(step=group1_step, test_order_number="PKG-1", barcode="CELL-2")
        Cell.objects.create(step=group2_step, test_order_number="PKG-2", barcode="CELL-3")

        self.client.login(username="user1", password="password")
        response = self.client.get(reverse('index'))
        self.assertEqual(response.context['overview_stats']['cell_count'], 3)
        self.assertContains(response, "电芯总数")
        mine_response = self.client.get(reverse('index'), {'overview_scope': 'mine'})
        self.assertEqual(mine_response.context['overview_stats']['cell_count'], 2)

        self.client.login(username="staff", password="password")
        response = self.client.get(reverse('index'))
        self.assertEqual(response.context['overview_stats']['cell_count'], 3)

    def test_overview_scope_switches_between_mine_and_group(self):
        teammate = User.objects.create_user(username='teammate', password='password')
        UserProfile.objects.create(user=teammate, research_group=self.group1)
        teammate_project = Project.objects.create(
            exp_name='PRA002', project=self.project1, owner=teammate,
        )
        teammate_experiment = Experiment.objects.create(
            experiment_code='AA', project=teammate_project,
        )
        ExperimentStep.objects.create(step_name='AA', experiment=teammate_experiment)

        self.client.login(username='user1', password='password')
        mine = self.client.get(reverse('index'), {'overview_scope': 'mine'})
        global_scope = self.client.get(reverse('index'), {'overview_scope': 'global'})

        self.assertEqual(mine.context['overview_stats']['total_count'], 1)
        self.assertEqual(global_scope.context['overview_stats']['total_count'], 3)
        self.assertEqual(mine.context['overview_stats']['active_experiment_count'], 1)
        self.assertEqual(global_scope.context['overview_stats']['active_experiment_count'], 2)
        self.assertEqual(global_scope.context['overview_global_label'], '全部团队')
        self.assertNotContains(global_scope, 'PRB001')

    def test_overview_rejects_unknown_time_range(self):
        self.client.login(username='user1', password='password')
        response = self.client.get(reverse('index'), {'overview_days': '365'})
        self.assertEqual(response.context['overview_days'], 14)
        self.assertEqual(len(response.context['growth_chart']['points']), 14)

    def test_changelog_page_requires_login_and_renders_repository_log(self):
        anonymous = self.client.get(reverse('changelog'))
        self.assertRedirects(anonymous, f"{reverse('login')}?next={reverse('changelog')}")

        self.client.login(username='user1', password='password')
        response = self.client.get(reverse('changelog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '更新日志')
        self.assertContains(response, '[Unreleased]')

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
            'experiment_code': 'BB',
            'experiment_description': 'Validate the new formulation',
        })
        self.assertEqual(response.status_code, 302)
        created = Experiment.objects.get(full_experiment_code="PRA001BB")
        self.assertEqual(created.experiment_description, 'Validate the new formulation')
        
        # Try to add project_experiment to Project 2
        response = self.client.post(reverse('add_project_experiment', args=[self.exp2.id]), {
            'experiment_code': 'BB',
            'experiment_description': 'Unauthorized experiment',
        })
        self.assertEqual(response.status_code, 302) # Redirects to index due to permission
        self.assertFalse(Experiment.objects.filter(full_experiment_code="PRB001BB").exists())

    def test_add_project_experiment_requires_non_blank_description(self):
        self.client.login(username="user1", password="password")

        response = self.client.post(
            reverse('add_project_experiment', args=[self.exp1.id]),
            {'experiment_code': 'BB', 'experiment_description': '   '},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], '实验描述为必填项。')
        self.assertFalse(Experiment.objects.filter(full_experiment_code='PRA001BB').exists())

    def test_description_source_search_follows_access_and_puts_current_project_first(self):
        self.experiment1_item.experiment_description = 'Current project source'
        self.experiment1_item.save()
        same_group_project = Project.objects.create(
            exp_name='PRA002', project=self.project1, owner=self.user1,
        )
        same_group_source = Experiment.objects.create(
            experiment_code='AB', project=same_group_project,
            experiment_description='Same group source',
        )
        hidden_source = Experiment.objects.create(
            experiment_code='AA', project=self.exp2,
            experiment_description='Other group secret',
        )
        Experiment.objects.create(
            experiment_code='AC', project=same_group_project,
            experiment_description='   ',
        )
        self.client.login(username='user1', password='password')

        detail_response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))
        response = self.client.get(
            reverse('search_experiment_description_sources', args=[self.exp1.id]),
            {'q': 'source'},
        )
        sources = response.json()['results']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sources[0]['id'], self.experiment1_item.id)
        self.assertIn(same_group_source.id, [source['id'] for source in sources])
        self.assertNotIn(hidden_source.id, [source['id'] for source in sources])
        self.assertNotIn('Other group secret', response.content.decode())
        self.assertNotIn('Same group source', detail_response.content.decode())
        self.assertNotContains(detail_response, 'experimentDescriptionSources')

    def test_description_source_search_requires_two_characters_and_paginates(self):
        for index in range(21):
            project = Project.objects.create(
                exp_name=f'PRA{index + 100:03d}', project=self.project1, owner=self.user1,
            )
            Experiment.objects.create(
                experiment_code='AA', project=project,
                experiment_description=f'Shared coating description {index}',
            )
        self.client.login(username='user1', password='password')
        url = reverse('search_experiment_description_sources', args=[self.exp1.id])

        short_response = self.client.get(url, {'q': 'P'})
        first_page = self.client.get(url, {'q': 'PRA', 'page': 1})
        second_page = self.client.get(url, {'q': 'PRA', 'page': 2})

        self.assertEqual(short_response.json()['results'], [])
        self.assertEqual(len(first_page.json()['results']), 20)
        self.assertTrue(first_page.json()['pagination']['more'])
        self.assertEqual(len(second_page.json()['results']), 1)
        self.assertFalse(second_page.json()['pagination']['more'])

    def test_description_source_detail_returns_full_description_after_selection(self):
        self.experiment1_item.experiment_description = 'Full reusable description'
        self.experiment1_item.save()
        hidden_source = Experiment.objects.create(
            experiment_code='AA', project=self.exp2,
            experiment_description='Other group secret',
        )
        self.client.login(username='user1', password='password')

        response = self.client.get(reverse(
            'get_experiment_description_source',
            args=[self.exp1.id, self.experiment1_item.id],
        ))
        hidden_response = self.client.get(reverse(
            'get_experiment_description_source',
            args=[self.exp1.id, hidden_source.id],
        ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['description'], 'Full reusable description')
        self.assertEqual(hidden_response.status_code, 404)

    def test_add_project_experiment_logs_copy_source_without_persisting_relationship(self):
        self.experiment1_item.experiment_description = 'Reusable description'
        self.experiment1_item.save()
        self.client.login(username='user1', password='password')

        response = self.client.post(
            reverse('add_project_experiment', args=[self.exp1.id]),
            {
                'experiment_code': 'BB',
                'experiment_description': 'Reusable description, edited',
                'description_source_id': self.experiment1_item.id,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        created = Experiment.objects.get(full_experiment_code='PRA001BB')
        self.assertEqual(created.experiment_description, 'Reusable description, edited')
        event = AuditLog.objects.filter(
            category='experiment', action='create', object_id=str(created.id),
        ).latest('id')
        self.assertEqual(event.changes['description_source_id']['after'], self.experiment1_item.id)
        self.assertEqual(event.changes['description_source_code']['after'], 'PRA001AA')

    def test_add_project_experiment_copies_all_steps_genealogy_and_materials(self):
        self.experiment1_item.experiment_description = 'Reusable process'
        self.experiment1_item.save()
        parent_a = ExperimentStep.objects.create(
            step_name='MX', experiment=self.experiment1_item,
            step_description='Mix A', owner=self.user1,
        )
        parent_b = ExperimentStep.objects.create(
            step_name='PS', experiment=self.experiment1_item,
            step_description='Prepare substrate',
        )
        child = ExperimentStep.objects.create(
            step_name='CA', experiment=self.experiment1_item,
            step_description='Coat', status='Completed', recipe='R-01', notes='Keep dry',
        )
        child.parents.set([parent_a, parent_b])
        StepRawMaterialUsage.objects.create(
            step=child, raw_material=self.raw_material,
            quantity='2.0000', unit='g', notes='Process input',
        )
        Cell.objects.create(step=child, test_order_number='PKG-1', barcode='CELL-1')
        Sample.objects.create(step=child, sample_name='SOURCE-SAMPLE')
        self.client.login(username='user1', password='password')

        response = self.client.post(
            reverse('add_project_experiment', args=[self.exp1.id]),
            {
                'experiment_code': 'BB',
                'experiment_description': 'Reusable process, edited',
                'description_source_id': self.experiment1_item.id,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['copied_step_count'], 3)
        copied_experiment = Experiment.objects.get(full_experiment_code='PRA001BB')
        copied_parent_a = copied_experiment.steps.get(step_name='MX')
        copied_parent_b = copied_experiment.steps.get(step_name='PS')
        copied_child = copied_experiment.steps.get(step_name='CA')
        self.assertEqual(set(copied_child.parents.all()), {copied_parent_a, copied_parent_b})
        self.assertEqual(copied_child.parent, copied_parent_a)
        self.assertEqual(copied_child.status, 'Planned')
        self.assertIsNone(copied_child.completed_on)
        self.assertEqual(copied_child.recipe, 'R-01')
        self.assertEqual(copied_child.notes, 'Keep dry')
        copied_usage = copied_child.raw_material_usages.get()
        self.assertEqual(copied_usage.raw_material, self.raw_material)
        self.assertEqual(copied_usage.quantity, Decimal('2.0000'))
        self.assertEqual(copied_experiment.steps.filter(cells__isnull=False).count(), 0)
        self.assertEqual(copied_experiment.steps.filter(samples__isnull=False).count(), 0)
        event = AuditLog.objects.filter(
            category='experiment', action='create', object_id=str(copied_experiment.id),
        ).latest('id')
        self.assertEqual(event.changes['copied_step_count']['after'], 3)

    def test_add_project_experiment_rejects_inaccessible_copy_source(self):
        hidden_source = Experiment.objects.create(
            experiment_code='AA', project=self.exp2,
            experiment_description='Other group secret',
        )
        self.client.login(username='user1', password='password')

        response = self.client.post(
            reverse('add_project_experiment', args=[self.exp1.id]),
            {
                'experiment_code': 'BB',
                'experiment_description': 'Copied text',
                'description_source_id': hidden_source.id,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], '复制来源不可用或你没有访问权限。')
        self.assertFalse(Experiment.objects.filter(full_experiment_code='PRA001BB').exists())

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
        self.assertContains(response, '.lineage-parent-select2 .lineage-parent-search-icon')
        self.assertContains(response, '.lineage-parent-select2 .select2-selection__clear')
        self.assertContains(response, 'right: 2rem !important;')
        self.assertNotContains(response, '.select2-selection--multiple::after')

    def test_experiment_detail_configures_raw_material_search_first_dropdown(self):
        self.client.login(username="user1", password="password")

        response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "modalElement.find('.raw-material-select')")
        self.assertContains(response, "dropdownCssClass: 'search-first-dropdown raw-material-dropdown'")
        self.assertContains(response, '请输入至少 1 个字符后搜索原材料')
        self.assertContains(response, 'max-height: 220px !important;')
        self.assertContains(response, "$searchField.val('').trigger('input')")

    def test_add_step_with_cells(self):
        self.client.login(username="user1", password="password")
        response = self.client.post(
            reverse('add_step', args=[self.exp1.id, self.experiment1_item.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [
                        {'id': None, 'test_order_number': ' pkg-01 ', 'barcode': ' cell-001 '},
                        {'id': None, 'test_order_number': 'PKG-01', 'barcode': 'CELL-002'},
                    ],
                    'deleted_ids': [],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        step = ExperimentStep.objects.get(full_step="PRA001AA-AA00")
        self.assertEqual(
            list(step.cells.values_list('test_order_number', 'barcode')),
            [('PKG-01', 'CELL-001'), ('PKG-01', 'CELL-002')],
        )

    def test_edit_step_reconciles_cells_and_removed_barcode_can_be_reused(self):
        self.client.login(username="user1", password="password")
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        retained = Cell.objects.create(step=step, test_order_number="PKG-01", barcode="CELL-001")
        removed = Cell.objects.create(step=step, test_order_number="PKG-01", barcode="CELL-002")

        response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [
                        {'id': retained.id, 'test_order_number': 'PKG-02', 'barcode': 'CELL-001A'},
                        {'id': None, 'test_order_number': 'PKG-02', 'barcode': 'CELL-003'},
                    ],
                    'deleted_ids': [removed.id],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(step.cells.values_list('test_order_number', 'barcode')),
            [('PKG-02', 'CELL-001A'), ('PKG-02', 'CELL-003')],
        )
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        rebound = Cell.objects.create(
            step=other_step,
            test_order_number="PKG-03",
            barcode="CELL-002",
        )
        self.assertEqual(rebound.step, other_step)

    def test_edit_step_links_one_cell_to_samples_from_multiple_steps(self):
        source_step_1 = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        source_step_2 = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        target_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        sample_1 = Sample.objects.create(step=source_step_1, sample_number=1, sample_name="PRA001AA-AA00-01")
        sample_2 = Sample.objects.create(step=source_step_2, sample_number=1, sample_name="PRA001AA-BB00-01")
        cell = Cell.objects.create(step=target_step, test_order_number="PKG-01", barcode="CELL-LINKED")

        self.client.login(username="user1", password="password")
        response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, target_step.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [{
                        'id': cell.id,
                        'test_order_number': 'PKG-01',
                        'barcode': 'CELL-LINKED',
                        'sample_ids': [sample_1.id, sample_2.id],
                    }],
                    'deleted_ids': [],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(cell.samples.values_list('id', flat=True)), {sample_1.id, sample_2.id})
        self.assertEqual(
            set(CellSampleLink.objects.filter(cell=cell).values_list('created_by_id', flat=True)),
            {self.user1.id},
        )

    def test_legacy_cell_payload_without_sample_ids_preserves_links(self):
        source_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        target_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        sample = Sample.objects.create(step=source_step, sample_number=1, sample_name="PRA001AA-AA00-01")
        cell = Cell.objects.create(step=target_step, test_order_number="PKG-01", barcode="CELL-LEGACY")
        CellSampleLink.objects.create(cell=cell, sample=sample, created_by=self.user1)

        self.client.login(username="user1", password="password")
        response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, target_step.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [{
                        'id': cell.id,
                        'test_order_number': 'PKG-02',
                        'barcode': 'CELL-LEGACY',
                    }],
                    'deleted_ids': [],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(cell.samples.values_list('id', flat=True)), [sample.id])

    def test_linkable_sample_search_is_team_scoped_and_cursor_paginated(self):
        own_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        for number in range(1, 31):
            Sample.objects.create(
                step=own_step,
                sample_number=number,
                sample_name=f"PRA001AA-AA00-{number:02d}",
            )
        group2_experiment = Experiment.objects.create(experiment_code="AA", project=self.exp2)
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=group2_experiment)
        Sample.objects.create(
            step=other_step,
            sample_number=1,
            sample_name="PRA-OTHER-TEAM",
        )

        self.client.login(username="user1", password="password")
        first = self.client.get(reverse('search_linkable_samples'), {'q': 'PRA'})
        self.assertEqual(first.status_code, 200)
        first_data = first.json()
        self.assertEqual(len(first_data['results']), 25)
        self.assertTrue(first_data['next_cursor'])
        self.assertNotIn('PRA-OTHER-TEAM', {item['name'] for item in first_data['results']})

        second = self.client.get(reverse('search_linkable_samples'), {
            'q': 'PRA',
            'cursor': first_data['next_cursor'],
        })
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.json()['results']), 5)
        self.assertIsNone(second.json()['next_cursor'])

    def test_other_team_sample_cannot_be_linked(self):
        target_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        cell = Cell.objects.create(step=target_step, test_order_number="PKG-01", barcode="CELL-SECURE")
        group2_experiment = Experiment.objects.create(experiment_code="AA", project=self.exp2)
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=group2_experiment)
        foreign_sample = Sample.objects.create(step=other_step, sample_number=1, sample_name="PRB001AA-AA00-01")

        self.client.login(username="user1", password="password")
        response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, target_step.id]),
            {
                'step_name': 'AA',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [{
                        'id': cell.id,
                        'test_order_number': 'PKG-01',
                        'barcode': 'CELL-SECURE',
                        'sample_ids': [foreign_sample.id],
                    }],
                    'deleted_ids': [],
                }),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(cell.samples.exists())

    def test_duplicate_cell_barcode_rolls_back_step_edit(self):
        self.client.login(username="user1", password="password")
        step = ExperimentStep.objects.create(
            step_name="AA",
            experiment=self.experiment1_item,
            step_description="Before",
        )
        existing = Cell.objects.create(step=step, test_order_number="PKG-01", barcode="CELL-001")
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        Cell.objects.create(step=other_step, test_order_number="PKG-02", barcode="DUPLICATE")

        response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            {
                'step_name': 'AA',
                'step_description': 'After',
                'status': 'Planned',
                'cells_payload': json.dumps({
                    'records': [
                        {'id': existing.id, 'test_order_number': 'PKG-01', 'barcode': 'CELL-001'},
                        {'id': None, 'test_order_number': 'PKG-01', 'barcode': 'DUPLICATE'},
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
        cell = Cell.objects.create(step=step, test_order_number="PKG-01", barcode="CELL-001")
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
            test_order_number="PKG-SHARED",
            barcode="OWN-CELL",
        )
        group2_experiment = Experiment.objects.create(experiment_code="AA", project=self.exp2)
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=group2_experiment)
        Cell.objects.create(
            step=other_step,
            test_order_number="PKG-SHARED",
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
        Cell.objects.create(step=step, test_order_number="PKG-01", barcode="CELL-001")
        Sample.sync_for_step(step, 2)
        self.client.login(username="user1", password="password")

        detail_response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))
        self.assertContains(detail_response, '电芯')
        self.assertContains(detail_response, 'PKG-01')
        self.assertContains(detail_response, 'CELL-001')
        self.assertContains(detail_response, '<th>样品</th>', html=True)
        self.assertContains(detail_response, 'data-step-sample-count="2"')
        self.assertContains(detail_response, f'{step.full_step} 样品数量：2')

        genealogy_response = self.client.get(reverse('step_genealogy', args=[step.id]))
        self.assertContains(genealogy_response, '当前步骤电芯')
        self.assertContains(genealogy_response, 'PKG-01')
        self.assertContains(genealogy_response, 'CELL-001')

    def test_edit_step_renders_step_cell_and_sample_tabs(self):
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        Cell.objects.create(step=step, test_order_number="PKG-01", barcode="CELL-001")
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

    def test_step_owner_is_optional_searchable_and_limited_to_project_team(self):
        teammate = User.objects.create_user(
            username='team_member', first_name='Team', last_name='Member', password='password',
        )
        UserProfile.objects.create(user=teammate, research_group=self.group1)
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item)
        self.client.login(username="user1", password="password")

        form_response = self.client.get(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id])
        )
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, 'id="id_owner"')
        self.assertContains(form_response, '负责人')
        self.assertContains(form_response, 'Team Member · team_member')
        self.assertNotContains(form_response, f'value="{self.user2.id}"')

        detail_response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))
        self.assertContains(detail_response, "selector: '#id_owner'")
        self.assertContains(detail_response, 'maximumSelectionLength: 1')
        self.assertContains(detail_response, '请输入至少 1 个字符后搜索用户')

        assign_response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            {'step_name': 'AA', 'status': 'Planned', 'owner': teammate.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(assign_response.status_code, 200)
        self.assertTrue(assign_response.json()['success'])
        step.refresh_from_db()
        self.assertEqual(step.owner, teammate)

        forbidden_response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            {'step_name': 'AA', 'status': 'Planned', 'owner': self.user2.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(forbidden_response.status_code, 200)
        self.assertFalse(forbidden_response.json()['success'])
        self.assertIn('owner', forbidden_response.json()['errors'])
        step.refresh_from_db()
        self.assertEqual(step.owner, teammate)

        clear_response = self.client.post(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            {'step_name': 'AA', 'status': 'Planned', 'owner': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertTrue(clear_response.json()['success'])
        step.refresh_from_db()
        self.assertIsNone(step.owner)

    def test_step_equipment_uses_single_search_first_interaction(self):
        self.client.login(username='user1', password='password')

        form_response = self.client.get(
            reverse('add_step', args=[self.exp1.id, self.experiment1_item.id])
        )
        detail_response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))

        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, 'id="id_tool"')
        self.assertContains(form_response, 'step-equipment-select')
        self.assertContains(detail_response, "selector: '#id_tool'")
        self.assertContains(detail_response, '请输入至少 1 个字符后搜索设备')
        self.assertContains(detail_response, "initializeStepEquipmentSelect('#addStepModal')")
        self.assertContains(detail_response, "initializeStepEquipmentSelect('#editStepModal')")

    def test_edit_step_renders_existing_completed_time(self):
        completed_on = timezone.make_aware(datetime(2026, 8, 6, 14, 35))
        step = ExperimentStep.objects.create(
            step_name="AA",
            experiment=self.experiment1_item,
            status="Completed",
            completed_on=completed_on,
        )
        self.client.login(username="user1", password="password")

        response = self.client.get(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-08-06T14:35"')

    def test_edit_step_raw_material_option_shows_and_searches_code_with_batch(self):
        step = ExperimentStep.objects.create(
            step_name="AA",
            experiment=self.experiment1_item,
        )
        StepRawMaterialUsage.objects.create(
            step=step,
            raw_material=self.raw_material,
            quantity="1.0000",
            unit="g",
        )
        self.client.login(username="user1", password="password")

        response = self.client.get(
            reverse('edit_step', args=[self.exp1.id, self.experiment1_item.id, step.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'{self.raw_material.material_code}-{self.raw_material.batch_number}',
        )

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

        response = self.client.post(
            reverse('delete_step', args=[self.exp1.id, self.experiment1_item.id, parent.id]),
            follow=True,
        )

        self.assertRedirects(
            response,
            f'{reverse("experiment_detail", args=[self.exp1.id])}?expanded_experiment={self.experiment1_item.id}',
        )
        self.assertContains(
            response,
            '该步骤已有下游关联步骤，无法删除。请先移除下游步骤的前置关系。',
        )
        self.assertTrue(ExperimentStep.objects.filter(id=parent.id).exists())
        self.assertTrue(ExperimentStep.objects.filter(id=child.id).exists())

        logout_response = self.client.get(reverse('logout'), follow=True)
        self.assertNotContains(logout_response, '该步骤已有下游关联步骤，无法删除。')

    def test_experiment_detail_renders_accessible_actions_and_delete_counts(self):
        step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment1_item)
        Cell.objects.create(step=step, test_order_number='PKG-1', barcode='CELL-1')
        Sample.objects.create(step=step, sample_name='SAMPLE-1')
        self.client.login(username='user1', password='password')

        response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))

        self.assertContains(response, '<span>新增实验</span>', html=True)
        self.assertContains(response, '<span>新增步骤</span>', html=True)
        self.assertContains(response, f'aria-label="为 {self.experiment1_item.full_experiment_code} 新增步骤"')
        self.assertContains(response, f'aria-label="删除实验 {self.experiment1_item.full_experiment_code}"')
        self.assertContains(response, f'aria-label="编辑步骤 {step.full_step}"')
        self.assertContains(response, f'aria-label="删除步骤 {step.full_step}"')
        self.assertContains(response, f'aria-label="查看步骤 {step.full_step} 的谱系"')
        self.assertContains(response, 'data-step-count="1"')
        self.assertContains(response, 'data-cell-count="1"')
        self.assertContains(response, 'data-sample-count="1"')
        self.assertContains(response, 'id="deleteConfirmModal"')
        self.assertContains(response, 'id="deleteConfirmForm" method="post"')

    def test_experiment_detail_enables_dragging_for_selected_modals(self):
        self.client.login(username='user1', password='password')

        response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))

        self.assertContains(response, 'id="addProjectExperimentModal" tabindex="-1" data-draggable-modal')
        self.assertContains(response, 'id="deleteConfirmModal" tabindex="-1" data-draggable-modal')
        self.assertContains(
            response,
            'id="addStepModal" tabindex="-1" aria-hidden="true" data-draggable-modal',
        )
        self.assertContains(
            response,
            'id="editStepModal" tabindex="-1" aria-hidden="true" data-draggable-modal',
        )
        self.assertContains(response, 'data-modal-drag-handle>', count=4)
        self.assertContains(response, 'js/draggable-modals.js?v=2')

    def test_single_delete_endpoints_reject_get(self):
        step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment1_item)
        self.client.login(username='user1', password='password')

        experiment_response = self.client.get(reverse(
            'delete_project_experiment', args=[self.exp1.id, self.experiment1_item.id],
        ))
        step_response = self.client.get(reverse(
            'delete_step', args=[self.exp1.id, self.experiment1_item.id, step.id],
        ))

        self.assertEqual(experiment_response.status_code, 405)
        self.assertEqual(step_response.status_code, 405)
        self.assertTrue(Experiment.objects.filter(id=self.experiment1_item.id).exists())
        self.assertTrue(ExperimentStep.objects.filter(id=step.id).exists())

    def test_delete_experiment_post_deletes_scoped_object_and_logs(self):
        experiment = Experiment.objects.create(experiment_code='BB', project=self.exp1)
        ExperimentStep.objects.create(step_name='AA', experiment=experiment)
        self.client.login(username='user1', password='password')

        response = self.client.post(
            reverse('delete_project_experiment', args=[self.exp1.id, experiment.id]),
            follow=True,
        )

        self.assertRedirects(response, reverse('experiment_detail', args=[self.exp1.id]))
        self.assertContains(response, f'已删除实验 {experiment.full_experiment_code}。')
        self.assertFalse(Experiment.objects.filter(id=experiment.id).exists())
        event = AuditLog.objects.get(category='experiment', action='delete', object_id=str(experiment.id))
        self.assertEqual(event.request_method, 'POST')

    def test_delete_step_post_deletes_scoped_object_and_reopens_experiment(self):
        step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment1_item)
        self.client.login(username='user1', password='password')

        response = self.client.post(
            reverse('delete_step', args=[self.exp1.id, self.experiment1_item.id, step.id]),
            follow=True,
        )

        detail_url = f'{reverse("experiment_detail", args=[self.exp1.id])}?expanded_experiment={self.experiment1_item.id}'
        self.assertRedirects(response, detail_url)
        self.assertContains(response, f'已删除步骤 {step.full_step}。')
        self.assertFalse(ExperimentStep.objects.filter(id=step.id).exists())
        event = AuditLog.objects.get(category='step', action='delete', object_id=str(step.id))
        self.assertEqual(event.request_method, 'POST')

    def test_single_deletes_reject_cross_team_access(self):
        hidden_experiment = Experiment.objects.create(experiment_code='AA', project=self.exp2)
        hidden_step = ExperimentStep.objects.create(step_name='AA', experiment=hidden_experiment)
        self.client.login(username='user1', password='password')

        experiment_response = self.client.post(reverse(
            'delete_project_experiment', args=[self.exp2.id, hidden_experiment.id],
        ))
        step_response = self.client.post(reverse(
            'delete_step', args=[self.exp2.id, hidden_experiment.id, hidden_step.id],
        ))

        self.assertEqual(experiment_response.status_code, 403)
        self.assertEqual(step_response.status_code, 403)
        self.assertTrue(Experiment.objects.filter(id=hidden_experiment.id).exists())
        self.assertTrue(ExperimentStep.objects.filter(id=hidden_step.id).exists())

    def test_single_deletes_reject_object_hierarchy_mismatch(self):
        other_experiment = Experiment.objects.create(experiment_code='AA', project=self.exp2)
        other_step = ExperimentStep.objects.create(step_name='AA', experiment=other_experiment)
        local_step = ExperimentStep.objects.create(step_name='AA', experiment=self.experiment1_item)
        self.client.login(username='user1', password='password')

        experiment_response = self.client.post(reverse(
            'delete_project_experiment', args=[self.exp1.id, other_experiment.id],
        ))
        step_response = self.client.post(reverse(
            'delete_step', args=[self.exp1.id, self.experiment1_item.id, other_step.id],
        ))
        wrong_experiment_response = self.client.post(reverse(
            'delete_step', args=[self.exp1.id, other_experiment.id, local_step.id],
        ))

        self.assertEqual(experiment_response.status_code, 404)
        self.assertEqual(step_response.status_code, 404)
        self.assertEqual(wrong_experiment_response.status_code, 404)
        self.assertTrue(Experiment.objects.filter(id=other_experiment.id).exists())
        self.assertTrue(ExperimentStep.objects.filter(id=other_step.id).exists())
        self.assertTrue(ExperimentStep.objects.filter(id=local_step.id).exists())

    def test_single_delete_post_requires_csrf_token(self):
        experiment = Experiment.objects.create(experiment_code='BB', project=self.exp1)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='user1', password='password')

        response = csrf_client.post(reverse(
            'delete_project_experiment', args=[self.exp1.id, experiment.id],
        ))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Experiment.objects.filter(id=experiment.id).exists())

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
        self.assertEqual(response.json()['completed_date'], timezone.localdate().isoformat())
        
        step.refresh_from_db()
        self.assertEqual(step.status, 'Completed')
        self.assertIsNotNone(step.completed_on)

    def test_experiment_detail_displays_completion_date_only_when_present(self):
        completed_on = timezone.make_aware(datetime(2026, 8, 6, 14, 35))
        completed_step = ExperimentStep.objects.create(
            step_name="AA", experiment=self.experiment1_item,
            status="Completed", completed_on=completed_on,
        )
        planned_step = ExperimentStep.objects.create(
            step_name="BB", experiment=self.experiment1_item,
            status="Planned", completed_on=completed_on,
        )
        self.client.login(username="user1", password="password")

        response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))

        self.assertContains(response, "完成日期")
        self.assertContains(
            response,
            f'<span class="step-completed-date" data-step-id="{completed_step.id}">2026-08-06</span>',
            html=True,
        )
        self.assertContains(
            response,
            f'<span class="step-completed-date" data-step-id="{planned_step.id}"></span>',
            html=True,
        )

    def test_copy_steps(self):
        self.client.login(username="user1", password="password")
        
        # Create source step
        step1 = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment1_item, step_description="Source")
        StepRawMaterialUsage.objects.create(
            step=step1,
            raw_material=self.raw_material,
            quantity="3.0000",
            unit="g"
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
        self.assertEqual(copied_usage.unit, "g")

    def test_raw_material_views_and_search(self):
        self.client.login(username="user1", password="password")

        list_response = self.client.get(reverse('raw_material_list'), {'search': 'Vendor A'})
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "RM001")
        self.assertContains(list_response, "Test Powder")

        detail_response = self.client.get(reverse('raw_material_detail', args=[self.raw_material.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "RM001-061926")
        self.assertContains(detail_response, "1000 g")

        add_response = self.client.post(reverse('add_raw_material'), {
            'material_code': 'RM002',
            'batch_number': 'LOT-002',
            'received_date': '',
            'material_type': 'Liquid',
            'material_name': '',
            'total_quantity': '2000',
            'total_unit': 'mL',
            'owner': self.user1.id,
            'supplier': 'Vendor B',
            'location': 'Cabinet 2',
            'is_active': 'on'
        })
        self.assertEqual(add_response.status_code, 302)
        self.assertTrue(RawMaterial.objects.filter(
            material_code="RM002", batch_number="LOT-002", received_date__isnull=True,
            material_name__isnull=True, total_quantity="2000", total_unit="mL",
        ).exists())

        edit_response = self.client.post(reverse('edit_raw_material', args=[self.raw_material.id]), {
            'material_code': 'RM001',
            'batch_number': 'LOT-001-REV',
            'received_date': '2026-06-21',
            'material_type': 'Powder',
            'material_name': '',
            'total_quantity': '750.5',
            'total_unit': 'g',
            'owner': self.user1.id,
            'supplier': 'Vendor A',
            'location': 'Shelf 2',
            'is_active': 'on'
        })
        self.assertEqual(edit_response.status_code, 302)
        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.batch_number, "LOT-001-REV")
        self.assertIsNone(self.raw_material.material_name)
        self.assertEqual(self.raw_material.total_quantity, Decimal("750.5000"))
        self.assertEqual(self.raw_material.total_unit, "g")

    def test_management_dashboard_requires_staff(self):
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse('management_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url.split('?')[0], reverse('index'))

    def test_team_owner_can_manage_only_own_team_project_access(self):
        self.user1.profile.is_team_owner = True
        self.user1.profile.save(update_fields=['is_team_owner'])
        self.client.login(username="user1", password="password")

        dashboard = self.client.get(reverse('management_dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertTrue(dashboard.context['access_only'])
        self.assertContains(dashboard, '项目授权')
        self.assertContains(dashboard, self.exp1.exp_name)
        self.assertNotContains(dashboard, self.exp2.exp_name)
        self.assertNotContains(dashboard, 'data-bs-target="#teams"')

        response = self.client.post(
            reverse('grant_project_access', args=[self.exp1.id]),
            {'users': [self.user2.id]},
        )
        self.assertRedirects(response, reverse('management_dashboard') + '#permissions')
        self.assertTrue(self.exp1.authorized_users.filter(id=self.user2.id).exists())

        denied = self.client.post(
            reverse('grant_project_access', args=[self.exp2.id]),
            {'users': [self.user1.id]},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(self.exp2.authorized_users.filter(id=self.user1.id).exists())

    def test_management_team_list_shows_responsible_person(self):
        self.user1.profile.is_team_owner = True
        self.user1.profile.save(update_fields=['is_team_owner'])
        self.client.login(username="staff", password="password")

        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<th>负责人</th>', html=True)
        self.assertContains(response, self.user1.username)
        self.assertNotContains(response, 'Team Owner')

    def test_explicit_project_grant_adds_cross_team_access(self):
        self.exp1.authorized_users.add(self.user2)
        self.client.login(username="user2", password="password")

        dashboard = self.client.get(reverse('index'))
        self.assertContains(dashboard, self.exp1.exp_name)
        self.assertContains(dashboard, self.exp2.exp_name)
        detail = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))
        self.assertEqual(detail.status_code, 200)

    def test_superuser_can_grant_access_to_any_project(self):
        superuser = User.objects.create_superuser(
            username='root-manager', password='password', email='root@example.com',
        )
        self.client.login(username=superuser.username, password='password')

        response = self.client.post(
            reverse('grant_project_access', args=[self.exp2.id]),
            {'users': [self.user1.id]},
        )
        self.assertRedirects(response, reverse('management_dashboard') + '#permissions')
        self.assertTrue(self.exp2.authorized_users.filter(id=self.user1.id).exists())

    def test_staff_without_team_owner_role_cannot_grant_project_access(self):
        self.client.login(username="staff", password="password")
        response = self.client.post(
            reverse('grant_project_access', args=[self.exp1.id]),
            {'users': [self.user2.id]},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.exp1.authorized_users.filter(id=self.user2.id).exists())

    def test_management_cells_tab_lists_and_filters_cells_across_teams(self):
        own_step = ExperimentStep.objects.create(
            step_name="AA",
            experiment=self.experiment1_item,
        )
        own_cell = Cell.objects.create(
            step=own_step,
            test_order_number="PKG-MANAGEMENT-A",
            barcode="CELL-MANAGEMENT-A",
        )
        other_experiment = Experiment.objects.create(experiment_code="AA", project=self.exp2)
        other_step = ExperimentStep.objects.create(step_name="AA", experiment=other_experiment)
        Cell.objects.create(
            step=other_step,
            test_order_number="PKG-MANAGEMENT-B",
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

    def test_management_crud_for_raw_material_types(self):
        self.client.login(username="staff", password="password")

        dashboard = self.client.get(reverse('management_dashboard'))
        self.assertContains(dashboard, 'data-bs-target="#material-types"')
        self.assertContains(dashboard, 'Powder')

        response = self.client.post(reverse('add_raw_material_type'), {
            'name': 'Foil',
            'description': 'Metal sheet',
            'is_active': 'on',
        })
        self.assertRedirects(response, reverse('management_dashboard') + '#material-types')
        material_type = RawMaterialType.objects.get(name='Foil')

        RawMaterial.objects.create(
            material_code='RM-FOIL',
            batch_number='FOIL-001',
            received_date='2026-07-01',
            material_type='Foil',
            owner=self.user1,
        )
        self.client.post(reverse('edit_raw_material_type', args=[material_type.id]), {
            'name': 'Metal Foil',
            'description': 'Renamed option',
            'is_active': 'on',
        })
        material_type.refresh_from_db()
        self.assertEqual(material_type.name, 'Metal Foil')
        self.assertTrue(RawMaterial.objects.filter(material_type='Metal Foil').exists())

        self.client.post(reverse('delete_raw_material_type', args=[material_type.id]))
        self.assertTrue(RawMaterialType.objects.filter(id=material_type.id).exists())

        unused_type = RawMaterialType.objects.create(name='Unused')
        self.client.post(reverse('delete_raw_material_type', args=[unused_type.id]))
        self.assertFalse(RawMaterialType.objects.filter(id=unused_type.id).exists())

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

    def test_insights_requires_login(self):
        response = self.client.get(reverse('insights'))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('insights')}")

    def test_logged_in_user_can_open_insights_workspace(self):
        self.client.login(username="user1", password="password")

        response = self.client.get(reverse('insights'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'experiment_flow/insights.html')
        self.assertContains(response, '数据洞察')
        self.assertContains(response, 'data-query-mode="mock"')
        self.assertContains(response, 'PCA001 首圈克容量')
        self.assertContains(response, 'GM001 × FS02 循环衰减')
        self.assertContains(response, '正极配方横向对比')
        self.assertContains(response, '模拟电化学数据')
        self.assertContains(response, '模拟 SQL · 未来分析数据结构')

    def test_navigation_links_to_insights_workspace(self):
        self.client.login(username="user1", password="password")

        sidebar_response = self.client.get(reverse('index'))
        no_sidebar_response = self.client.get(reverse('equipment_list'))

        self.assertContains(sidebar_response, reverse('insights'))
        self.assertContains(no_sidebar_response, reverse('insights'))
