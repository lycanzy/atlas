from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from experiment_flow.models import (
    ResearchGroup, UserProfile, Project, Exp, ExpFlow, ExpStep, Equipment
)

class ModelTests(TestCase):
    def setUp(self):
        # Create basic setup
        self.group = ResearchGroup.objects.create(group_name="Test Group")
        self.user = User.objects.create_user(username="testuser", password="password")
        self.profile = UserProfile.objects.create(user=self.user, research_group=self.group)
        self.project = Project.objects.create(
            project_name="Test Project",
            project_code="TPR",
            group=self.group
        )
        self.equipment = Equipment.objects.create(
            equipment_name="Test Equipment",
            equipment_id="EQ001"
        )

    def test_project_code_validation(self):
        """Test that project code must be 3 uppercase letters"""
        project = Project(
            project_name="Bad Code",
            project_code="AB", # Too short
            group=self.group
        )
        with self.assertRaises(ValidationError):
            project.full_clean()

        project.project_code = "123" # Not alpha
        with self.assertRaises(ValidationError):
            project.full_clean()

        project.project_code = "abc" # Lowercase (should be auto-converted or fail depending on implementation, 
                                     # but model clean() converts it)
        project.full_clean()
        project.save()
        self.assertEqual(project.project_code, "ABC")

    def test_team_code_validation(self):
        """Test that team code must be 3 uppercase letters when provided"""
        group = ResearchGroup(group_name="Bad Team", team_code="AB")
        with self.assertRaises(ValidationError):
            group.full_clean()

        group.team_code = "123"
        with self.assertRaises(ValidationError):
            group.full_clean()

        group.team_code = "abc"
        group.full_clean()
        group.save()
        self.assertEqual(group.team_code, "ABC")

    def test_generate_experiment_name(self):
        """Test experiment name generation"""
        # First experiment
        exp1 = Exp.objects.create(
            exp_name=self.project.generate_experiment_name(),
            project=self.project,
            owner=self.user
        )
        self.assertEqual(exp1.exp_name, "TPR001")

        # Second experiment
        exp2 = Exp.objects.create(
            exp_name=self.project.generate_experiment_name(),
            project=self.project,
            owner=self.user
        )
        self.assertEqual(exp2.exp_name, "TPR002")

    def test_flow_creation_and_signals(self):
        """Test flow creation, validation, and full_flow signal"""
        exp = Exp.objects.create(
            exp_name="TPR001",
            project=self.project,
            owner=self.user
        )
        
        flow = ExpFlow(
            flow_name="aa", # Lowercase, should be converted
            exp=exp
        )
        flow.full_clean()
        flow.save()
        
        self.assertEqual(flow.flow_name, "AA")
        self.assertEqual(flow.full_flow, "TPR001AA")
        self.assertTrue(flow.barcode.startswith("F"))

        # Test invalid flow name
        flow_bad = ExpFlow(flow_name="A", exp=exp)
        with self.assertRaises(ValidationError):
            flow_bad.full_clean()

    def test_step_creation_and_signals(self):
        """Test step creation, numbering, and full_step signal"""
        exp = Exp.objects.create(
            exp_name="TPR001",
            project=self.project,
            owner=self.user
        )
        flow = ExpFlow.objects.create(flow_name="AA", exp=exp)
        
        # First step
        step1 = ExpStep(
            step_name="ST",
            flow=flow,
            step_description="Step 1"
        )
        step1.save()
        
        self.assertEqual(step1.step_number, "00")
        self.assertEqual(step1.full_step, "TPR001AA-ST00")
        self.assertTrue(step1.barcode.startswith("S"))
        
        # Second step with same name
        step2 = ExpStep(
            step_name="ST",
            flow=flow,
            step_description="Step 2"
        )
        step2.save()
        self.assertEqual(step2.step_number, "01")
        self.assertEqual(step2.full_step, "TPR001AA-ST01")

        # Step with different name
        step3 = ExpStep(
            step_name="XY",
            flow=flow
        )
        step3.save()
        self.assertEqual(step3.step_number, "00")
        self.assertEqual(step3.full_step, "TPR001AA-XY00")

    def test_step_num_property(self):
        """Test the step_num property which counts previous steps in the flow"""
        exp = Exp.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        flow = ExpFlow.objects.create(flow_name="AA", exp=exp)
        
        step1 = ExpStep.objects.create(step_name="AA", flow=flow)
        step2 = ExpStep.objects.create(step_name="BB", flow=flow, parent=step1)
        step3 = ExpStep.objects.create(step_name="CC", flow=flow, parent=step2)
        
        self.assertEqual(step1.step_num, "00")
        self.assertEqual(step2.step_num, "01")
        self.assertEqual(step3.step_num, "02")
        
        # Test with parent in different flow (should break chain)
        flow2 = ExpFlow.objects.create(flow_name="BB", exp=exp)
        step_other = ExpStep.objects.create(step_name="ZZ", flow=flow2)
        
        step4 = ExpStep.objects.create(step_name="DD", flow=flow, parent=step_other)
        self.assertEqual(step4.step_num, "00")

    def test_update_flow_identifiers_signal(self):
        """Test that changing experiment name updates flow and step identifiers"""
        exp = Exp.objects.create(exp_name="OLD001", project=self.project, owner=self.user)
        flow = ExpFlow.objects.create(flow_name="AA", exp=exp)
        step = ExpStep.objects.create(step_name="BB", flow=flow)
        
        self.assertEqual(flow.full_flow, "OLD001AA")
        self.assertEqual(step.full_step, "OLD001AA-BB00")
        
        # Update experiment name
        exp.exp_name = "NEW001"
        exp.save()
        
        # Refresh from db
        flow.refresh_from_db()
        step.refresh_from_db()
        
        self.assertEqual(flow.full_flow, "NEW001AA")
        self.assertEqual(step.full_step, "NEW001AA-BB00")
