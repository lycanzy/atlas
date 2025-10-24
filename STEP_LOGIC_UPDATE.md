# Step Logic Update

## Summary of Changes

This document describes the modifications made to the step parent/previous step selection logic and step numbering system.

## Changes Made

### 1. Previous Step Selection - Cross-Experiment Support

**Previous Behavior:**
- Parent step could only be selected from steps within the same flow
- Limited flexibility in defining step dependencies

**New Behavior:**
- Parent step can now be **any step from any experiment** (except the step itself)
- Provides a **searchable dropdown** interface using Select2
- Allows complex cross-experiment workflows and dependencies

**Technical Implementation:**
- **models.py**: No changes needed - `parent` field already allows any ExpStep
- **forms.py**: 
  - Added custom `parent` field with Select2-compatible widget
  - Changed queryset to include all steps across all experiments
  - Excludes only the current step (when editing) to prevent circular references
  - Orders steps by: experiment name → flow name → step name → step number
- **templates**: 
  - Added Select2 CSS/JS libraries via CDN
  - JavaScript initializes searchable dropdown when modals open
  - Updated label from "Parent Step" to "Previous Step (Any Experiment)"
  - Added help text: "Search and select any step from any experiment as the previous step"

**User Experience:**
- Click in the "Previous Step" field
- Type to search across all experiments, flows, and steps
- Select from filtered results
- Clear selection with × button if needed

### 2. Step Number Calculation - Flow-Scoped Counting

**Previous Behavior:**
- `step_num` counted ALL parent steps in the parent chain, regardless of which flow they belonged to

**New Behavior:**
- `step_num` now counts **only previous steps within the current flow**
- Steps from other flows/experiments don't increment the counter
- Provides accurate step numbering within each flow's context

**Technical Implementation:**
- **models.py - ExpStep.step_num property**:
```python
@property
def step_num(self):
    """Count the number of previous steps within the current flow only"""
    step_num = 0
    current = self.parent
    while current:
        # Only count if the parent is in the same flow
        if current.flow == self.flow:
            step_num += 1
        current = current.parent   # move up to the next parent
    return f"{step_num:02d}"
```

**Example Scenarios:**

**Scenario 1: All steps in same flow**
```
Flow: MLO001AA
- Step AA (no parent) → step_num = 00
- Step BB (parent: AA in MLO001AA) → step_num = 01  
- Step CC (parent: BB in MLO001AA) → step_num = 02
```

**Scenario 2: Parent from different flow**
```
Flow: MLO001MX
- Step AA (no parent) → step_num = 00
- Step BB (parent: AA in MLO001MX) → step_num = 01
- Step CV (parent: CC in MLO001AA - different flow!) → step_num = 00
  - CV's parent is in a different flow, so it doesn't count
  - CV is treated as a top-level step within MLO001MX
```

**Scenario 3: Mixed parent chain**
```
Flow: MLO002BB
- Step AA (parent: CV in MLO001MX) → step_num = 00
  - Parent is in different flow, doesn't count
- Step BB (parent: AA in MLO002BB) → step_num = 01
  - Parent is in SAME flow (MLO002BB), counts!
- Step CC (parent: BB in MLO002BB) → step_num = 02
  - Chain: CC → BB (count) → AA (count) → CV (don't count)
```

## Benefits

### 1. Cross-Experiment Dependencies
- Model complex workflows that span multiple experiments
- Reference previous work without duplicating steps
- Track dependencies between related projects

### 2. Accurate Flow-Based Numbering
- Step numbers reflect position within the flow
- Makes sense when viewing/sorting steps in a flow
- Prevents misleading high step numbers from external parents

### 3. Better User Experience
- Searchable dropdown for finding steps quickly
- Clear labeling: "Previous Step (Any Experiment)"
- Flexible workflow design

## Database Migrations

No database migrations needed - these are logic and UI changes only:
- `parent` field already exists and accepts any ExpStep
- `step_num` is a computed property, not a database field

## Testing Recommendations

1. **Create steps with cross-experiment parents**
   - Add step in Flow A with parent from Flow B
   - Verify step_num = 00 (parent not counted)

2. **Create step chains within same flow**
   - Add steps A → B → C in same flow
   - Verify step_num increments: 00, 01, 02

3. **Test mixed parent chains**
   - Add step with external parent
   - Add child step in same flow
   - Verify only same-flow parents are counted

4. **Test searchability**
   - Open add/edit step modal
   - Type in previous step field
   - Verify search filters results
   - Verify can select from any experiment

## Files Modified

1. **experiment_app/experiment_flow/models.py**
   - Updated `ExpStep.step_num` property to only count same-flow parents

2. **experiment_app/experiment_flow/forms.py**
   - Added custom `parent` field with Select2 widget
   - Changed queryset to all steps (except self)
   - Removed flow-based filtering

3. **experiment_app/experiment_flow/templates/experiment_flow/base.html**
   - Added Select2 CSS/JS CDN links
   - Added jQuery (required for Select2)

4. **experiment_app/experiment_flow/templates/experiment_flow/experiment_detail.html**
   - Added Select2 initialization in modal load handlers
   - Added Select2 cleanup in modal close handlers
   - Applies to both add and edit step modals

5. **experiment_app/experiment_flow/templates/experiment_flow/add_step.html**
   - Updated label and help text for parent field

6. **experiment_app/experiment_flow/templates/experiment_flow/edit_step.html**
   - Updated label and help text for parent field

## Backward Compatibility

✅ **Fully backward compatible**
- Existing steps with parents in the same flow continue to work
- Existing step numbers remain accurate
- No data migration required
- Just adds new capabilities

## Notes

- Select2 initialization uses 100ms timeout to ensure DOM is ready
- Select2 theme matches Bootstrap 5 styling
- Dropdown renders inside modal to prevent z-index issues
- Step_num is always computed on-the-fly, never stored
