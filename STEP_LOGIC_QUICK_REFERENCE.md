# Step Logic Modifications - Quick Reference

## 🎯 What Changed?

### 1️⃣ Previous Step Selection
**Before:** Could only select parent from the same flow  
**After:** Can select **ANY step from ANY experiment** (with searchable dropdown)

### 2️⃣ Step Number Calculation  
**Before:** Counted ALL parents in the chain  
**After:** Counts **ONLY parents within the same flow**

---

## 💡 How It Works

### Previous Step (Parent) Selection

```
┌─────────────────────────────────────────────┐
│  Previous Step (Any Experiment)             │
│  ┌────────────────────────────────────────┐ │
│  │ 🔍 Search for a previous step...       │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │ MLO001AA-AA00                          │ │
│  │ MLO001AA-BB00                          │ │
│  │ MLO001MX-CV00                          │ │
│  │ MLO002BB-AA00                          │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

**Features:**
- Type to search across all experiments/flows/steps
- Results update in real-time
- Shows full step names (e.g., `MLO001AA-AA00`)
- Can select from thousands of steps easily
- Click × to clear selection

---

## 📊 Step Numbering Examples

### Example 1: All Steps in Same Flow
```
Flow: MLO001AA
┌─────────────────────────────────┐
│ Step AA (no parent)             │ → step_num = 00
│   ↓                             │
│ Step BB (parent: AA in MLO001AA)│ → step_num = 01
│   ↓                             │
│ Step CC (parent: BB in MLO001AA)│ → step_num = 02
└─────────────────────────────────┘
```

### Example 2: Parent from Different Flow
```
Flow: MLO001MX
┌─────────────────────────────────┐
│ Step AA (no parent)             │ → step_num = 00
│   ↓                             │
│ Step BB (parent: AA in MLO001MX)│ → step_num = 01
│                                 │
│ Step CV ───→ parent in MLO001AA │ → step_num = 00 ⚠️
│            (different flow!)    │    (external parent not counted)
└─────────────────────────────────┘
```

### Example 3: Mixed Parent Chain
```
┌──────────────────────────────────────────────────┐
│ Flow: MLO001AA         Flow: MLO002BB            │
│ ┌──────────┐           ┌──────────┐             │
│ │ Step CC  │           │ Step AA  │─┐           │
│ └────┬─────┘           └──────────┘ │           │
│      │                               │ step_num=00
│      │ (external parent)             │ (doesn't count)
│      └───────────────────────────────┘           │
│                         ┌──────────┐             │
│                         │ Step BB  │─┐           │
│                         └──────────┘ │ step_num=01
│                                      │ (counts!)
│                         ┌──────────┐ │           │
│                         │ Step CC  │←┘           │
│                         └──────────┘             │
│                          step_num=02             │
└──────────────────────────────────────────────────┘

Chain for MLO002BB-CC:
CC → BB (same flow ✅ count)
  → AA (same flow ✅ count)
    → MLO001AA-CC (different flow ❌ don't count)

Final step_num = 02
```

---

## ✅ Benefits

| Feature | Benefit |
|---------|---------|
| **Cross-experiment parents** | Model complex workflows spanning multiple projects |
| **Searchable dropdown** | Find steps quickly even with hundreds of steps |
| **Flow-scoped numbering** | Accurate step position within each flow |
| **No data migration** | Changes are logic-only, existing data untouched |
| **Flexible dependencies** | Reference previous work without duplication |

---

## 🧪 Testing Checklist

- [ ] Create step with external parent → verify step_num = 00
- [ ] Create step chain in same flow → verify step_num increments
- [ ] Search for step in dropdown → verify filtering works
- [ ] Select step from different experiment → verify it saves
- [ ] Edit existing step → verify parent field is searchable
- [ ] Clear parent selection → verify it works

---

## 🚀 Usage Instructions

### Adding a Step with Previous Step

1. Click the **+** button next to a flow
2. Fill in step name
3. Click in **"Previous Step (Any Experiment)"** field
4. Type to search (e.g., type "MLO001" to find all MLO001 steps)
5. Click to select the desired previous step
6. Fill in other fields
7. Click **"Add Step"**

### Understanding Step Numbers

- **Step_num** shows how many steps came before in **this flow only**
- Steps from other flows don't increment the counter
- First step in a flow is always `00`
- Chain only counts same-flow parents

---

## 📝 Technical Notes

**Libraries Added:**
- Select2 4.1.0 (searchable dropdown)
- jQuery 3.7.0 (Select2 dependency)

**Modified Files:**
- `models.py` - Updated `step_num` calculation
- `forms.py` - Changed parent queryset to all steps
- `base.html` - Added Select2 CDN links
- `experiment_detail.html` - Added Select2 initialization
- `add_step.html` - Updated labels
- `edit_step.html` - Updated labels

**Performance:**
- Parent field uses `select_related()` for efficient queries
- Dropdown loads all steps but filters client-side (fast with Select2)
- Step_num calculated on-the-fly (not stored, always current)

---

## 🔗 Related Documentation

See `STEP_LOGIC_UPDATE.md` for detailed technical implementation notes.
