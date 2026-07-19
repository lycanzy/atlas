from django.test import TestCase
from django.utils import timezone
from experiment_flow.forms import ExperimentStepForm, ExperimentForm, RawMaterialForm
from experiment_flow.models import StepNameTemplate, ExperimentStep, Experiment, Project, ProjectCategory, ResearchGroup, Sample, User, Equipment

class FormTests(TestCase):
    def setUp(self):
        self.group = ResearchGroup.objects.create(group_name="Test Group")
        self.user = User.objects.create_user(username="testuser", password="password")
        self.project = ProjectCategory.objects.create(project_name="Test ProjectCategory", project_code="TPR", group=self.group)
        self.exp = Project.objects.create(exp_name="TPR001", project=self.project, owner=self.user)
        self.experiment = Experiment.objects.create(experiment_code="AA", project=self.exp)
        
        # Create templates
        StepNameTemplate.objects.create(step_code="AA", step_label="Step A")
        StepNameTemplate.objects.create(step_code="BB", step_label="Step B")

    def test_step_form_valid(self):
        form_data = {
            'step_name': 'AA',
            'step_description': 'Test Description',
            'status': 'Planned'
        }
        form = ExperimentStepForm(data=form_data, experiment=self.experiment)
        self.assertTrue(form.is_valid())

    def test_completed_step_without_time_uses_current_time(self):
        form = ExperimentStepForm(data={
            'step_name': 'AA',
            'status': 'Completed',
        }, experiment=self.experiment)
        self.assertTrue(form.is_valid())

        before_save = timezone.now()
        step = form.save(commit=False)
        step.experiment = self.experiment
        step.save()
        after_save = timezone.now()

        self.assertGreaterEqual(step.completed_on, before_save)
        self.assertLessEqual(step.completed_on, after_save)

    def test_step_form_rejects_more_than_200_samples(self):
        form = ExperimentStepForm(data={
            'step_name': 'AA',
            'status': 'Planned',
            'sample_count': 201,
        }, experiment=self.experiment)

        self.assertFalse(form.is_valid())
        self.assertIn('sample_count', form.errors)

    def test_step_form_does_not_allow_removing_existing_samples(self):
        step = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment)
        Sample.sync_for_step(step, 2)
        form = ExperimentStepForm(data={
            'step_name': 'AA',
            'status': 'Planned',
            'sample_count': 1,
        }, instance=step, experiment=self.experiment)

        self.assertFalse(form.is_valid())
        self.assertIn('sample_count', form.errors)

    def test_step_form_invalid_name(self):
        # 'CC' is not in StepNameTemplate, but the form choice field is populated from DB.
        # If we try to submit a value not in choices, it should fail.
        form_data = {
            'step_name': 'CC', 
            'status': 'Planned'
        }
        form = ExperimentStepForm(data=form_data, experiment=self.experiment)
        self.assertFalse(form.is_valid())
        self.assertIn('step_name', form.errors)

    def test_step_form_parent_queryset(self):
        # Create some steps
        step1 = ExperimentStep.objects.create(step_name="AA", experiment=self.experiment)
        step2 = ExperimentStep.objects.create(step_name="BB", experiment=self.experiment)
        
        # Initialize form for a new step
        form = ExperimentStepForm(experiment=self.experiment)
        # Parent queryset should include existing steps
        self.assertIn(step1, form.fields['parents'].queryset)
        self.assertIn(step2, form.fields['parents'].queryset)
        
        # Initialize form for editing step1
        form_edit = ExperimentStepForm(instance=step1, experiment=self.experiment)
        # Parent queryset should NOT include step1 (cannot be own parent)
        self.assertNotIn(step1, form_edit.fields['parents'].queryset)
        self.assertIn(step2, form_edit.fields['parents'].queryset)

    def test_step_form_equipment_choices_use_equipment_id(self):
        equipment = Equipment.objects.create(
            equipment_name="Vacuum Oven",
            equipment_id="EQ-OVEN-001",
            owner=self.user,
        )

        form = ExperimentStepForm(experiment=self.experiment)

        self.assertEqual(form.fields['tool'].label_from_instance(equipment), "EQ-OVEN-001")

    def test_flow_form(self):
        form_data = {'experiment_code': 'AA'}
        form = ExperimentForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        form_data_invalid = {'experiment_code': 'A'} # Too short
        form = ExperimentForm(data=form_data_invalid)
        # Validation happens at model level, but ModelForm calls model.clean()
        # Wait, ModelForm validation usually checks max_length but custom clean() might need explicit call or is handled by is_valid() running full_clean()
        # Let's check if is_valid captures model validation errors.
        # Django ModelForm runs model.clean() during validation.
        self.assertFalse(form.is_valid()) 

    def test_raw_material_form_valid(self):
        form = RawMaterialForm(data={
            'material_code': 'RM001',
            'received_date': '2026-06-19',
            'material_type': 'Powder',
            'material_name': '',
            'owner': self.user.id,
            'supplier': 'Vendor A',
            'location': 'Shelf 1',
            'is_active': 'on'
        })
        self.assertTrue(form.is_valid())
