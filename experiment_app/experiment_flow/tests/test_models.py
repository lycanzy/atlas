from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import date
from experiment_flow.models import (
    ResearchGroup, UserProfile, ProjectCategory, Project, Experiment, ExperimentStep, Equipment,
    RawMaterial, StepRawMaterialUsage
)

class ModelTests(TestCase):
    def setUp(self):
        # Create basic setup
        self.group = ResearchGroup.objects.create(group_name="Test Group")
        self.user = User.objects.create_user(username="testuser", password="password")
        self.profile = UserProfile.objects.create(user=self.user, research_group=self.group)
        self.project = ProjectCategory.objects.create(
            project_name="Test ProjectCategory",
            project_code="TPR",
            group=self.group
        )
        self.equipment = Equipment.objects.create(
            equipment_name="Test Equipment",
            equipment_id="EQ001"
        )

    def test_project_code_validation(self):
        """Test that project code must be 3 uppercase letters"""
        project = ProjectCategory(
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
        exp1 = Project.objects.create(
            exp_name=self.project.generate_experiment_name(),
            project=self.project,
            owner=self.user
        )
        self.assertEqual(exp1.exp_name, "TPR001")

        # Second experiment
        exp2 = Project.objects.create(
            exp_name=self.project.generate_experiment_name(),
            project=self.project,
            owner=self.user
        )
        self.assertEqual(exp2.exp_name, "TPR002")

    def test_flow_creation_and_signals(self):
        """Test flow creation, validation, and full_flow signal"""
        exp = Project.objects.create(
            exp_name="TPR001",
            project=self.project,
            owner=self.user
        )
        
        flow = Experiment(
            flow_name="aa", # Lowercase, should be converted
            exp=exp
        )
        flow.full_clean()
        flow.save()
        
        self.assertEqual(flow.flow_name, "AA")
        self.assertEqual(flow.full_flow, "TPR001AA")
        self.assertFalse(hasattr(flow, "barcode"))

        # Test invalid flow name
        flow_bad = Experiment(flow_name="A", exp=exp)
        with self.assertRaises(ValidationError):
            flow_bad.full_clean()

    def test_step_creation_and_signals(self):
        """Test step creation, numbering, and full_step signal"""
        exp = Project.objects.create(
            exp_name="TPR001",
            project=self.project,
            owner=self.user
        )
        flow = Experiment.objects.create(flow_name="AA", exp=exp)
        
        # First step
        step1 = ExperimentStep(
            step_name="ST",
            flow=flow,
            step_description="Step 1"
        )
        step1.save()
        
        self.assertEqual(step1.step_number, "00")
        self.assertEqual(step1.full_step, "TPR001AA-ST00")
        self.assertFalse(hasattr(step1, "barcode"))
        
        # Second step with same name
        step2 = ExperimentStep(
            step_name="ST",
            flow=flow,
            step_description="Step 2"
        )
        step2.save()
        self.assertEqual(step2.step_number, "01")
        self.assertEqual(step2.full_step, "TPR001AA-ST01")

        # Step with different name
        step3 = ExperimentStep(
            step_name="XY",
            flow=flow
        )
        step3.save()
        self.assertEqual(step3.step_number, "00")
        self.assertEqual(step3.full_step, "TPR001AA-XY00")

    def test_step_num_property(self):
        """Test the step_num property which counts previous steps in the flow"""
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        flow = Experiment.objects.create(flow_name="AA", exp=exp)
        
        step1 = ExperimentStep.objects.create(step_name="AA", flow=flow)
        step2 = ExperimentStep.objects.create(step_name="BB", flow=flow, parent=step1)
        step3 = ExperimentStep.objects.create(step_name="CC", flow=flow, parent=step2)
        
        self.assertEqual(step1.step_num, "00")
        self.assertEqual(step2.step_num, "01")
        self.assertEqual(step3.step_num, "02")
        
        # Test with parent in different flow (should break chain)
        flow2 = Experiment.objects.create(flow_name="BB", exp=exp)
        step_other = ExperimentStep.objects.create(step_name="ZZ", flow=flow2)
        
        step4 = ExperimentStep.objects.create(step_name="DD", flow=flow, parent=step_other)
        self.assertEqual(step4.step_num, "00")

    def test_step_parent_cycle_is_rejected(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        flow = Experiment.objects.create(flow_name="AA", exp=exp)

        step1 = ExperimentStep.objects.create(step_name="AA", flow=flow)
        step2 = ExperimentStep.objects.create(step_name="BB", flow=flow, parent=step1)
        step3 = ExperimentStep.objects.create(step_name="CC", flow=flow, parent=step2)

        step1.parent = step3
        with self.assertRaises(ValidationError):
            step1.save()

    def test_update_flow_identifiers_signal(self):
        """Test that changing experiment name updates flow and step identifiers"""
        exp = Project.objects.create(exp_name="OLD001", project=self.project, owner=self.user)
        flow = Experiment.objects.create(flow_name="AA", exp=exp)
        step = ExperimentStep.objects.create(step_name="BB", flow=flow)
        
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

    def test_raw_material_creation_and_unique_batch(self):
        material = RawMaterial.objects.create(
            material_code="rm001",
            received_date=date(2026, 6, 19),
            material_type="Powder",
            owner=self.user
        )

        self.assertEqual(material.material_code, "RM001")
        self.assertEqual(material.batch_number, "RM001-061926")
        self.assertIsNone(material.material_name)
        self.assertEqual(material.owner, self.user)

        duplicate = RawMaterial(
            material_code="RM001",
            received_date=date(2026, 6, 19),
            owner=self.user
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_step_raw_material_usage_unique_per_step(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        flow = Experiment.objects.create(flow_name="AA", exp=exp)
        step = ExperimentStep.objects.create(step_name="AA", flow=flow)
        material = RawMaterial.objects.create(
            material_code="RM002",
            received_date=date(2026, 6, 20),
            material_name="Binder",
            owner=self.user
        )

        usage = StepRawMaterialUsage.objects.create(
            step=step,
            raw_material=material,
            quantity="1.5000",
            unit="g"
        )

        self.assertEqual(usage.raw_material, material)
        self.assertEqual(usage.unit, "g")

        duplicate = StepRawMaterialUsage(step=step, raw_material=material, quantity="2.0000", unit="g")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
