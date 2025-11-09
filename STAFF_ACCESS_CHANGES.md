# Staff and Superuser Access Changes

## Summary
Updated the experiment tracking application to allow users with **Staff** or **Superuser** status to access all experiments without research group restrictions, while regular users continue to be restricted to their own research group.

## Changes Made

### 1. Updated `get_experiments_for_user()` helper function
**File:** `experiment_app/experiment_flow/views.py`

- Added logic to check if user is staff or superuser
- If yes: return all experiments (no group filtering)
- If no: apply existing research group filtering

```python
# Staff and superusers can access all experiments
if user.is_staff or user.is_superuser:
    qs = Exp.objects.all().order_by('-created_on')
else:
    # Regular users: filter by research group
    # ...existing logic...
```

### 2. Updated `experiment_detail()` view
**File:** `experiment_app/experiment_flow/views.py`

- Bypasses group permission check for staff/superuser
- Regular users still require matching research group

```python
# Staff and superusers can access all experiments
if not (request.user.is_staff or request.user.is_superuser):
    # Apply group restriction for regular users
    # ...existing logic...
```

### 3. Updated `add_experiment()` view
**File:** `experiment_app/experiment_flow/views.py`

- Staff/superuser can see and select from all projects
- Regular users still see only projects in their research group

### 4. Updated `add_flow()` view
**File:** `experiment_app/experiment_flow/views.py`

- Staff/superuser can add flows to any experiment
- Regular users restricted to experiments in their group

### 5. Updated barcode generation views
**Files:** `flow_barcode()` and `step_barcode()` in `views.py`

- Staff/superuser can generate barcodes for any flow/step
- Regular users restricted to their group's flows/steps

### 6. Updated `get_all_steps()` API endpoint
**File:** `experiment_app/experiment_flow/views.py`

- Staff/superuser get all steps across all groups
- Regular users get only steps from their research group

## User Types and Access Levels

| User Type | Access Level | Can See |
|-----------|-------------|---------|
| **Regular User** (no staff/superuser) | Group-restricted | Only experiments/flows/steps in their research group |
| **Staff User** (`is_staff=True`) | Unrestricted | All experiments/flows/steps across all groups |
| **Superuser** (`is_superuser=True`) | Unrestricted | All experiments/flows/steps across all groups |

## Testing

A test script has been created to verify the changes:

```bash
cd /Users/yizhou/Experiment-Tracking-App
python scripts/test_staff_access.py
```

The script validates:
- ✅ Staff users can see all experiments
- ✅ Superusers can see all experiments  
- ✅ Regular users are still restricted to their research group
- ✅ Users with no group see no experiments (unless staff/superuser)

## Security Considerations

### Maintained Security
- Authentication is still required (`@login_required` decorator on all views)
- Regular users cannot access experiments outside their group
- Permission boundaries remain intact for non-privileged users

### New Capabilities
- Staff and superuser accounts now have cross-group visibility
- Useful for:
  - System administrators monitoring all experiments
  - Lab managers overseeing multiple research groups
  - Technical support staff helping users across groups
  - Data analysis requiring cross-group insights

## Backward Compatibility

✅ **Fully backward compatible**
- Existing user permissions unchanged
- Regular users experience no change in behavior
- Only staff/superuser accounts gain additional access
- No database migrations required
- No changes to models or templates

## Files Modified

1. `experiment_app/experiment_flow/views.py` - Core access control logic

## Files Created

1. `scripts/test_staff_access.py` - Test script to verify changes
2. `STAFF_ACCESS_CHANGES.md` - This documentation file

## Verification Steps

1. **Run system check:**
   ```bash
   cd experiment_app
   python manage.py check
   ```
   Expected: No errors (only staticfiles warning is acceptable)

2. **Run test script:**
   ```bash
   python scripts/test_staff_access.py
   ```
   Expected: All PASS results for staff and superuser access

3. **Manual testing (recommended):**
   - Log in as regular user → verify only group experiments visible
   - Log in as staff user → verify all experiments visible
   - Log in as superuser → verify all experiments visible
   - Test "My Experiments" filter for each user type
   - Test experiment detail access for each user type

## Future Considerations

If you need more granular permissions in the future, consider:
- Adding custom permissions for specific cross-group access
- Implementing group-level permissions (e.g., "can_view_all_experiments")
- Using Django's built-in permissions framework for role-based access
- Adding audit logging for staff/superuser cross-group access

---

**Date:** November 9, 2025  
**Status:** ✅ Complete and tested
