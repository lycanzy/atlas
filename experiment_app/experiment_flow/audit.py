"""Centralized, request-aware business audit logging."""

from datetime import date, datetime
from decimal import Decimal
from ipaddress import ip_address

from django.db.models import Model

from .models import AuditLog


SENSITIVE_KEYS = {
    'password', 'password1', 'password2', 'old_password', 'new_password1',
    'new_password2', 'token', 'authorization', 'cookie', 'session',
    'sessionid', 'csrfmiddlewaretoken',
}


def _safe_value(value):
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Model):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def changed_values(before, after):
    return {
        field: {'before': _safe_value(before.get(field)), 'after': _safe_value(value)}
        for field, value in after.items()
        if _safe_value(before.get(field)) != _safe_value(value)
    }


def model_snapshot(instance, fields):
    snapshot = {}
    for field in fields:
        value = getattr(instance, field)
        if isinstance(value, Model):
            value = getattr(value, 'username', str(value))
        snapshot[field] = _safe_value(value)
    return snapshot


def raw_material_usage_snapshot(step):
    return [
        {
            'material_id': usage.raw_material_id,
            'material_code': usage.raw_material.material_code,
            'batch_number': usage.raw_material.batch_number,
            'quantity': _safe_value(usage.quantity),
            'unit': usage.unit or '',
            'notes': usage.notes or '',
        }
        for usage in step.raw_material_usages.select_related('raw_material').order_by('raw_material_id')
    ]


def step_snapshot(step):
    return {
        'step_code': step.full_step or str(step),
        'step_name': step.step_name,
        'description': step.step_description or '',
        'parents': list(step.parents.order_by('full_step').values_list('full_step', flat=True)),
        'status': step.status,
        'completed_on': _safe_value(step.completed_on),
        'equipment': step.tool.equipment_id if step.tool else '',
        'recipe': step.recipe or '',
        'notes': step.notes or '',
        'sample_count': step.samples.count(),
        'samples': list(step.samples.order_by('sample_number', 'id').values('id', 'sample_number', 'sample_name')),
        'cell_count': step.cells.count(),
        'cells': list(step.cells.order_by('package_number', 'barcode', 'id').values(
            'id', 'package_number', 'barcode', 'test_item_id', 'test_item__name',
        )),
        'raw_material_usages': raw_material_usage_snapshot(step),
    }


EQUIPMENT_FIELDS = (
    'equipment_id', 'equipment_name', 'owner', 'location', 'is_active',
    'description', 'size', 'power_requirement', 'voltage', 'current',
    'water_requirement', 'gas_input', 'exhaust_requirement',
)
RAW_MATERIAL_FIELDS = (
    'material_code', 'batch_number', 'received_date', 'material_name',
    'material_type', 'total_quantity', 'total_unit', 'owner', 'supplier', 'location', 'is_active',
    'description', 'notes',
)


def record_audit_event(
    request, action, category, summary, instance=None, changes=None,
    object_repr=None, object_id=None, entity_type=None, outcome='success',
    actor_username=None,
):
    user = getattr(request, 'user', None)
    actor = user if getattr(user, 'is_authenticated', False) else None
    if actor_username is None:
        actor_username = getattr(actor, 'username', '')
    team = ''
    if actor:
        profile = getattr(actor, 'profile', None)
        team = str(getattr(profile, 'research_group', '') or '')
    if instance is not None:
        entity_type = entity_type or instance._meta.verbose_name.title()
        object_id = str(instance.pk or '') if object_id is None else object_id
        object_repr = object_repr or str(instance)
    direct_ip = request.META.get('REMOTE_ADDR') or None
    try:
        direct_ip = str(ip_address(direct_ip)) if direct_ip else None
    except ValueError:
        direct_ip = None
    return AuditLog.objects.create(
        actor=actor,
        actor_username=(actor_username or '')[:150],
        actor_team=team[:100],
        category=category,
        action=action,
        outcome=outcome,
        entity_type=(entity_type or '')[:50],
        object_id=str(object_id or '')[:64],
        object_repr=str(object_repr or '')[:200],
        summary=str(summary)[:500],
        changes=_safe_value(changes or {}),
        request_path=getattr(request, 'path', '')[:255],
        request_method=getattr(request, 'method', '')[:10],
        ip_address=direct_ip,
    )


def record_permission_denied(request, category, summary, instance=None, **kwargs):
    return record_audit_event(
        request, 'permission_denied', category, summary, instance=instance,
        outcome='denied', **kwargs,
    )
