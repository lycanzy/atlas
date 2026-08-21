# Test script to verify copy_steps copies step details and parent relationships
from django.contrib.auth import get_user_model
from django.test import Client
from datetime import date
import json

from experiment_flow.models import Experiment, ExperimentStep, Project, ProjectCategory, RawMaterial, StepRawMaterialUsage

User = get_user_model()

# create/get a test user
user, created = User.objects.get_or_create(username='test_copy_user')
if created:
    user.set_password('testpass')
    user.save()

# create/get a research group and project category
from experiment_flow.models import ResearchGroup
group, _ = ResearchGroup.objects.get_or_create(group_name='TestGroup')
project_category, _ = ProjectCategory.objects.get_or_create(project_name='TestProj', defaults={'project_code': 'TPX', 'group': group})

# create a project
exp = Project.objects.create(exp_name='TestExp', project=project_category, owner=user)

# create source and target project_experiments
experiment_src = Experiment.objects.create(experiment_code='AA', project=exp)
experiment_tgt = Experiment.objects.create(experiment_code='BB', project=exp)

# create steps in source project_experiment
s1 = ExperimentStep.objects.create(step_name='MX', step_number='00', step_description='Original step 1', experiment=experiment_src, status='Planned')
s2 = ExperimentStep.objects.create(step_name='MY', step_number='00', step_description='Original step 2 (child)', experiment=experiment_src, parent=s1, status='Planned')
raw_material = RawMaterial.objects.create(
    material_code='RMTEST',
    batch_number='RMTEST-001',
    received_date=date.today(),
    material_name='Test Raw Material',
    owner=user,
)
StepRawMaterialUsage.objects.create(step=s1, raw_material=raw_material, quantity='1.0000', unit='g')

print('Setup complete:')
print('Project', exp.id, exp.exp_name)
print('Source experiment', experiment_src.id, experiment_src.full_experiment_code)
print('Target experiment', experiment_tgt.id, experiment_tgt.full_experiment_code)
print('Source steps:')
for s in ExperimentStep.objects.filter(experiment=experiment_src).order_by('id'):
    print(s.id, s.step_name, s.step_number, 'parent->', s.parent.id if s.parent else None, 'desc:', s.step_description)

# Prepare payload
payload = {
    'step_ids': [s1.id, s2.id],
    'target_experiment_code': experiment_tgt.full_experiment_code
}

client = Client()
client.force_login(user)
resp = client.post(f'/experiment/{exp.id}/copy_steps/', data=json.dumps(payload), content_type='application/json')
print('\nPOST /copy_steps/ response status:', resp.status_code)
try:
    print('Response JSON:', resp.json())
except Exception:
    print('Response content:', resp.content)

# Verify copied steps in target experiment
print('\nTarget experiment steps after copy:')
for s in ExperimentStep.objects.filter(experiment=experiment_tgt).order_by('id'):
    usages = [
        f"{usage.raw_material.material_code}/{usage.raw_material.batch_number}: {usage.quantity} {usage.unit or ''}".strip()
        for usage in s.raw_material_usages.select_related('raw_material')
    ]
    print(s.id, s.step_name, s.step_number, 'parent->', s.parent.id if s.parent else None, 'desc:', s.step_description, 'raw materials:', usages)

# Clean up created objects (optional - commented out if you want to inspect data)
# Project.objects.filter(id=exp.id).delete()
print('\nTest script finished.')
