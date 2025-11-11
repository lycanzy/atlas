#!/usr/bin/env python
"""
Test s cript to verify that staff and superuser can access all experiments
while regular users are still restricted to their research group.

This script demonstrates the expected behavior:
1. Regular users can only see experiments in their research group
2. Staff users can see ALL experiments regardless of group
3. Superusers can see ALL experiments regardless of group

Usage:
    python test_staff_access.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'experiment_app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'experiment_app.settings')
django.setup()

from django.contrib.auth.models import User
from experiment_flow.models import Exp, Project, ResearchGroup, UserProfile
from experiment_flow.views import get_experiments_for_user


def test_access_control():
    """Test that access control works correctly for different user types"""
    
    print("=" * 60)
    print("Testing Staff/Superuser Access to All Experiments")
    print("=" * 60)
    
    # Get all experiments
    all_experiments = Exp.objects.all()
    total_count = all_experiments.count()
    print(f"\nTotal experiments in database: {total_count}")
    
    # Test with different user types
    test_users = [
        ("regular user", lambda u: not u.is_staff and not u.is_superuser),
        ("staff user", lambda u: u.is_staff),
        ("superuser", lambda u: u.is_superuser)
    ]
    
    for user_type, user_filter in test_users:
        users = User.objects.filter(is_active=True)
        matching_users = [u for u in users if user_filter(u)]
        
        if not matching_users:
            print(f"\n⚠️  No {user_type} found in database")
            continue
            
        user = matching_users[0]
        profile = getattr(user, 'profile', None)
        user_group = getattr(profile, 'research_group', None) if profile else None
        
        # Get experiments visible to this user
        visible_experiments = get_experiments_for_user(user)
        visible_count = visible_experiments.count()
        
        print(f"\n{user_type.upper()}: {user.username}")
        print(f"  Research Group: {user_group.group_name if user_group else 'None'}")
        print(f"  Is Staff: {user.is_staff}")
        print(f"  Is Superuser: {user.is_superuser}")
        print(f"  Visible Experiments: {visible_count}/{total_count}")
        
        # Verify expected behavior
        if user.is_staff or user.is_superuser:
            if visible_count == total_count:
                print(f"  ✅ PASS: {user_type.capitalize()} can see all experiments")
            else:
                print(f"  ❌ FAIL: {user_type.capitalize()} should see all {total_count} experiments but only sees {visible_count}")
        else:
            # Regular user should only see their group's experiments
            if user_group:
                group_exp_count = Exp.objects.filter(project__group=user_group).count()
                if visible_count == group_exp_count:
                    print(f"  ✅ PASS: Regular user sees only their group's {visible_count} experiments")
                else:
                    print(f"  ❌ FAIL: Regular user should see {group_exp_count} experiments but sees {visible_count}")
            else:
                if visible_count == 0:
                    print(f"  ✅ PASS: User with no group sees 0 experiments")
                else:
                    print(f"  ❌ FAIL: User with no group should see 0 experiments but sees {visible_count}")
    
    # Show group distribution
    print("\n" + "=" * 60)
    print("Experiment Distribution by Research Group")
    print("=" * 60)
    
    groups = ResearchGroup.objects.all()
    for group in groups:
        count = Exp.objects.filter(project__group=group).count()
        print(f"  {group.group_name}: {count} experiments")
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == '__main__':
    test_access_control()
