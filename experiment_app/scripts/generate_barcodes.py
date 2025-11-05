"""
Script to generate barcodes for existing ExpFlow and ExpStep objects that don't have barcodes yet.
Run this with: python manage.py shell < scripts/generate_barcodes.py
"""

from experiment_flow.models import ExpFlow, ExpStep

# Generate barcodes for existing flows
flows_without_barcode = ExpFlow.objects.filter(barcode__isnull=True)
count_flows = 0
for flow in flows_without_barcode:
    barcode_id = f"F{flow.id:06d}"
    flow.barcode = barcode_id
    flow.save(update_fields=['barcode'])
    count_flows += 1
    print(f"Generated barcode for flow {flow.full_flow}: {barcode_id}")

# Generate barcodes for existing steps
steps_without_barcode = ExpStep.objects.filter(barcode__isnull=True)
count_steps = 0
for step in steps_without_barcode:
    barcode_id = f"S{step.id:06d}"
    step.barcode = barcode_id
    step.save(update_fields=['barcode'])
    count_steps += 1
    print(f"Generated barcode for step {step.full_step}: {barcode_id}")

print(f"\nSummary:")
print(f"- Generated {count_flows} flow barcodes")
print(f"- Generated {count_steps} step barcodes")
print(f"- Total: {count_flows + count_steps} barcodes generated")
