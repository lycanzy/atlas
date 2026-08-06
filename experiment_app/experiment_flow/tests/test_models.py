from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal
from experiment_flow.models import (
    Cell, ResearchGroup, UserProfile, ProjectCategory, Project, Experiment, ExperimentStep, ExperimentStepLink, Sample, Equipment,
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
        """Test project_experiment creation, validation, and full_experiment_code signal"""
        exp = Project.objects.create(
            exp_name="TPR001",
            project=self.project,
            owner=self.user
        )
        
        project_experiment = Experiment(
            experiment_code="aa", # Lowercase, should be converted
            project=exp
        )
        project_experiment.full_clean()
        project_experiment.save()
        
        self.assertEqual(project_experiment.experiment_code, "AA")
        self.assertEqual(project_experiment.full_experiment_code, "TPR001AA")
        self.assertFalse(hasattr(project_experiment, "barcode"))

        # Test invalid project_experiment name
        flow_bad = Experiment(experiment_code="A", project=exp)
        with self.assertRaises(ValidationError):
            flow_bad.full_clean()

    def test_step_creation_and_signals(self):
        """Test step creation, numbering, and full_step signal"""
        exp = Project.objects.create(
            exp_name="TPR001",
            project=self.project,
            owner=self.user
        )
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        
        # First step
        step1 = ExperimentStep(
            step_name="ST",
            experiment=project_experiment,
            step_description="Step 1"
        )
        step1.save()
        
        self.assertEqual(step1.step_number, "00")
        self.assertEqual(step1.full_step, "TPR001AA-ST00")
        self.assertFalse(hasattr(step1, "barcode"))
        
        # Second step with same name
        step2 = ExperimentStep(
            step_name="ST",
            experiment=project_experiment,
            step_description="Step 2"
        )
        step2.save()
        self.assertEqual(step2.step_number, "01")
        self.assertEqual(step2.full_step, "TPR001AA-ST01")

        # Step with different name
        step3 = ExperimentStep(
            step_name="XY",
            experiment=project_experiment
        )
        step3.save()
        self.assertEqual(step3.step_number, "00")
        self.assertEqual(step3.full_step, "TPR001AA-XY00")

    def test_samples_are_generated_with_step_based_numbers(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        step = ExperimentStep.objects.create(step_name="MX", experiment=project_experiment)

        generated_count = Sample.sync_for_step(step, 200)

        self.assertEqual(generated_count, 200)
        self.assertEqual(step.samples.get(sample_number=1).sample_name, "TPR001AA-MX00-01")
        self.assertEqual(step.samples.get(sample_number=200).sample_name, "TPR001AA-MX00-200")

    def test_sample_sync_only_adds_and_never_duplicates(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        step = ExperimentStep.objects.create(step_name="MX", experiment=project_experiment)

        Sample.sync_for_step(step, 2)
        Sample.sync_for_step(step, 2)
        Sample.sync_for_step(step, 3)

        self.assertEqual(step.samples.count(), 3)
        self.assertEqual(
            list(step.samples.values_list('sample_number', flat=True)),
            [1, 2, 3],
        )

    def test_cell_normalizes_identifiers_and_allows_shared_package(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        first_step = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)
        second_step = ExperimentStep.objects.create(step_name="BB", experiment=project_experiment)

        first_cell = Cell.objects.create(
            step=first_step,
            package_number=" pkg-01 ",
            barcode=" cell-001 ",
        )
        second_cell = Cell.objects.create(
            step=second_step,
            package_number="pkg-01",
            barcode="cell-002",
        )

        self.assertEqual(first_cell.package_number, "PKG-01")
        self.assertEqual(first_cell.barcode, "CELL-001")
        self.assertEqual(second_cell.package_number, "PKG-01")
        self.assertEqual(first_cell.step, first_step)
        self.assertEqual(second_cell.step, second_step)

    def test_cell_barcode_is_globally_unique(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        first_step = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)
        second_step = ExperimentStep.objects.create(step_name="BB", experiment=project_experiment)
        Cell.objects.create(step=first_step, package_number="PKG-01", barcode="CELL-001")

        with self.assertRaises(ValidationError):
            Cell.objects.create(
                step=second_step,
                package_number="PKG-02",
                barcode=" cell-001 ",
            )

    def test_step_num_property(self):
        """Test the step_num property which counts previous steps in the project_experiment"""
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        
        step1 = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)
        step2 = ExperimentStep.objects.create(step_name="BB", experiment=project_experiment, parent=step1)
        step3 = ExperimentStep.objects.create(step_name="CC", experiment=project_experiment, parent=step2)
        
        self.assertEqual(step1.step_num, "00")
        self.assertEqual(step2.step_num, "01")
        self.assertEqual(step3.step_num, "02")
        
        # Test with parent in different project_experiment (should break chain)
        experiment2 = Experiment.objects.create(experiment_code="BB", project=exp)
        step_other = ExperimentStep.objects.create(step_name="ZZ", experiment=experiment2)
        
        step4 = ExperimentStep.objects.create(step_name="DD", experiment=project_experiment, parent=step_other)
        self.assertEqual(step4.step_num, "00")

    def test_step_parent_cycle_is_rejected(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)

        step1 = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)
        step2 = ExperimentStep.objects.create(step_name="BB", experiment=project_experiment, parent=step1)
        step3 = ExperimentStep.objects.create(step_name="CC", experiment=project_experiment, parent=step2)

        step1.parent = step3
        with self.assertRaises(ValidationError):
            step1.save()

    def test_step_can_have_multiple_parent_links(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)

        slurry_a = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)
        slurry_b = ExperimentStep.objects.create(step_name="BB", experiment=project_experiment)
        final_mix = ExperimentStep.objects.create(step_name="CC", experiment=project_experiment)

        final_mix.parents.set([slurry_a, slurry_b])

        self.assertEqual(set(final_mix.parents.all()), {slurry_a, slurry_b})
        self.assertIn(final_mix, slurry_a.children.all())
        self.assertIn(final_mix, slurry_b.children.all())

    def test_duplicate_step_link_is_rejected(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)

        parent = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)
        child = ExperimentStep.objects.create(step_name="BB", experiment=project_experiment)
        ExperimentStepLink.objects.create(parent_step=parent, child_step=child)

        with self.assertRaises(Exception):
            ExperimentStepLink.objects.create(parent_step=parent, child_step=child)

    def test_step_link_self_reference_is_rejected(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        step = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)

        with self.assertRaises(ValidationError):
            ExperimentStepLink.objects.create(parent_step=step, child_step=step)

    def test_step_link_cycle_is_rejected(self):
        exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)

        step1 = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)
        step2 = ExperimentStep.objects.create(step_name="BB", experiment=project_experiment)
        step3 = ExperimentStep.objects.create(step_name="CC", experiment=project_experiment)

        ExperimentStepLink.objects.create(parent_step=step1, child_step=step2)
        ExperimentStepLink.objects.create(parent_step=step2, child_step=step3)

        with self.assertRaises(ValidationError):
            ExperimentStepLink.objects.create(parent_step=step3, child_step=step1)

    def test_update_experiment_identifiers_signal(self):
        """Test that changing experiment name updates project_experiment and step identifiers"""
        exp = Project.objects.create(exp_name="OLD001", project=self.project, owner=self.user)
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        step = ExperimentStep.objects.create(step_name="BB", experiment=project_experiment)
        
        self.assertEqual(project_experiment.full_experiment_code, "OLD001AA")
        self.assertEqual(step.full_step, "OLD001AA-BB00")
        
        # Update experiment name
        exp.exp_name = "NEW001"
        exp.save()
        
        # Refresh from db
        project_experiment.refresh_from_db()
        step.refresh_from_db()
        
        self.assertEqual(project_experiment.full_experiment_code, "NEW001AA")
        self.assertEqual(step.full_step, "NEW001AA-BB00")

    def test_raw_material_creation_and_unique_batch(self):
        material = RawMaterial.objects.create(
            material_code="rm001",
            received_date=date(2026, 6, 19),
            material_type="Powder",
            total_quantity="2500.0000",
            total_unit="g",
            owner=self.user
        )

        self.assertEqual(material.material_code, "RM001")
        self.assertEqual(material.batch_number, "RM001-061926")
        self.assertIsNone(material.material_name)
        self.assertEqual(material.total_quantity, Decimal("2500.0000"))
        self.assertEqual(material.total_unit, "g")
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
        project_experiment = Experiment.objects.create(experiment_code="AA", project=exp)
        step = ExperimentStep.objects.create(step_name="AA", experiment=project_experiment)
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
