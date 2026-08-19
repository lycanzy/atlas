"""Raw-material inventory calculations and validation.

Inventory is derived from the material batch total and step usages.  No
mutable balance is stored, which keeps the displayed balance reproducible.
"""

import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from .models import RawMaterial, StepRawMaterialUsage


ZERO = Decimal('0')
DECIMAL_OUTPUT = DecimalField(max_digits=18, decimal_places=4)


class RawMaterialUsageValidationError(ValidationError):
    pass


def inventory_ready(material):
    return material.total_quantity is not None and bool((material.total_unit or '').strip())


def inventory_state(total, remaining, ready=True):
    if not ready:
        return 'unknown'
    if remaining <= ZERO:
        return 'critical'
    if total > ZERO and remaining / total <= Decimal('0.20'):
        return 'low'
    return 'normal'


def inventory_totals(material_ids=None):
    usages = StepRawMaterialUsage.objects.all()
    if material_ids is not None:
        usages = usages.filter(raw_material_id__in=material_ids)
    rows = usages.values('raw_material_id').annotate(
        completed_quantity=Coalesce(
            Sum('quantity', filter=Q(step__status='Completed')),
            Value(ZERO), output_field=DECIMAL_OUTPUT,
        ),
        planned_quantity=Coalesce(
            Sum('quantity', filter=Q(step__status='Planned')),
            Value(ZERO), output_field=DECIMAL_OUTPUT,
        ),
    )
    return {
        row['raw_material_id']: {
            'completed_quantity': row['completed_quantity'] or ZERO,
            'planned_quantity': row['planned_quantity'] or ZERO,
        }
        for row in rows
    }


def inventory_summary(material, totals=None):
    totals = totals or {}
    completed = totals.get('completed_quantity', ZERO)
    planned = totals.get('planned_quantity', ZERO)
    ready = inventory_ready(material)
    total = material.total_quantity if ready else None
    remaining = total - completed if ready else None
    projected = remaining - planned if ready else None
    return {
        'completed_quantity': completed,
        'planned_quantity': planned,
        'remaining_quantity': remaining,
        'projected_remaining_quantity': projected,
        'inventory_ready': ready,
        'inventory_state': inventory_state(total, remaining, ready),
    }


def attach_inventory_summaries(materials):
    materials = list(materials)
    totals_by_id = inventory_totals([material.id for material in materials])
    for material in materials:
        for name, value in inventory_summary(material, totals_by_id.get(material.id)).items():
            setattr(material, name, value)
    return materials


def parse_usage_payload(payload_json, existing_step=None):
    try:
        payload = json.loads(payload_json or '[]')
    except (TypeError, json.JSONDecodeError) as exc:
        raise RawMaterialUsageValidationError('原材料用量数据格式无效。') from exc
    if not isinstance(payload, list):
        raise RawMaterialUsageValidationError('原材料用量数据格式无效。')

    existing = {}
    if existing_step and existing_step.pk:
        existing = {
            usage.raw_material_id: usage
            for usage in existing_step.raw_material_usages.select_related('raw_material')
        }

    parsed = []
    seen = set()
    for item in payload:
        try:
            material_id = int(item.get('raw_material_id'))
        except (AttributeError, TypeError, ValueError) as exc:
            raise RawMaterialUsageValidationError('请选择有效的原材料批次。') from exc
        if material_id in seen:
            raise RawMaterialUsageValidationError('同一步骤不能重复登记同一原材料批次。')
        seen.add(material_id)
        try:
            material = RawMaterial.objects.get(pk=material_id)
        except RawMaterial.DoesNotExist as exc:
            raise RawMaterialUsageValidationError('所选原材料不存在。') from exc

        raw_quantity = item.get('quantity')
        try:
            quantity = Decimal(str(raw_quantity))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RawMaterialUsageValidationError(f'原材料 {material.batch_number} 必须填写有效用量。') from exc
        if quantity <= ZERO:
            raise RawMaterialUsageValidationError(f'原材料 {material.batch_number} 的用量必须大于 0。')

        supplied_unit = (item.get('unit') or '').strip()
        expected_unit = (material.total_unit or '').strip()
        old_usage = existing.get(material_id)
        if not inventory_ready(material):
            unchanged_legacy = bool(
                old_usage
                and old_usage.quantity == quantity
                and (old_usage.unit or '').strip() == supplied_unit
            )
            if not unchanged_legacy:
                raise RawMaterialUsageValidationError(
                    f'原材料 {material.batch_number} 缺少总量或固定单位，请先补齐库存资料。'
                )
        elif not material.is_active and material_id not in existing:
            raise RawMaterialUsageValidationError(f'原材料 {material.batch_number} 已停用，不能新增使用。')
        elif supplied_unit and supplied_unit != expected_unit:
            raise RawMaterialUsageValidationError(
                f'原材料 {material.batch_number} 的用量单位必须为 {expected_unit}。'
            )

        parsed.append({
            'raw_material': material,
            'quantity': quantity,
            'unit': expected_unit or supplied_unit,
            'notes': (item.get('notes') or '').strip() or None,
        })
    return parsed


