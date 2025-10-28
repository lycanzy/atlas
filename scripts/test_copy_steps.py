# Test script to verify copy_steps copies step details and parent relationships
from django.contrib.auth import get_user_model
from django.test import Client
import json

from experiment_flow.models import Exp, ExpFlow, ExpStep, Project

User = get_user_model()

# create/get a test user
user, created = User.objects.get_or_create(username='test_copy_user')
if created:
    user.set_password('testpass')
    user.save()

# create/get a research group and project
from experiment_flow.models import ResearchGroup
group, _ = ResearchGroup.objects.get_or_create(group_name='TestGroup')
project, _ = Project.objects.get_or_create(project_name='TestProj', defaults={'project_code': 'TPX', 'group': group})

# create an experiment
exp = Exp.objects.create(exp_name='TestExp', project=project, owner=user)

# create source and target flows
flow_src = ExpFlow.objects.create(flow_name='AA', exp=exp)
flow_tgt = ExpFlow.objects.create(flow_name='BB', exp=exp)

# create steps in source flow
s1 = ExpStep.objects.create(step_name='MX', step_number='00', step_description='Original step 1', flow=flow_src, status='Planned')
s2 = ExpStep.objects.create(step_name='MY', step_number='00', step_description='Original step 2 (child)', flow=flow_src, parent=s1, status='Planned')

print('Setup complete:')
print('Exp', exp.id, exp.exp_name)
print('Source flow', flow_src.id, flow_src.full_flow)
print('Target flow', flow_tgt.id, flow_tgt.full_flow)
print('Source steps:')
for s in ExpStep.objects.filter(flow=flow_src).order_by('id'):
    print(s.id, s.step_name, s.step_number, 'parent->', s.parent.id if s.parent else None, 'desc:', s.step_description)

# Prepare payload
payload = {
    'step_ids': [s1.id, s2.id],
    'target_flow_name': flow_tgt.full_flow
}

client = Client()
client.force_login(user)
resp = client.post(f'/experiment/{exp.id}/copy_steps/', data=json.dumps(payload), content_type='application/json')
print('\nPOST /copy_steps/ response status:', resp.status_code)
try:
    print('Response JSON:', resp.json())
except Exception:
    print('Response content:', resp.content)

# Verify copied steps in target flow
print('\nTarget flow steps after copy:')
for s in ExpStep.objects.filter(flow=flow_tgt).order_by('id'):
    print(s.id, s.step_name, s.step_number, 'parent->', s.parent.id if s.parent else None, 'desc:', s.step_description, 'components:', s.components)

# Clean up created objects (optional - commented out if you want to inspect data)
# Exp.objects.filter(id=exp.id).delete()
print('\nTest script finished.')
