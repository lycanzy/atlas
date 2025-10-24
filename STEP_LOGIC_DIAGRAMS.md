# Step Logic - Visual Diagrams

## Previous Step Selection Interface

```
╔══════════════════════════════════════════════════════════╗
║  Add New Experiment Step                            [×]  ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  ┌─────────────────────────────────────────────────┐    ║
║  │ Step Name *                                     │    ║
║  │ ┌─────────────────────────────────────────────┐ │    ║
║  │ │ AA - Cleaning                             ▼ │ │    ║
║  │ └─────────────────────────────────────────────┘ │    ║
║  └─────────────────────────────────────────────────┘    ║
║                                                          ║
║  ┌─────────────────────────────────────────────────┐    ║
║  │ Previous Step (Any Experiment)                  │    ║
║  │ ┌─────────────────────────────────────────────┐ │    ║
║  │ │ 🔍 Search for a previous step...          × │ │ ← Searchable!
║  │ └─────────────────────────────────────────────┘ │    ║
║  │ ┌─────────────────────────────────────────────┐ │    ║
║  │ │ MLO001AA-AA00 (Cleaning)                   │ │    ║
║  │ │ MLO001AA-BB00 (Deposition)                 │ │ ← All experiments
║  │ │ MLO001AA-CV01 (Lithography)                │ │    ║
║  │ │ MLO001MX-AA00 (Cleaning)                   │ │    ║
║  │ │ MLO002BB-AA00 (Cleaning)                   │ │    ║
║  │ │ MLO002BB-BB00 (Etching)                    │ │    ║
║  │ └─────────────────────────────────────────────┘ │    ║
║  └─────────────────────────────────────────────────┘    ║
║                                                          ║
║  Search and select any step from any experiment as      ║
║  the previous step                                       ║
║                                                          ║
║  [Cancel]                              [Add Step]        ║
╚══════════════════════════════════════════════════════════╝
```

---

## Step Numbering Logic Flow Chart

```
                    ┌─────────────────────┐
                    │  Calculate step_num │
                    │   for current step  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Initialize counter │
                    │    step_num = 0     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Get parent step   │
                    └──────────┬──────────┘
                               │
                      ┌────────┴────────┐
                      │                 │
                   No parent         Has parent
                      │                 │
                      ▼                 ▼
              ┌──────────────┐   ┌─────────────────────┐
              │ Return 00    │   │  Is parent in the   │
              │ (top-level)  │   │  SAME flow?         │
              └──────────────┘   └──────┬──────────────┘
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                           YES (same)          NO (different)
                              │                   │
                              ▼                   ▼
                    ┌─────────────────┐   ┌──────────────────┐
                    │  step_num += 1  │   │  Don't increment │
                    │  (count it!)    │   │  (skip it)       │
                    └────────┬────────┘   └────────┬─────────┘
                             │                     │
                             └──────────┬──────────┘
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │  Move to parent's   │
                             │  parent             │
                             └──────────┬──────────┘
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │  Repeat until no    │
                             │  more parents       │
                             └──────────┬──────────┘
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │  Format as 2 digits │
                             │  e.g., "02"         │
                             └─────────────────────┘
```

---

## Real-World Example Scenario

### Scenario: Lithography Process with Cross-Experiment Reference

```
╔══════════════════════════════════════════════════════════════════╗
║                    EXPERIMENT MLO001                             ║
╠══════════════════════════════════════════════════════════════════╣
║  Flow: MLO001AA (Standard Cleaning)                              ║
║  ┌────────────────────────────────────────────────────────┐      ║
║  │  AA00  │  Wafer Cleaning         │  Status: Completed  │      ║
║  └────────────────────────────────────────────────────────┘      ║
║  ┌────────────────────────────────────────────────────────┐      ║
║  │  BB00  │  Rinse & Dry   (→AA00)  │  Status: Completed  │      ║
║  └────────────────────────────────────────────────────────┘      ║
╚══════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════╗
║                    EXPERIMENT MLO002                             ║
╠══════════════════════════════════════════════════════════════════╣
║  Flow: MLO002LT (Lithography)                                    ║
║  ┌────────────────────────────────────────────────────────┐      ║
║  │  AA00  │  HMDS Priming  (→MLO001AA-BB00) │ Planned    │ ← References MLO001!
║  └────────────────────────────────────────────────────────┘      ║
║           Parent is from different flow                          ║
║           So step_num = 00 (external parent not counted)         ║
║                                                                  ║
║  ┌────────────────────────────────────────────────────────┐      ║
║  │  BB01  │  Spin Coat PR  (→AA00)  │  Status: Planned   │ ← Same flow!
║  └────────────────────────────────────────────────────────┘      ║
║           Parent IS in same flow (MLO002LT)                      ║
║           So step_num = 01 (AA00 counts)                         ║
║                                                                  ║
║  ┌────────────────────────────────────────────────────────┐      ║
║  │  CV02  │  Soft Bake     (→BB01)  │  Status: Planned   │ ← Chain continues
║  └────────────────────────────────────────────────────────┘      ║
║           Chain: CV → BB01 (count) → AA00 (count) → MLO001-BB00 (don't count)
║           So step_num = 02                                       ║
╚══════════════════════════════════════════════════════════════════╝
```