def replace_step_usages(step, parsed_usages):
    StepRawMaterialUsage.objects.filter(step=step).delete()
    StepRawMaterialUsage.objects.bulk_create([
        StepRawMaterialUsage(
            step=step,
            raw_material=item['raw_material'],
            quantity=item['quantity'],
            unit=item['unit'],
            notes=item['notes'],
        )
        for item in parsed_usages
    ])


def validate_usage_records_for_completion(usages):
    errors = []
    for usage in usages:
        material = usage.raw_material if hasattr(usage, 'raw_material') else usage['raw_material']
        quantity = usage.quantity if hasattr(usage, 'quantity') else usage['quantity']
        unit = usage.unit if hasattr(usage, 'unit') else usage['unit']
        if not inventory_ready(material):
            errors.append(f'{material.batch_number} 缺少总量或固定单位')
        elif quantity is None or quantity <= ZERO:
            errors.append(f'{material.batch_number} 缺少有效用量')
        elif (unit or '').strip() != (material.total_unit or '').strip():
            errors.append(f'{material.batch_number} 的用量单位必须为 {material.total_unit}')
    if errors:
        raise RawMaterialUsageValidationError('；'.join(errors) + '。')


def completed_usage_delta(old_status, old_usages, new_status, new_usages):
    delta = defaultdict(lambda: ZERO)
    if old_status == 'Completed':
        for item in old_usages:
            material_id = getattr(item, 'raw_material_id', None) or item['raw_material'].id
            quantity = item.quantity if hasattr(item, 'quantity') else item['quantity']
            delta[material_id] -= quantity or ZERO
    if new_status == 'Completed':
        for item in new_usages:
            material_id = getattr(item, 'raw_material_id', None) or item['raw_material'].id
            quantity = item.quantity if hasattr(item, 'quantity') else item['quantity']
            delta[material_id] += quantity or ZERO
    return {material_id: quantity for material_id, quantity in delta.items() if quantity}


def negative_inventory_shortages(deltas=None, total_overrides=None):
    deltas = deltas or {}
    total_overrides = total_overrides or {}
    material_ids = set(deltas) | set(total_overrides)
    if not material_ids:
        return []

    materials = {
        material.id: material
        for material in RawMaterial.objects.select_for_update().filter(id__in=material_ids)
    }
    totals_by_id = inventory_totals(material_ids)
    shortages = []
    for material_id in sorted(material_ids):
        material = materials.get(material_id)
        if not material:
            continue
        proposed_total = total_overrides.get(material_id, material.total_quantity)
        if proposed_total is None:
            continue
        completed = totals_by_id.get(material_id, {}).get('completed_quantity', ZERO)
        current_remaining = (
            material.total_quantity - completed
            if material.total_quantity is not None else None
        )
        after_remaining = proposed_total - completed - deltas.get(material_id, ZERO)
        if after_remaining < ZERO and (
            current_remaining is None or after_remaining < current_remaining
        ):
            shortages.append({
                'raw_material_id': material.id,
                'batch_number': material.batch_number,
                'total_quantity': str(proposed_total),
                'current_remaining': str(current_remaining) if current_remaining is not None else '',
                'remaining_after': str(after_remaining),
                'shortage': str(-after_remaining),
                'unit': material.total_unit or '',
            })
    return shortages


def shortage_response(shortages):
    return {
        'success': False,
        'error': '该操作将导致原材料库存为负，请确认后继续。',
        'requires_confirmation': True,
        'shortages': shortages,
    }


def allows_negative(value):
    return value in (True, 1, '1', 'true', 'True', 'on', 'yes')
