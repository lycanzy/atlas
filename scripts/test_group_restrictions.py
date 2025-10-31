# Test script to verify group-based restrictions on projects and experiments.
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
import json

from experiment_flow.models import Exp, Project, ResearchGroup, UserProfile

User = get_user_model()

def run_test():
    print("--- Setting up test data ---")
    # Create two research groups
    group_a, _ = ResearchGroup.objects.get_or_create(group_name='GroupA')
    group_b, _ = ResearchGroup.objects.get_or_create(group_name='GroupB')
    print(f"Created groups: {group_a.group_name}, {group_b.group_name}")

    # Create two users and their profiles
    user_a, created_a = User.objects.get_or_create(username='userA')
    if created_a:
        user_a.set_password('testpass')
        user_a.save()
    profile_a, _ = UserProfile.objects.get_or_create(user=user_a, defaults={'research_group': group_a})
    
    user_b, created_b = User.objects.get_or_create(username='userB')
    if created_b:
        user_b.set_password('testpass')
        user_b.save()
    profile_b, _ = UserProfile.objects.get_or_create(user=user_b, defaults={'research_group': group_b})
    print(f"Created users: {user_a.username} (in {profile_a.research_group.group_name}), {user_b.username} (in {profile_b.research_group.group_name})")

    # Create two projects, one for each group
    proj_a, _ = Project.objects.get_or_create(project_name='ProjectA', defaults={'project_code': 'PRA', 'group': group_a})
    proj_b, _ = Project.objects.get_or_create(project_name='ProjectB', defaults={'project_code': 'PRB', 'group': group_b})
    print(f"Created projects: {proj_a.project_name} (Group A), {proj_b.project_name} (Group B)")

    # Create two experiments
    exp_a = Exp.objects.create(exp_name='ExpA', project=proj_a, owner=user_a)
    exp_b = Exp.objects.create(exp_name='ExpB', project=proj_b, owner=user_b)
    print(f"Created experiments: {exp_a.exp_name} (Project A), {exp_b.exp_name} (Project B)")

    client = Client()

    # --- Test Case 1: User A ---
    print("\n--- Testing as User A (should only see Group A data) ---")
    client.force_login(user_a)

    # 1.1: Check index page
    index_url = reverse('index')
    response = client.get(index_url)
    print(f"GET {index_url} -> Status: {response.status_code}")
    content = response.content.decode()
    sees_exp_a = exp_a.exp_name in content
    sees_exp_b = exp_b.exp_name in content
    print(f"Index page sees '{exp_a.exp_name}'? -> {sees_exp_a} (Expected: True)")
    print(f"Index page sees '{exp_b.exp_name}'? -> {sees_exp_b} (Expected: False)")
    assert sees_exp_a and not sees_exp_b

    # 1.2: Check detail page access (should succeed for ExpA)
    exp_a_url = reverse('experiment_detail', args=[exp_a.id])
    response = client.get(exp_a_url)
    print(f"GET {exp_a_url} (own group) -> Status: {response.status_code} (Expected: 200)")
    assert response.status_code == 200

    # 1.3: Check detail page access (should fail for ExpB)
    exp_b_url = reverse('experiment_detail', args=[exp_b.id])
    response = client.get(exp_b_url)
    print(f"GET {exp_b_url} (other group) -> Status: {response.status_code}, Redirects to: {response.url} (Expected: 302 to index)")
    assert response.status_code == 302
    assert response.url == reverse('index')

    # --- Test Case 2: User B ---
    print("\n--- Testing as User B (should only see Group B data) ---")
    client.force_login(user_b)

    # 2.1: Check index page
    response = client.get(index_url)
    print(f"GET {index_url} -> Status: {response.status_code}")
    content = response.content.decode()
    sees_exp_a = exp_a.exp_name in content
    sees_exp_b = exp_b.exp_name in content
    print(f"Index page sees '{exp_a.exp_name}'? -> {sees_exp_a} (Expected: False)")
    print(f"Index page sees '{exp_b.exp_name}'? -> {sees_exp_b} (Expected: True)")
    assert not sees_exp_a and sees_exp_b

    # 2.2: Check detail page access (should fail for ExpA)
    response = client.get(exp_a_url)
    print(f"GET {exp_a_url} (other group) -> Status: {response.status_code}, Redirects to: {response.url} (Expected: 302 to index)")
    assert response.status_code == 302
    assert response.url == reverse('index')

    # 2.3: Check detail page access (should succeed for ExpB)
    response = client.get(exp_b_url)
    print(f"GET {exp_b_url} (own group) -> Status: {response.status_code} (Expected: 200)")
    assert response.status_code == 200
    
    print("\n--- All tests passed successfully! ---")

    # Optional: Clean up test data
    # print("\n--- Cleaning up test data ---")
    # exp_a.delete()
    # exp_b.delete()
    # proj_a.delete()
    # proj_b.delete()
    # user_a.delete()
    # user_b.delete()
    # group_a.delete()
    # group_b.delete()
    # print("Cleanup complete.")

run_test()