**Explanation:**
- MLO002LT-AA00 references MLO001AA-BB00 as prerequisite (different experiment!)
- step_num = 00 because parent is external
- MLO002LT-BB01 has parent MLO002LT-AA00 (same flow)
- step_num = 01 because it has 1 same-flow parent
- MLO002LT-CV02 has parent MLO002LT-BB01 (same flow)
- step_num = 02 because it has 2 same-flow parents in chain

---

## Before vs After Comparison

### BEFORE: Limited Parent Selection
```
┌─────────────────────────────────────┐
│ Flow: MLO001AA                      │
│ ┌─────────────────────────────────┐ │
│ │ Parent Step             ▼       │ │
│ │ ─────────────────────────────── │ │
│ │ No parent (top-level step)      │ │  
│ │ MLO001AA-AA00                   │ │ ← Only same flow!
│ │ MLO001AA-BB00                   │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### AFTER: Full Cross-Experiment Access
```
┌─────────────────────────────────────────┐
│ Previous Step (Any Experiment)          │
│ ┌─────────────────────────────────────┐ │
│ │ 🔍 Search...                      × │ │ ← Searchable!
│ │ ─────────────────────────────────── │ │
│ │ No parent (top-level step)          │ │
│ │ MLO001AA-AA00                       │ │ ← All experiments
│ │ MLO001AA-BB00                       │ │ ← All flows
│ │ MLO001MX-CV00                       │ │ ← All steps
│ │ MLO002BB-AA00                       │ │
│ │ MLO002BB-BB00                       │ │
│ │ MLO003XX-AA00                       │ │
│ │ ...                                 │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

## Step Number Calculation Examples Table

| Step | Parent | Parent Flow | Current Flow | Same Flow? | Count? | step_num |
|------|--------|-------------|--------------|------------|--------|----------|
| MLO001AA-AA00 | None | - | MLO001AA | - | - | 00 |
| MLO001AA-BB00 | AA00 | MLO001AA | MLO001AA | ✅ Yes | ✅ Yes | 01 |
| MLO001AA-CC00 | BB00 | MLO001AA | MLO001AA | ✅ Yes | ✅ Yes | 02 |
| MLO002LT-AA00 | MLO001AA-BB00 | MLO001AA | MLO002LT | ❌ No | ❌ No | 00 |
| MLO002LT-BB00 | MLO002LT-AA00 | MLO002LT | MLO002LT | ✅ Yes | ✅ Yes | 01 |
| MLO002LT-CV00 | MLO002LT-BB00 | MLO002LT | MLO002LT | ✅ Yes | ✅ Yes | 02 |

**Key Insight:** step_num only increments when climbing the parent chain **within the same flow**.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                        │
├────────────────────────────────────────────────────────────┤
│  Experiment Detail Page                                    │
│  ├─ Add Step Button (opens modal)                          │
│  └─ Edit Step Button (opens modal)                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Modal: Add/Edit Step                                │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ Previous Step (Any Experiment)                 │  │  │
│  │  │ ┌────────────────────────────────────────────┐ │  │  │
│  │  │ │ 🔍 Search... [Select2]                  × │ │  │  │
│  │  │ └────────────────────────────────────────────┘ │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────┬──────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────────┐
│                        BACKEND                             │
├────────────────────────────────────────────────────────────┤
│  forms.py (ExpStepForm)                                    │
│  ├─ parent field queryset = ALL steps (except self)        │
│  ├─ Select2 widget with searchable dropdown                │
│  └─ Ordered by exp → flow → step                           │
│                                                             │
│  models.py (ExpStep)                                       │
│  ├─ parent = ForeignKey('self')  [unchanged]               │
│  └─ @property step_num:                                    │
│      └─ Count only same-flow parents                       │
│                                                             │
│  views.py                                                  │
│  └─ Passes flow context to form [unchanged]                │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│                       DATABASE                             │
├────────────────────────────────────────────────────────────┤
│  ExpStep table                                             │
│  ├─ id (PK)                                                │
│  ├─ step_name (e.g., "AA")                                 │
│  ├─ step_number (e.g., "00")                               │
│  ├─ full_step (computed, e.g., "MLO001AA-AA00")            │
│  ├─ parent_id (FK to ExpStep) ← Can be ANY step!          │
│  ├─ flow_id (FK to ExpFlow)                                │
│  └─ ... (other fields)                                     │
│                                                             │
│  Note: step_num is NOT stored, computed on-the-fly         │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                    EXTERNAL LIBRARIES                      │
├────────────────────────────────────────────────────────────┤
│  Select2 4.1.0       ← Searchable dropdown                 │
│  jQuery 3.7.0        ← Required by Select2                 │
│  Bootstrap 5.3.0     ← UI framework                        │
└────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

✅ **Flexibility**: Can now reference steps from any experiment  
✅ **Usability**: Searchable dropdown makes finding steps easy  
✅ **Accuracy**: Step numbers reflect position within each flow  
✅ **Compatibility**: No database changes, existing data works  
✅ **Performance**: Efficient queries with select_related()  

🎯 **Use Cases**:
- Reference cleaning steps from standard experiments
- Build on previous lithography work
- Create process flows that span multiple projects
- Track complex dependencies between experiments
