from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date
from experiment_flow.models import (
    ResearchGroup, UserProfile, ProjectCategory, Project, Experiment, ExperimentStep, StepNameTemplate,
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
        self.flow1 = Experiment.objects.create(flow_name="AA", exp=self.exp1)
        
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
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))
        self.assertEqual(response.status_code, 200)
        
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

    def test_add_flow(self):
        self.client.login(username="user1", password="password")
        
        # Add flow to Project 1
        response = self.client.post(reverse('add_flow', args=[self.exp1.id]), {
            'flow_name': 'BB'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Experiment.objects.filter(full_flow="PRA001BB").exists())
        
        # Try to add flow to Project 2
        response = self.client.post(reverse('add_flow', args=[self.exp2.id]), {
            'flow_name': 'BB'
        })
        self.assertEqual(response.status_code, 302) # Redirects to index due to permission
        self.assertFalse(Experiment.objects.filter(full_flow="PRB001BB").exists())

    def test_add_step(self):
        self.client.login(username="user1", password="password")
        
        # Add step to Flow 1
        response = self.client.post(reverse('add_step', args=[self.exp1.id, self.flow1.id]), {
            'step_name': 'AA',
            'step_description': 'Test Step',
            'status': 'Planned',
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

    def test_ajax_update_status(self):
        self.client.login(username="user1", password="password")
        step = ExperimentStep.objects.create(step_name="AA", flow=self.flow1)
        
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
        step1 = ExperimentStep.objects.create(step_name="AA", flow=self.flow1, step_description="Source")
        StepRawMaterialUsage.objects.create(
            step=step1,
            raw_material=self.raw_material,
            quantity="3.0000",
            unit="ml"
        )
        
        # Create target flow
        flow2 = Experiment.objects.create(flow_name="BB", exp=self.exp1)
        
        url = reverse('copy_steps', args=[self.exp1.id])
        data = {
            'step_ids': [step1.id],
            'target_flow_name': flow2.full_flow
        }
        
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
        
        # Verify copy
        copied_step = ExperimentStep.objects.get(flow=flow2, step_name="AA", step_description="Source")
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

    def test_copy_step_preserves_external_parent(self):
        self.client.login(username="user1", password="password")

        parent = ExperimentStep.objects.create(step_name="MX", flow=self.flow1)
        child = ExperimentStep.objects.create(step_name="CA", flow=self.flow1, parent=parent)
        flow2 = Experiment.objects.create(flow_name="BB", exp=self.exp1)

        response = self.client.post(
            reverse('copy_steps', args=[self.exp1.id]),
            json.dumps({
                'step_ids': [child.id],
                'target_flow_name': flow2.full_flow
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)

        copied_child = ExperimentStep.objects.get(flow=flow2, step_name="CA")
        self.assertEqual(copied_child.parent, parent)

    def test_copy_steps_remaps_parent_when_parent_is_copied(self):
        self.client.login(username="user1", password="password")

        parent = ExperimentStep.objects.create(step_name="MX", flow=self.flow1)
        child = ExperimentStep.objects.create(step_name="CA", flow=self.flow1, parent=parent)
        flow2 = Experiment.objects.create(flow_name="BB", exp=self.exp1)

        response = self.client.post(
            reverse('copy_steps', args=[self.exp1.id]),
            json.dumps({
                'step_ids': [parent.id, child.id],
                'target_flow_name': flow2.full_flow
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)

        copied_parent = ExperimentStep.objects.get(flow=flow2, step_name="MX")
        copied_child = ExperimentStep.objects.get(flow=flow2, step_name="CA")
        self.assertEqual(copied_child.parent, copied_parent)

    def test_step_genealogy_view_shows_lineage_descendants_and_materials(self):
        self.client.login(username="user1", password="password")

        root = ExperimentStep.objects.create(step_name="AA", flow=self.flow1, step_description="Root step")
        current = ExperimentStep.objects.create(step_name="BB", flow=self.flow1, parent=root, recipe="R1")
        child = ExperimentStep.objects.create(step_name="CC", flow=self.flow1, parent=current)
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

    def test_step_genealogy_view_respects_group_access(self):
        self.client.login(username="user1", password="password")
        flow2 = Experiment.objects.create(flow_name="AA", exp=self.exp2)
        other_step = ExperimentStep.objects.create(step_name="AA", flow=flow2)

        response = self.client.get(reverse('step_genealogy', args=[other_step.id]))

        self.assertEqual(response.status_code, 302)
