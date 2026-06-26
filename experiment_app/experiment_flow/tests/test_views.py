from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from experiment_flow.models import (
    ResearchGroup, UserProfile, Project, Exp, ExpFlow, ExpStep, StepNameTemplate
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
        self.project1 = Project.objects.create(project_name="P1", project_code="PRA", group=self.group1)
        self.exp1 = Exp.objects.create(exp_name="PRA001", project=self.project1, owner=self.user1)
        self.flow1 = ExpFlow.objects.create(flow_name="AA", exp=self.exp1)
        
        # Setup data for Group 2
        self.project2 = Project.objects.create(project_name="P2", project_code="PRB", group=self.group2)
        self.exp2 = Exp.objects.create(exp_name="PRB001", project=self.project2, owner=self.user2)

        # Setup templates
        StepNameTemplate.objects.create(step_code="AA", step_label="Step A")

    def test_index_view_permissions(self):
        # User 1 should see Exp 1 but not Exp 2
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRA001")
        self.assertNotContains(response, "PRB001")
        
        # User 2 should see Exp 2 but not Exp 1
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
        # User 1 accessing Exp 1 -> OK
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse('experiment_detail', args=[self.exp1.id]))
        self.assertEqual(response.status_code, 200)
        
        # User 1 accessing Exp 2 -> Redirect/Error
        response = self.client.get(reverse('experiment_detail', args=[self.exp2.id]))
        self.assertEqual(response.status_code, 302) # Redirects to index
        
        # Staff accessing Exp 2 -> OK
        self.client.login(username="staff", password="password")
        response = self.client.get(reverse('experiment_detail', args=[self.exp2.id]))
        self.assertEqual(response.status_code, 200)

    def test_add_experiment(self):
        self.client.login(username="user1", password="password")
        
        # Post valid data
        response = self.client.post(reverse('add_experiment'), {
            'team': self.group1.id,
            'exp_description': 'New Exp'
        })
        self.assertEqual(response.status_code, 302) # Redirects to index
        
        # Check created
        self.assertTrue(Exp.objects.filter(exp_name="PRA002").exists())
        
        # Try to add to team 2 (not in group)
        response = self.client.post(reverse('add_experiment'), {
            'team': self.group2.id,
            'exp_description': 'Hacked Exp'
        })
        # Should fail (likely 404 or validation error caught in view)
        # The view catches ResearchGroup.DoesNotExist if filtered by group
        self.assertEqual(response.status_code, 200) # Renders form with error
        self.assertContains(response, "Selected team not found")

    def test_add_flow(self):
        self.client.login(username="user1", password="password")
        
        # Add flow to Exp 1
        response = self.client.post(reverse('add_flow', args=[self.exp1.id]), {
            'flow_name': 'BB'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ExpFlow.objects.filter(full_flow="PRA001BB").exists())
        
        # Try to add flow to Exp 2
        response = self.client.post(reverse('add_flow', args=[self.exp2.id]), {
            'flow_name': 'BB'
        })
        self.assertEqual(response.status_code, 302) # Redirects to index due to permission
        self.assertFalse(ExpFlow.objects.filter(full_flow="PRB001BB").exists())

    def test_add_step(self):
        self.client.login(username="user1", password="password")
        
        # Add step to Flow 1
        response = self.client.post(reverse('add_step', args=[self.exp1.id, self.flow1.id]), {
            'step_name': 'AA',
            'step_description': 'Test Step',
            'status': 'Planned'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ExpStep.objects.filter(full_step="PRA001AA-AA00").exists())

    def test_ajax_update_status(self):
        self.client.login(username="user1", password="password")
        step = ExpStep.objects.create(step_name="AA", flow=self.flow1)
        
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
        step1 = ExpStep.objects.create(step_name="AA", flow=self.flow1, step_description="Source")
        
        # Create target flow
        flow2 = ExpFlow.objects.create(flow_name="BB", exp=self.exp1)
        
        url = reverse('copy_steps', args=[self.exp1.id])
        data = {
            'step_ids': [step1.id],
            'target_flow_name': flow2.full_flow
        }
        
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
        
        # Verify copy
        self.assertTrue(ExpStep.objects.filter(flow=flow2, step_name="AA", step_description="Source").exists())
