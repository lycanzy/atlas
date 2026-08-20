from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, IntegerField, Prefetch, Q, Value, When
from django.db.models.functions import Trim
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import AuditLog, Cell, CellTestItem, Project, Experiment, ExperimentStep, ExperimentStepLink, ProjectCategory, ResearchGroup, UserProfile, Sample, StepNameTemplate, Equipment, RawMaterial, RawMaterialType, StepRawMaterialUsage
from .forms import ExperimentStepForm, ExperimentForm, EquipmentForm, RawMaterialForm, CustomPasswordChangeForm, TeamManagementForm, ProjectManagementForm, ProjectCreateForm, ManagedUserForm, MemberTeamForm, StepTemplateManagementForm, RawMaterialTypeManagementForm, CellTestItemManagementForm
import json
import string
from urllib.parse import urlencode
from functools import wraps
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.utils.dateparse import parse_date
from .audit import (
    EQUIPMENT_FIELDS, RAW_MATERIAL_FIELDS, changed_values, model_snapshot,
    record_audit_event as write_audit_event, record_permission_denied,
    step_snapshot,
)
from .inventory import (
    allows_negative, attach_inventory_summaries, completed_usage_delta,
    inventory_ready, inventory_summary, inventory_totals, negative_inventory_shortages,
    parse_usage_payload, replace_step_usages, shortage_response,
    validate_usage_records_for_completion, RawMaterialUsageValidationError,
)


STATUS_LABELS_ZH = {
    'Planned': '计划中',
    'Completed': '已完成',
    'Canceled': '已取消',
}


_management_access = user_passes_test(
    lambda user: user.is_authenticated and (user.is_staff or user.is_superuser),
    login_url='index',
)


def management_required(view_func):
    protected_view = _management_access(view_func)

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated and not (request.user.is_staff or request.user.is_superuser):
            record_permission_denied(
                request, 'management', '拒绝访问管理中心',
                entity_type='Management Center', object_repr='管理中心',
            )
        return protected_view(request, *args, **kwargs)

    return wrapped


def record_audit_event(request, action, instance, summary, changes=None, object_repr=None, category=None, **kwargs):
    """Compatibility wrapper for management operations using the audit service."""
    if category is None:
        category = {
            'Project': 'project', 'User': 'member',
        }.get(instance.__class__.__name__, 'management')
    return write_audit_event(
        request, action, category, summary, instance=instance,
        changes=changes, object_repr=object_repr, **kwargs,
    )


@login_required
def insights(request):
    """Render the read-only data insights workspace.

    The first release is intentionally frontend-only: no SQL or model request is
    executed by this view.
    """
    return render(request, 'experiment_flow/insights.html')


@management_required
def management_dashboard(request):
    teams = ResearchGroup.objects.prefetch_related('members__user').order_by('group_name')
    projects = Project.objects.select_related('project__group', 'owner').order_by('-created_on')
    users = User.objects.select_related('profile__research_group').order_by('username')
    step_templates = StepNameTemplate.objects.order_by('category', 'step_code')
    raw_material_types = list(RawMaterialType.objects.order_by('name'))
    cell_test_items = list(CellTestItem.objects.annotate(usage_count=Count('cells')).order_by('name'))
    material_type_usage_counts = dict(
        RawMaterial.objects.exclude(material_type__isnull=True)
        .exclude(material_type='')
        .values('material_type')
        .annotate(count=Count('id'))
        .values_list('material_type', 'count')
    )
    for material_type in raw_material_types:
        material_type.usage_count = material_type_usage_counts.get(material_type.name, 0)
    cells = Cell.objects.select_related(
        'test_item', 'step__experiment__project__project__group',
    ).order_by('package_number', 'barcode', 'id')
    cell_q = request.GET.get('cell_q', '').strip()
    if cell_q:
        cells = cells.filter(
            Q(package_number__icontains=cell_q) |
            Q(barcode__icontains=cell_q) |
            Q(test_item__name__icontains=cell_q) |
            Q(step__full_step__icontains=cell_q) |
            Q(step__experiment__full_experiment_code__icontains=cell_q) |
            Q(step__experiment__project__exp_name__icontains=cell_q) |
            Q(step__experiment__project__project__group__team_code__icontains=cell_q) |
            Q(step__experiment__project__project__group__group_name__icontains=cell_q)
        )
    cell_page_obj = Paginator(cells, 50).get_page(request.GET.get('cell_page', 1))
    audit_logs = AuditLog.objects.select_related('actor')
    audit_q = request.GET.get('audit_q', '').strip()
    audit_actor = request.GET.get('audit_actor', '').strip()
    audit_team = request.GET.get('audit_team', '').strip()
    audit_category = request.GET.get('audit_category', '').strip()
    audit_action = request.GET.get('audit_action', '').strip()
    audit_outcome = request.GET.get('audit_outcome', '').strip()
    audit_from = request.GET.get('audit_from', '').strip()
    audit_to = request.GET.get('audit_to', '').strip()
    if audit_q:
        audit_logs = audit_logs.filter(
            Q(actor_username__icontains=audit_q) | Q(entity_type__icontains=audit_q) |
            Q(object_repr__icontains=audit_q) | Q(summary__icontains=audit_q)
        )
    if audit_actor:
        audit_logs = audit_logs.filter(actor_username__icontains=audit_actor)
    if audit_team:
        audit_logs = audit_logs.filter(actor_team__icontains=audit_team)
    if audit_category:
        audit_logs = audit_logs.filter(category=audit_category)
    if audit_action:
        audit_logs = audit_logs.filter(action=audit_action)
    if audit_outcome:
        audit_logs = audit_logs.filter(outcome=audit_outcome)
    if parse_date(audit_from):
        audit_logs = audit_logs.filter(created_on__date__gte=parse_date(audit_from))
    if parse_date(audit_to):
        audit_logs = audit_logs.filter(created_on__date__lte=parse_date(audit_to))
    audit_page_obj = Paginator(audit_logs, 50).get_page(request.GET.get('audit_page', 1))
    audit_query = request.GET.copy()
    audit_query.pop('audit_page', None)
    return render(request, 'experiment_flow/management_dashboard.html', {
        'teams': teams,
        'managed_projects': projects,
        'managed_users': users,
        'step_templates': step_templates,
        'raw_material_types': raw_material_types,
        'cell_test_items': cell_test_items,
        'managed_cells': cell_page_obj,
        'cell_page_obj': cell_page_obj,
        'cell_q': cell_q,
        'cell_query_without_page': urlencode({'cell_q': cell_q}) if cell_q else '',
        'audit_logs': audit_page_obj,
        'audit_page_obj': audit_page_obj,
        'audit_query_without_page': audit_query.urlencode(),
        'audit_filters': {
            'q': audit_q, 'actor': audit_actor, 'team': audit_team,
            'category': audit_category, 'action': audit_action,
            'outcome': audit_outcome, 'from': audit_from, 'to': audit_to,
        },
        'audit_categories': AuditLog.CATEGORY_CHOICES,
        'audit_actions': AuditLog.ACTION_CHOICES,
        'audit_outcomes': AuditLog.OUTCOME_CHOICES,
        'team_form': TeamManagementForm(),
        'project_create_form': ProjectCreateForm(),
        'member_form': ManagedUserForm(),
        'step_template_form': StepTemplateManagementForm(),
        'raw_material_type_form': RawMaterialTypeManagementForm(),
        'cell_test_item_form': CellTestItemManagementForm(),
    })


def management_redirect(tab):
    return redirect(f"{reverse('management_dashboard')}#{tab}")


@management_required
@transaction.atomic
def add_team(request):
    if request.method == 'POST':
        form = TeamManagementForm(request.POST)
        if form.is_valid():
            team = form.save()
            ProjectCategory.objects.get_or_create(
                group=team,
                defaults={'project_name': team.group_name, 'project_code': team.team_code},
            )
            record_audit_event(
                request, 'create', team, f'创建 Team {team}',
                {'group_name': {'before': None, 'after': team.group_name},
                 'team_code': {'before': None, 'after': team.team_code}},
            )
            messages.success(request, f'Team {team} 已创建。')
        else:
            messages.error(request, 'Team 创建失败：' + ' '.join(form.non_field_errors() or [str(form.errors)]))
    return management_redirect('teams')


@management_required
@transaction.atomic
def edit_team(request, team_id):
    team = get_object_or_404(ResearchGroup, id=team_id)
    if request.method == 'POST':
        old_code = team.team_code
        before = {'group_name': team.group_name, 'team_code': team.team_code}
        form = TeamManagementForm(request.POST, instance=team)
        if form.is_valid():
            team = form.save()
            category = ProjectCategory.objects.filter(group=team).order_by('id').first()
            if category and category.project_code == old_code:
                category.project_code = team.team_code
                category.save(update_fields=['project_code'])
            changes = changed_values(before, {
                'group_name': team.group_name,
                'team_code': team.team_code,
            })
            record_audit_event(request, 'update', team, f'修改 Team {team}', changes)
            messages.success(request, f'Team {team} 已更新。')
        else:
            messages.error(request, 'Team 更新失败：' + str(form.errors))
    return management_redirect('teams')


@management_required
@transaction.atomic
def delete_team(request, team_id):
    team = get_object_or_404(ResearchGroup, id=team_id)
    if request.method == 'POST':
        name = str(team)
        record_audit_event(
            request, 'delete', team, f'删除 Team {name}', object_repr=name,
            changes={'snapshot': model_snapshot(team, ('group_name', 'team_code'))},
        )
        team.delete()
        messages.success(request, f'Team {name} 已删除。')
    return management_redirect('teams')


@management_required
@transaction.atomic
def assign_member_team(request, user_id):
    member = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        before_team = str(getattr(getattr(member, 'profile', None), 'research_group', '') or '')
        form = MemberTeamForm(request.POST)
        if form.is_valid():
            profile, _ = UserProfile.objects.get_or_create(user=member)
            profile.research_group = form.cleaned_data['research_group']
            profile.save(update_fields=['research_group'])
            after_team = str(profile.research_group or '')
            record_audit_event(
                request, 'update', member, f'修改成员 {member.username} 的 Team',
                changed_values({'team': before_team}, {'team': after_team}),
            )
            messages.success(request, f'{member.username} 的 Team 已更新。')
    return management_redirect('members')


@management_required
@transaction.atomic
def edit_managed_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        before = {
            'description': project.exp_description or '',
            'owner': project.owner.username,
        }
        form = ProjectManagementForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            changes = changed_values(before, {
                'description': project.exp_description or '',
                'owner': project.owner.username,
            })
            record_audit_event(request, 'update', project, f'修改项目 {project.exp_name}', changes)
            messages.success(request, f'项目 {project.exp_name} 已更新。')
        else:
            messages.error(request, '项目更新失败：' + str(form.errors))
    return management_redirect('projects')


@management_required
@transaction.atomic
def add_managed_project(request):
    if request.method == 'POST':
        form = ProjectCreateForm(request.POST)
        if form.is_valid():
            team = form.cleaned_data['team']
            category = ProjectCategory.objects.filter(group=team).order_by('id').first()
            if not category:
                category = ProjectCategory.objects.create(
                    group=team, project_name=team.group_name, project_code=team.team_code,
                )
            project = Project.objects.create(
                exp_name=category.generate_experiment_name(),
                exp_description=form.cleaned_data['exp_description'],
                project=category,
                owner=form.cleaned_data['owner'],
            )
            record_audit_event(
                request, 'create', project, f'创建项目 {project.exp_name}',
                {'team': {'before': None, 'after': str(team)},
                 'owner': {'before': None, 'after': project.owner.username},
                 'description': {'before': None, 'after': project.exp_description or ''}},
            )
            messages.success(request, f'项目 {project.exp_name} 已创建。')
        else:
            messages.error(request, '项目创建失败：' + str(form.errors))
    return management_redirect('projects')


@management_required
@transaction.atomic
def delete_managed_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        name = project.exp_name
        record_audit_event(
            request, 'delete', project, f'删除项目 {name}', object_repr=name,
            changes={'snapshot': model_snapshot(project, ('exp_name', 'exp_description', 'owner'))},
        )
        project.delete()
        messages.success(request, f'项目 {name} 已删除。')
    return management_redirect('projects')


@management_required
@transaction.atomic
def add_managed_user(request):
    if request.method == 'POST':
        form = ManagedUserForm(request.POST)
        if form.is_valid():
            member = form.save()
            record_audit_event(
                request, 'create', member, f'创建成员 {member.username}',
                {'username': {'before': None, 'after': member.username},
                 'team': {'before': None, 'after': str(member.profile.research_group or '')},
                 'is_active': {'before': None, 'after': member.is_active},
                 'is_staff': {'before': None, 'after': member.is_staff}},
            )
            messages.success(request, f'成员 {member.username} 已创建。')
        else:
            messages.error(request, '成员创建失败：' + str(form.errors))
    return management_redirect('members')


@management_required
@transaction.atomic
def edit_managed_user(request, user_id):
    member = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        before = {
            'username': member.username,
            'first_name': member.first_name,
            'last_name': member.last_name,
            'email': member.email,
            'team': str(getattr(getattr(member, 'profile', None), 'research_group', '') or ''),
            'is_active': member.is_active,
            'is_staff': member.is_staff,
        }
        form = ManagedUserForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            changes = changed_values(before, {
                'username': member.username,
                'first_name': member.first_name,
                'last_name': member.last_name,
                'email': member.email,
                'team': str(member.profile.research_group or ''),
                'is_active': member.is_active,
                'is_staff': member.is_staff,
            })
            if form.cleaned_data.get('password'):
                changes['password'] = {'before': '********', 'after': '********（已更新）'}
            record_audit_event(request, 'update', member, f'修改成员 {member.username}', changes)
            messages.success(request, f'成员 {member.username} 已更新。')
        else:
            messages.error(request, '成员更新失败：' + str(form.errors))
    return management_redirect('members')


@management_required
@transaction.atomic
def delete_managed_user(request, user_id):
    member = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        if member == request.user:
            messages.error(request, '不能删除当前登录账号。')
        elif member.is_superuser and not request.user.is_superuser:
            messages.error(request, '只有超级管理员可以删除超级管理员账号。')
        else:
            username = member.username
            record_audit_event(
                request, 'delete', member, f'删除成员 {username}', object_repr=username,
                changes={'snapshot': model_snapshot(
                    member, ('username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff'),
                )},
            )
            member.delete()
            messages.success(request, f'成员 {username} 已删除。')
    return management_redirect('members')


@management_required
@transaction.atomic
def add_step_template(request):
    if request.method == 'POST':
        form = StepTemplateManagementForm(request.POST)
        if form.is_valid():
            template = form.save()
            record_audit_event(
                request, 'create', template, f'创建步骤模板 {template}',
                {'step_code': {'before': None, 'after': template.step_code},
                 'step_label': {'before': None, 'after': template.step_label},
                 'is_active': {'before': None, 'after': template.is_active}},
            )
            messages.success(request, f'步骤模板 {template} 已创建。')
        else:
            messages.error(request, '步骤模板创建失败：' + str(form.errors))
    return management_redirect('steps')


@management_required
@transaction.atomic
def edit_step_template(request, template_id):
    template = get_object_or_404(StepNameTemplate, id=template_id)
    if request.method == 'POST':
        before = {
            'step_code': template.step_code,
            'step_label': template.step_label,
            'category': template.category or '',
            'default_description': template.default_description or '',
            'is_active': template.is_active,
        }
        form = StepTemplateManagementForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            changes = changed_values(before, {
                'step_code': template.step_code,
                'step_label': template.step_label,
                'category': template.category or '',
                'default_description': template.default_description or '',
                'is_active': template.is_active,
            })
            record_audit_event(request, 'update', template, f'修改步骤模板 {template}', changes)
            messages.success(request, f'步骤模板 {template} 已更新。')
        else:
            messages.error(request, '步骤模板更新失败：' + str(form.errors))
    return management_redirect('steps')


@management_required
@transaction.atomic
def delete_step_template(request, template_id):
    template = get_object_or_404(StepNameTemplate, id=template_id)
    if request.method == 'POST':
        name = str(template)
        record_audit_event(
            request, 'delete', template, f'删除步骤模板 {name}', object_repr=name,
            changes={'snapshot': model_snapshot(
                template, ('step_code', 'step_label', 'category', 'default_description', 'is_active'),
            )},
        )
        template.delete()
        messages.success(request, f'步骤模板 {name} 已删除。')
    return management_redirect('steps')


@management_required
@transaction.atomic
def add_raw_material_type(request):
    if request.method == 'POST':
        form = RawMaterialTypeManagementForm(request.POST)
        if form.is_valid():
            material_type = form.save()
            record_audit_event(
                request, 'create', material_type, f'创建原材料种类 {material_type}',
                {'name': {'before': None, 'after': material_type.name},
                 'is_active': {'before': None, 'after': material_type.is_active}},
            )
            messages.success(request, f'原材料种类 {material_type} 已创建。')
        else:
            messages.error(request, '原材料种类创建失败：' + str(form.errors))
    return management_redirect('material-types')


@management_required
@transaction.atomic
def edit_raw_material_type(request, type_id):
    material_type = get_object_or_404(RawMaterialType, id=type_id)
    if request.method == 'POST':
        old_name = material_type.name
        before = {
            'name': old_name,
            'description': material_type.description,
            'is_active': material_type.is_active,
        }
        form = RawMaterialTypeManagementForm(request.POST, instance=material_type)
        if form.is_valid():
            material_type = form.save()
            if old_name != material_type.name:
                RawMaterial.objects.filter(material_type=old_name).update(
                    material_type=material_type.name
                )
            changes = changed_values(before, {
                'name': material_type.name,
                'description': material_type.description,
                'is_active': material_type.is_active,
            })
            record_audit_event(
                request, 'update', material_type,
                f'修改原材料种类 {material_type}', changes,
            )
            messages.success(request, f'原材料种类 {material_type} 已更新。')
        else:
            messages.error(request, '原材料种类更新失败：' + str(form.errors))
    return management_redirect('material-types')


@management_required
@transaction.atomic
def delete_raw_material_type(request, type_id):
    material_type = get_object_or_404(RawMaterialType, id=type_id)
    if request.method == 'POST':
        usage_count = RawMaterial.objects.filter(material_type=material_type.name).count()
        if usage_count:
            messages.error(
                request,
                f'原材料种类 {material_type} 已被 {usage_count} 条原材料记录使用，不能删除；可以将其停用。',
            )
        else:
            name = str(material_type)
            record_audit_event(
                request, 'delete', material_type,
                f'删除原材料种类 {name}', object_repr=name,
                changes={'snapshot': model_snapshot(
                    material_type, ('name', 'description', 'is_active'),
                )},
            )
            material_type.delete()
            messages.success(request, f'原材料种类 {name} 已删除。')
    return management_redirect('material-types')


@management_required
@transaction.atomic
def add_cell_test_item(request):
    if request.method == 'POST':
        form = CellTestItemManagementForm(request.POST)
        if form.is_valid():
            test_item = form.save()
            record_audit_event(
                request, 'create', test_item, f'创建电芯测试项目 {test_item}',
                {'name': {'before': None, 'after': test_item.name},
                 'is_active': {'before': None, 'after': test_item.is_active}},
            )
            messages.success(request, f'电芯测试项目 {test_item} 已创建。')
        else:
            messages.error(request, '电芯测试项目创建失败：' + str(form.errors))
    return management_redirect('cell-test-items')


@management_required
@transaction.atomic
def edit_cell_test_item(request, item_id):
    test_item = get_object_or_404(CellTestItem, id=item_id)
    if request.method == 'POST':
        before = model_snapshot(test_item, ('name', 'description', 'is_active'))
        form = CellTestItemManagementForm(request.POST, instance=test_item)
        if form.is_valid():
            test_item = form.save()
            changes = changed_values(
                before, model_snapshot(test_item, ('name', 'description', 'is_active')),
            )
            record_audit_event(
                request, 'update', test_item, f'修改电芯测试项目 {test_item}', changes,
            )
            messages.success(request, f'电芯测试项目 {test_item} 已更新。')
        else:
            messages.error(request, '电芯测试项目更新失败：' + str(form.errors))
    return management_redirect('cell-test-items')


@management_required
@transaction.atomic
def delete_cell_test_item(request, item_id):
    test_item = get_object_or_404(CellTestItem, id=item_id)
    if request.method == 'POST':
        usage_count = test_item.cells.count()
        if usage_count:
            messages.error(
                request,
                f'测试项目 {test_item} 已被 {usage_count} 个电芯使用，不能删除；可以将其停用。',
            )
        else:
            name = str(test_item)
            record_audit_event(
                request, 'delete', test_item, f'删除电芯测试项目 {name}', object_repr=name,
                changes={'snapshot': model_snapshot(
                    test_item, ('name', 'description', 'is_active'),
                )},
            )
            test_item.delete()
            messages.success(request, f'电芯测试项目 {name} 已删除。')
    return management_redirect('cell-test-items')


def step_has_downstream_steps(step):
    """Return True when another step depends on this step."""
    return step.children.exists() or step.child.exists()


def save_step_cells(step, payload_json):
    """Apply explicit cell creates, updates, and deletions for one step."""
    if not payload_json:
        return

    try:
        payload = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError('电芯数据格式无效。') from exc

    if not isinstance(payload, dict):
        raise ValidationError('电芯数据格式无效。')
    records = payload.get('records', [])
    deleted_ids = payload.get('deleted_ids', [])
    if not isinstance(records, list) or not isinstance(deleted_ids, list):
        raise ValidationError('电芯数据格式无效。')

    normalized_records = []
    record_ids = set()
    barcodes = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValidationError('电芯记录格式无效。')
        raw_id = record.get('id')
        if raw_id in (None, ''):
            cell_id = None
        else:
            try:
                cell_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError('电芯记录 ID 无效。') from exc
            if cell_id <= 0 or cell_id in record_ids:
                raise ValidationError('电芯记录 ID 重复或无效。')
            record_ids.add(cell_id)

        package_number = str(record.get('package_number') or '').strip().upper()
        barcode = str(record.get('barcode') or '').strip().upper()
        raw_test_item_id = record.get('test_item_id')
        if raw_test_item_id in (None, ''):
            test_item_id = None
        else:
            try:
                test_item_id = int(raw_test_item_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError('测试项目 ID 无效。') from exc
            if test_item_id <= 0:
                raise ValidationError('测试项目 ID 无效。')
        if not package_number:
            raise ValidationError('每个电芯都必须填写 Package 号。')
        if not barcode:
            raise ValidationError('每个电芯都必须填写 Barcode。')
        if len(package_number) > 100 or len(barcode) > 100:
            raise ValidationError('Package 号和 Barcode 不能超过 100 个字符。')
        if barcode in barcodes:
            raise ValidationError(f'Barcode {barcode} 在本次提交中重复。')
        barcodes.add(barcode)
        normalized_records.append({
            'id': cell_id,
            'package_number': package_number,
            'barcode': barcode,
            'test_item_id': test_item_id,
        })

    requested_test_item_ids = {
        record['test_item_id'] for record in normalized_records if record['test_item_id'] is not None
    }
    valid_test_item_ids = set(
        CellTestItem.objects.filter(id__in=requested_test_item_ids).values_list('id', flat=True)
    )
    if valid_test_item_ids != requested_test_item_ids:
        raise ValidationError('包含不存在的测试项目。')

    normalized_deleted_ids = set()
    for raw_id in deleted_ids:
        try:
            cell_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError('待移除的电芯记录 ID 无效。') from exc
        if cell_id <= 0:
            raise ValidationError('待移除的电芯记录 ID 无效。')
        normalized_deleted_ids.add(cell_id)

    if record_ids & normalized_deleted_ids:
        raise ValidationError('同一电芯不能同时保存和移除。')

    referenced_ids = record_ids | normalized_deleted_ids
    existing_cells = {
        cell.id: cell
        for cell in Cell.objects.select_for_update().filter(
            step=step,
            id__in=referenced_ids,
        )
    }
    if set(existing_cells) != referenced_ids:
        raise ValidationError('包含不属于当前步骤的电芯记录。')

    conflicting_barcodes = set(
        Cell.objects.filter(barcode__in=barcodes)
        .exclude(id__in=referenced_ids)
        .values_list('barcode', flat=True)
    )
    if conflicting_barcodes:
        barcode = sorted(conflicting_barcodes)[0]
        raise ValidationError(f'Barcode {barcode} 已经关联到其他步骤。')

    if normalized_deleted_ids:
        Cell.objects.filter(step=step, id__in=normalized_deleted_ids).delete()

    for record in normalized_records:
        cell_id = record['id']
        if cell_id is None:
            Cell.objects.create(
                step=step,
                package_number=record['package_number'],
                barcode=record['barcode'],
                test_item_id=record['test_item_id'],
            )
            continue

        cell = existing_cells[cell_id]
        if (
            cell.package_number != record['package_number']
            or cell.barcode != record['barcode']
            or cell.test_item_id != record['test_item_id']
        ):
            cell.package_number = record['package_number']
            cell.barcode = record['barcode']
            cell.test_item_id = record['test_item_id']
            cell.save()


def cell_save_error_message(exc):
    if isinstance(exc, ValidationError):
        return ' '.join(exc.messages)
    return 'Barcode 已存在，请检查后重试。'


def cell_save_error_response(request, form, exc):
    message = cell_save_error_message(exc)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'errors': {'cells': [message]},
        }, status=400)
    form.add_error(None, message)
    return None


def raw_material_save_error_response(request, form, exc):
    message = ' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'errors': {'raw_material_usages': [message]},
        }, status=400)
    form.add_error(None, message)
    return None


# Helpe r to return experiments visible to the current user (by research group)
def get_experiments_for_user(user, search_query='', my_experiments=''):
    """Return a queryset of Project filtered to the user's research group.

    Staff and superusers can see all experiments.
    Regular users see only experiments in their research group.
    If the user has no profile or no research_group, return an empty queryset.
    """
    # Staff and superusers can access all experiments
    if user.is_staff or user.is_superuser:
        qs = Project.objects.all().order_by('-created_on')
    else:
        # Regular users: filter by research group
        rg = None
        profile = getattr(user, 'profile', None)
        if profile:
            rg = getattr(profile, 'research_group', None)

        if not rg:
            return Project.objects.none()

        qs = Project.objects.filter(project__group=rg).order_by('-created_on')

    # Filter by owner if requested
    if my_experiments == '1':
        qs = qs.filter(owner=user)

    if search_query:
        qs = qs.filter(
            Q(exp_name__icontains=search_query) |
            Q(exp_description__icontains=search_query) |
            Q(project__project_name__icontains=search_query) |
            Q(project__project_code__icontains=search_query) |
            Q(project__group__team_code__icontains=search_query) |
            Q(project__group__group_name__icontains=search_query) |
            Q(experiments__steps__cells__barcode__icontains=search_query) |
            Q(experiments__steps__cells__package_number__icontains=search_query)
        ).distinct()

    return qs


def get_experiment_overview_stats(experiments_qs):
    experiments = experiments_qs.prefetch_related('experiments__steps')
    total_count = 0
    completed_count = 0

    for experiment in experiments:
        total_count += 1
        project_experiments = list(experiment.experiments.all())
        if not project_experiments:
            continue

        all_experiments_completed = True
        has_any_step = False
        for project_experiment in project_experiments:
            steps = list(project_experiment.steps.all())
            if not steps:
                all_experiments_completed = False
                continue
            has_any_step = True
            if any(step.status != 'Completed' for step in steps):
                all_experiments_completed = False

        if has_any_step and all_experiments_completed:
            completed_count += 1

    in_progress_count = total_count - completed_count
    completion_rate = round((completed_count / total_count) * 100) if total_count else 0
    return {
        'total_count': total_count,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'completion_rate': completion_rate,
    }


def get_experiment_growth_chart(project_experiments_qs, days=14):
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    date_range = [start_date + timedelta(days=offset) for offset in range(days)]
    daily_counts = {day: 0 for day in date_range}
    baseline_count = 0

    for created_on in project_experiments_qs.order_by('created_on').values_list('created_on', flat=True):
        created_day = timezone.localtime(created_on).date()
        if created_day < start_date:
            baseline_count += 1
        elif created_day in daily_counts:
            daily_counts[created_day] += 1

    cumulative_count = baseline_count
    total_count = baseline_count + sum(daily_counts.values())
    max_count = max(total_count, 1)
    points = []

    for index, day in enumerate(date_range):
        cumulative_count += daily_counts[day]
        x = round((index / (days - 1)) * 100, 2) if days > 1 else 0
        y = round(40 - ((cumulative_count / max_count) * 32), 2)
        points.append({
            'date_label': day.strftime('%m/%d'),
            'count': cumulative_count,
            'new_count': daily_counts[day],
            'x': x,
            'y': y,
            'y_percent': round((y / 44) * 100, 2),
        })

    points_attr = ' '.join(f"{point['x']},{point['y']}" for point in points)
    area_points_attr = f"0,44 {points_attr} 100,44" if points_attr else ''
    return {
        'points': points,
        'points_attr': points_attr,
        'area_points_attr': area_points_attr,
        'start_label': date_range[0].strftime('%m/%d'),
        'end_label': date_range[-1].strftime('%m/%d'),
        'current_count': total_count,
    }

# Authentication views
def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            write_audit_event(request, 'login', 'auth', f'用户 {user.username} 登录成功',
                              instance=user, entity_type='认证', object_repr=user.username)
            # Redirect to 'next' parameter if present, otherwise to index
            next_url = request.GET.get('next', 'index')
            return redirect(next_url)
        else:
            write_audit_event(
                request, 'login_failed', 'auth', f'用户名 {username or "（空）"} 登录失败',
                entity_type='认证', object_repr=username or '（空）',
                actor_username=username or '', outcome='failed',
            )
            messages.error(request, '用户名或密码不正确。')

    return render(request, 'experiment_flow/login.html')

def logout_view(request):
    username = request.user.username if request.user.is_authenticated else ''
    if username:
        write_audit_event(request, 'logout', 'auth', f'用户 {username} 退出登录',
                          instance=request.user, entity_type='认证', object_repr=username)
    auth_logout(request)
    messages.success(request, '已成功退出登录。')
    return redirect('login')

@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session auth hash to prevent logout
            update_session_auth_hash(request, user)
            write_audit_event(
                request, 'password_change', 'auth', f'用户 {user.username} 修改密码',
                instance=user, entity_type='认证', object_repr=user.username,
                changes={'password': {'before': '已隐藏', 'after': '已更新'}},
            )
            messages.success(request, '密码已更新。')
            return redirect('index')
        else:
            messages.error(request, '请修正下面的错误。')
    else:
        form = CustomPasswordChangeForm(request.user)

    return render(request, 'experiment_flow/change_password.html', {
        'form': form
    })

# Helper function to generate available experiment codes
def get_available_experiment_codes(experiment):
    """Generate list of available 2-letter codes not used in this experiment"""
    existing_experiments = Experiment.objects.filter(project=experiment).values_list('experiment_code', flat=True)
    existing_experiments_set = set(existing_experiments)

    # Generate all possible 2-letter combinations (AA-ZZ)
    all_codes = [f"{a}{b}" for a in string.ascii_uppercase for b in string.ascii_uppercase]

    # Return codes that are not used
    available_codes = [code for code in all_codes if code not in existing_experiments_set]

    return available_codes


def accessible_description_sources(user):
    """Return permission-scoped Experiments that have a reusable description."""
    return (
        Experiment.objects
        .filter(project__in=get_experiments_for_user(user))
        .exclude(experiment_description__isnull=True)
        .annotate(trimmed_description=Trim('experiment_description'))
        .exclude(trimmed_description='')
        .select_related('project')
    )


def description_source_for_user(user, source_id):
    """Resolve one reusable description without materializing every source."""
    try:
        source_id = int(source_id)
    except (TypeError, ValueError):
        return None
    return accessible_description_sources(user).filter(id=source_id).first()


def copy_all_steps_to_experiment(source_experiment, target_experiment):
    """Copy an experiment's process definition while leaving physical outputs behind."""
    source_steps = list(
        source_experiment.steps
        .select_related('owner', 'tool')
        .prefetch_related('parents', 'raw_material_usages__raw_material')
        .order_by('step_name', 'step_number', 'id')
    )
    invalid_batches = sorted({
        usage.raw_material.batch_number
        for step in source_steps
        for usage in step.raw_material_usages.all()
        if (
            not inventory_ready(usage.raw_material)
            or not usage.raw_material.is_active
            or usage.quantity is None
            or usage.quantity <= 0
            or (usage.unit or '').strip() != (usage.raw_material.total_unit or '').strip()
        )
    })
    if invalid_batches:
        raise ValidationError(
            '以下原材料库存资料不完整、已停用或用量单位不一致，不能复制：'
            + '、'.join(invalid_batches)
        )

    original_to_copy = {}
    for source_step in source_steps:
        copied_step = ExperimentStep.objects.create(
            step_name=source_step.step_name,
            step_number=source_step.step_number,
            step_description=source_step.step_description,
            experiment=target_experiment,
            parent=None,
            owner=source_step.owner,
            tool=source_step.tool,
            recipe=source_step.recipe,
            notes=source_step.notes,
            status='Planned',
            completed_on=None,
        )
        for usage in source_step.raw_material_usages.all():
            StepRawMaterialUsage.objects.create(
                step=copied_step,
                raw_material=usage.raw_material,
                quantity=usage.quantity,
                unit=usage.unit,
                notes=usage.notes,
            )
        original_to_copy[source_step.id] = copied_step

    for source_step in source_steps:
        copied_step = original_to_copy[source_step.id]
        copied_parents = [
            original_to_copy.get(parent.id, parent)
            for parent in source_step.parents.all()
        ]
        if not copied_parents and source_step.parent:
            copied_parents = [original_to_copy.get(source_step.parent_id, source_step.parent)]
        copied_step.parents.set(copied_parents)
        sync_legacy_parent(copied_step)

    return list(original_to_copy.values())


@login_required
def search_experiment_description_sources(request, exp_id):
    """Search reusable descriptions in small, permission-scoped pages."""
    current_project = get_object_or_404(Project, id=exp_id)
    if not user_can_access_experiment(request.user, current_project):
        return JsonResponse({'error': '你没有权限访问该项目。'}, status=403)

    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'results': [], 'pagination': {'more': False}})

    try:
        page_number = max(int(request.GET.get('page', 1)), 1)
    except (TypeError, ValueError):
        page_number = 1

    sources = (
        accessible_description_sources(request.user)
        .filter(
            Q(full_experiment_code__icontains=query)
            | Q(project__exp_name__icontains=query)
            | Q(experiment_description__icontains=query)
        )
        .annotate(
            current_project_order=Case(
                When(project_id=current_project.id, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            step_count=Count('steps', distinct=True),
        )
        .order_by('current_project_order', 'full_experiment_code', 'id')
    )
    page = Paginator(sources, 20).get_page(page_number)
    results = []
    for source in page.object_list:
        preview = ' '.join(source.experiment_description.split())
        if len(preview) > 100:
            preview = f'{preview[:100].rstrip()}…'
        results.append({
            'id': source.id,
            'code': source.full_experiment_code,
            'project_code': source.project.exp_name,
            'preview': preview,
            'is_current_project': source.project_id == current_project.id,
            'step_count': source.step_count,
        })
    return JsonResponse({
        'results': results,
        'pagination': {'more': page.has_next()},
    })


@login_required
def get_experiment_description_source(request, exp_id, source_id):
    """Return the full description only after a source has been selected."""
    current_project = get_object_or_404(Project, id=exp_id)
    if not user_can_access_experiment(request.user, current_project):
        return JsonResponse({'error': '你没有权限访问该项目。'}, status=403)
    source = description_source_for_user(request.user, source_id)
    if not source:
        return JsonResponse({'error': '复制来源不可用或你没有访问权限。'}, status=404)
    return JsonResponse({
        'id': source.id,
        'code': source.full_experiment_code,
        'project_code': source.project.exp_name,
        'description': source.experiment_description,
        'is_current_project': source.project_id == current_project.id,
        'step_count': source.steps.count(),
    })


def user_can_access_experiment(user, experiment):
    if user.is_staff or user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    user_group = getattr(profile, 'research_group', None)
    return bool(
        user_group
        and getattr(experiment, 'project', None)
        and experiment.project.group == user_group
    )


def user_can_access_step(user, step):
    project = getattr(getattr(step, 'experiment', None), 'project', None)
    return bool(project and user_can_access_experiment(user, project))


def user_can_edit_raw_material(user, material):
    return bool(
        user.is_staff or user.is_superuser
        or (material.owner_id and material.owner_id == user.id)
    )


def selectable_raw_materials(existing_step=None):
    queryset = RawMaterial.objects.filter(
        is_active=True,
        total_quantity__isnull=False,
    ).exclude(total_unit__isnull=True).exclude(total_unit='')
    if existing_step:
        queryset = RawMaterial.objects.filter(
            Q(id__in=queryset.values('id')) | Q(step_usages__step=existing_step)
        )
    return queryset.distinct().order_by('material_code', 'batch_number')


def sync_legacy_parent(step):
    """Keep the old single-parent field populated for compatibility."""
    first_parent = step.parents.order_by(
        'experiment__project__exp_name',
        'experiment__experiment_code',
        'step_name',
        'step_number',
    ).first()
    new_parent_id = first_parent.id if first_parent else None
    if step.parent_id != new_parent_id:
        ExperimentStep.objects.filter(id=step.id).update(parent_id=new_parent_id)
        step.parent_id = new_parent_id


def build_step_ancestor_steps(step, user=None, seen_ids=None):
    seen_ids = seen_ids or set()
    if step.id in seen_ids:
        return []
    seen_ids.add(step.id)

    ancestors = []
    parent_links = (
        step.incoming_links
        .select_related('parent_step__experiment__project', 'parent_step__tool')
        .prefetch_related('parent_step__raw_material_usages__raw_material')
        .order_by(
            'parent_step__experiment__project__exp_name',
            'parent_step__experiment__experiment_code',
            'parent_step__step_name',
            'parent_step__step_number',
        )
    )
    for link in parent_links:
        parent = link.parent_step
        if user and not user_can_access_step(user, parent):
            continue
        ancestors.extend(build_step_ancestor_steps(parent, user=user, seen_ids=seen_ids.copy()))
        if parent.id not in {ancestor.id for ancestor in ancestors}:
            ancestors.append(parent)
    return ancestors


def build_step_descendant_tree(step, user=None, seen_ids=None):
    seen_ids = seen_ids or set()
    if step.id in seen_ids:
        return []
    seen_ids.add(step.id)

    descendants = []
    child_links = (
        step.outgoing_links
        .select_related('child_step__experiment__project', 'child_step__tool')
        .prefetch_related('child_step__raw_material_usages__raw_material')
        .order_by(
            'child_step__experiment__project__exp_name',
            'child_step__experiment__experiment_code',
            'child_step__step_name',
            'child_step__step_number',
        )
    )
    for link in child_links:
        child = link.child_step
        if user and not user_can_access_step(user, child):
            continue
        descendants.append({
            'step': child,
            'children': build_step_descendant_tree(child, user=user, seen_ids=seen_ids.copy()),
        })
    return descendants


def format_quantity(value):
    if value is None:
        return ''
    return f"{value:g}"


def add_genealogy_step_element(elements, step, x, y, is_current=False):
    step_node_id = f"step-{step.id}"
    status_label = STATUS_LABELS_ZH.get(step.status, step.status)
    elements.append({
        'group': 'nodes',
        'data': {
            'id': step_node_id,
            'type': 'step',
            'step_id': step.id,
            'label': step.full_step or str(step),
            'status': step.status,
            'status_label': status_label,
            'project_experiment': step.experiment.full_experiment_code if step.experiment else '',
            'tool': step.tool.equipment_name if step.tool else '未选择设备',
            'recipe': step.recipe or '',
            'description': step.step_description or '',
            'url': f"/step/{step.id}/genealogy/",
            'is_current': bool(is_current),
        },
        'position': {'x': x, 'y': y},
        'classes': 'step-node current-step' if is_current else 'step-node',
    })

    material_spacing = 82
    material_usages = list(step.raw_material_usages.all())
    material_start_y = y - ((len(material_usages) - 1) * material_spacing / 2)
    for index, usage in enumerate(material_usages):
        material = usage.raw_material
        material_node_id = f"material-{step.id}-{material.id}"
        material_y = material_start_y + index * material_spacing
        quantity = format_quantity(usage.quantity)
        amount = f"{quantity} {usage.unit or ''}".strip()
        elements.append({
            'group': 'nodes',
            'data': {
                'id': material_node_id,
                'type': 'material',
                'label': material.batch_number or material.material_code,
                'material_code': material.material_code,
                'amount': amount,
            },
            'position': {'x': x, 'y': material_y - 140},
            'classes': 'material-node',
        })
        elements.append({
            'group': 'edges',
            'data': {
                'id': f"material-edge-{step.id}-{material.id}",
                'source': material_node_id,
                'target': step_node_id,
                'type': 'material',
            },
            'classes': 'material-edge',
        })


def flatten_descendant_tree(descendant_tree):
    descendants = []
    for node in descendant_tree:
        child = node['step']
        descendants.append(child)
        descendants.extend(flatten_descendant_tree(node['children']))
    return descendants


def build_genealogy_graph(step, upstream_steps, downstream_tree, user=None):
    elements = []
    x_origin = 220
    x_gap = 310
    y_gap = 170
    current_y = 320

    graph_steps_by_id = {}
    for graph_step in upstream_steps + [step] + flatten_descendant_tree(downstream_tree):
        graph_steps_by_id[graph_step.id] = graph_step
    graph_steps = list(graph_steps_by_id.values())
    graph_step_ids = {graph_step.id for graph_step in graph_steps}

    visible_links = list(
        ExperimentStepLink.objects
        .filter(parent_step_id__in=graph_step_ids, child_step_id__in=graph_step_ids)
        .select_related('parent_step', 'child_step')
    )
    if user:
        visible_links = [
            link for link in visible_links
            if user_can_access_step(user, link.parent_step) and user_can_access_step(user, link.child_step)
        ]

    children_by_parent = {}
    parents_by_child = {}
    for link in visible_links:
        children_by_parent.setdefault(link.parent_step_id, set()).add(link.child_step_id)
        parents_by_child.setdefault(link.child_step_id, set()).add(link.parent_step_id)

    depth_by_id = {step.id: 0}
    pending = [step.id]
    while pending:
        child_id = pending.pop(0)
        child_depth = depth_by_id[child_id]
        for parent_id in parents_by_child.get(child_id, set()):
            parent_depth = child_depth - 1
            if parent_id not in depth_by_id or parent_depth < depth_by_id[parent_id]:
                depth_by_id[parent_id] = parent_depth
                pending.append(parent_id)

    pending = [step.id]
    while pending:
        parent_id = pending.pop(0)
        parent_depth = depth_by_id[parent_id]
        for child_id in children_by_parent.get(parent_id, set()):
            child_depth = parent_depth + 1
            if child_id not in depth_by_id or child_depth > depth_by_id[child_id]:
                depth_by_id[child_id] = child_depth
                pending.append(child_id)

    min_depth = min(depth_by_id.values(), default=0)

    steps_by_depth = {}
    for graph_step in graph_steps:
        steps_by_depth.setdefault(depth_by_id.get(graph_step.id, 0), []).append(graph_step)

    y_by_id = {}
    for depth, steps_at_depth in steps_by_depth.items():
        steps_at_depth.sort(
            key=lambda graph_step: (
                graph_step.experiment.project.exp_name if graph_step.experiment and graph_step.experiment.project else '',
                graph_step.experiment.experiment_code if graph_step.experiment else '',
                graph_step.step_name,
                graph_step.step_number,
                graph_step.id,
            )
        )
        layer_gap = max(y_gap, 132 if len(steps_at_depth) > 3 else y_gap)
        start_y = current_y - ((len(steps_at_depth) - 1) * layer_gap / 2)
        for index, graph_step in enumerate(steps_at_depth):
            y_by_id[graph_step.id] = start_y + index * layer_gap

    for depth in sorted(steps_by_depth):
        for graph_step in steps_by_depth[depth]:
            add_genealogy_step_element(
                elements,
                graph_step,
                x_origin + (depth - min_depth) * x_gap,
                y_by_id[graph_step.id],
                is_current=(graph_step.id == step.id),
            )

    for link in visible_links:
        elements.append({
            'group': 'edges',
            'data': {
                'id': f"step-edge-{link.parent_step_id}-{link.child_step_id}",
                'source': f"step-{link.parent_step_id}",
                'target': f"step-{link.child_step_id}",
                'type': 'step',
            },
            'classes': 'step-edge',
        })
    return {'elements': elements}

# Create your views here.

@login_required
def index(request):

    search_query = request.GET.get('search', '')
    my_experiments = request.GET.get('my_experiments', '')
    # Use group-restricted queryset helper
    latest_exp = get_experiments_for_user(request.user, search_query, my_experiments)
    overview_stats = get_experiment_overview_stats(latest_exp)
    visible_experiments = (
        Experiment.objects
        .filter(project__in=latest_exp)
        .select_related('project__owner', 'project__project__group')
        .order_by('-created_on')
    )
    growth_chart = get_experiment_growth_chart(visible_experiments)
    recent_experiment_updates = visible_experiments[:5]

    page_number = request.GET.get('page', 1)
    paginator = Paginator(latest_exp, 10)  # 10 experiments per page
    page_obj = paginator.get_page(page_number)

    return render(request, 'experiment_flow/index.html', {
        'experiments': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'overview_stats': overview_stats,
        'growth_chart': growth_chart,
        'recent_experiment_updates': recent_experiment_updates,
    })

@login_required
def experiment_detail(request, exp_id):

    experiment = Project.objects.get(id=exp_id)
    # Security: ensure the current user is in the same research group as the experiment's project
    # Staff and superusers can access all experiments
    if not user_can_access_experiment(request.user, experiment):
        record_permission_denied(request, 'project', f'拒绝访问项目 {experiment.exp_name}', instance=experiment)
        messages.error(request, '你没有权限查看该实验。')
        return redirect('index')
    detail_steps = (
        ExperimentStep.objects
        .annotate(sample_total=Count('samples'))
        .prefetch_related('cells__test_item')
    )
    project_experiments = (
        Experiment.objects
        .filter(project=experiment)
        .prefetch_related(Prefetch('steps', queryset=detail_steps))
        .order_by('created_on')
    )
    available_experiment_codes = get_available_experiment_codes(experiment)

    search_query = request.GET.get('search', '')
    my_experiments = request.GET.get('my_experiments', '')
    latest_exp = get_experiments_for_user(request.user, search_query, my_experiments)

    page_number = request.GET.get('page', 1)
    paginator = Paginator(latest_exp, 10)  # 10 experiments per page
    page_obj = paginator.get_page(page_number)

    return render(request, 'experiment_flow/experiment_detail.html', {
        'experiment': experiment,
        'project_experiments': project_experiments,
        'available_experiment_codes': available_experiment_codes,
        'experiments': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'cell_test_items': CellTestItem.objects.order_by('name'),
    })

@login_required
def delete_project_experiment(request, exp_id, experiment_id):

    experiment = Project.objects.get(id=exp_id)
    project_experiment = Experiment.objects.get(id=experiment_id)
    with transaction.atomic():
        snapshot = model_snapshot(project_experiment, ('experiment_code', 'full_experiment_code', 'experiment_description'))
        write_audit_event(
            request, 'delete', 'experiment', f'删除 Experiment {project_experiment}',
            instance=project_experiment, changes={'snapshot': snapshot},
        )
        project_experiment.delete()

    return redirect('experiment_detail', exp_id=exp_id)

@login_required
def delete_step(request, exp_id, experiment_id, step_id):

    step = ExperimentStep.objects.get(id=step_id, experiment_id=experiment_id)
    if step_has_downstream_steps(step):
        messages.error(request, '该步骤已有下游关联步骤，无法删除。请先移除下游步骤的前置关系。')
        return redirect(f'/experiment/{exp_id}/?expanded_experiment={experiment_id}')

    with transaction.atomic():
        snapshot = step_snapshot(step)
        write_audit_event(request, 'delete', 'step', f'删除 Step {step}', instance=step,
                          changes={'snapshot': snapshot})
        step.delete()

    return redirect(f'/experiment/{exp_id}/?expanded_experiment={experiment_id}')

@login_required
def add_experiment(request):
    # Show Teams directly. The ProjectCategory row is now an internal backing record
    # used to keep existing experiment relationships intact.
    if request.user.is_staff or request.user.is_superuser:
        teams = ResearchGroup.objects.exclude(team_code__isnull=True).exclude(team_code="").order_by('group_name')
    else:
        profile = getattr(request.user, 'profile', None)
        user_group = getattr(profile, 'research_group', None)
        if user_group:
            teams = ResearchGroup.objects.filter(id=user_group.id).exclude(team_code__isnull=True).exclude(team_code="")
        else:
            teams = ResearchGroup.objects.none()

    search_query = request.GET.get('search', '')
    my_experiments = request.GET.get('my_experiments', '')
    latest_exp = get_experiments_for_user(request.user, search_query, my_experiments)

    page_number = request.GET.get('page', 1)
    paginator = Paginator(latest_exp, 10)
    page_obj = paginator.get_page(page_number)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def render_add_experiment_form(error=None, status=200):
        context = {
            'teams': teams,
            'experiments': page_obj,
            'page_obj': page_obj,
            'search_query': search_query,
        }
        if error:
            context['error'] = error
        template_name = 'experiment_flow/_add_experiment_form.html' if is_ajax else 'experiment_flow/add_experiment.html'
        return render(request, template_name, context, status=status)

    if request.method == 'POST':
        team_id = request.POST.get('team')
        if team_id:
            try:
                # Staff and superusers can use any Team
                if request.user.is_staff or request.user.is_superuser:
                    team = ResearchGroup.objects.get(id=team_id)
                else:
                    # Regular users: ensure the selected Team is their own Team
                    profile = getattr(request.user, 'profile', None)
                    user_group = getattr(profile, 'research_group', None)
                    if not user_group or str(user_group.id) != str(team_id):
                        raise ResearchGroup.DoesNotExist
                    team = user_group

                if not team.team_code:
                    raise ValidationError('请先在后台为该 Team 设置 3 位 Team Code。')

                project = ProjectCategory.objects.filter(group=team).order_by("id").first()
                if not project:
                    project = ProjectCategory.objects.create(
                        group=team,
                        project_code=team.team_code,
                        project_name=team.group_name,
                    )
                elif project.project_code != team.team_code:
                    project.project_code = team.team_code
                    project.save(update_fields=["project_code"])

                exp_name = project.generate_experiment_name()
                exp_description = request.POST.get('exp_description')
                new_exp = Project(
                    exp_name=exp_name,
                    project=project,
                    exp_description=exp_description,
                    owner=request.user  # Automatically set the logged-in user as owner
                )
                with transaction.atomic():
                    new_exp.save()
                    write_audit_event(
                        request, 'create', 'project', f'创建 Project {new_exp.exp_name}',
                        instance=new_exp,
                        changes={'team': {'before': None, 'after': str(team)},
                                 'owner': {'before': None, 'after': request.user.username},
                                 'description': {'before': None, 'after': exp_description or ''}},
                    )
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'experiment_id': new_exp.id,
                        'experiment_name': new_exp.exp_name,
                        'redirect_url': reverse('experiment_detail', args=[new_exp.id])
                    })
                return redirect('index')
            except ResearchGroup.DoesNotExist:
                record_permission_denied(
                    request, 'project', '拒绝在无权限的 Team 中创建 Project',
                    entity_type='Project', object_repr=f'Team #{team_id}',
                )
                return render_add_experiment_form('未找到所选 Team。Selected team not found.', status=400 if is_ajax else 200)
            except ValidationError as e:
                return render_add_experiment_form(str(e), status=400 if is_ajax else 200)
        return render_add_experiment_form('请选择 Team。', status=400 if is_ajax else 200)

    return render_add_experiment_form()

@login_required
def add_project_experiment(request, exp_id):
    try:
        experiment = get_object_or_404(Project, id=exp_id)
        # Security: ensure the user is in the same research group as the experiment
        # Staff and superusers can access all experiments
        if not (request.user.is_staff or request.user.is_superuser):
            profile = getattr(request.user, 'profile', None)
            user_group = getattr(profile, 'research_group', None)
            if not user_group or not getattr(experiment, 'project', None) or experiment.project.group != user_group:
                record_permission_denied(request, 'experiment', f'拒绝访问项目 {experiment.exp_name}', instance=experiment)
                messages.error(request, "你没有权限访问该实验。")
                return redirect('index')

        if request.method == 'POST':
            try:
                experiment_code = (request.POST.get('experiment_code') or '').strip().upper()
                experiment_description = (request.POST.get('experiment_description') or '').strip()
                description_source_id = (request.POST.get('description_source_id') or '').strip()

                if not experiment_description:
                    raise ValidationError('实验描述为必填项。')
                if experiment_code not in get_available_experiment_codes(experiment):
                    raise ValidationError('请选择一个当前可用的实验代码。')

                description_source = None
                if description_source_id:
                    description_source = description_source_for_user(request.user, description_source_id)
                    if not description_source:
                        raise ValidationError('复制来源不可用或你没有访问权限。')

                new_experiment = Experiment(
                    experiment_code=experiment_code,
                    experiment_description=experiment_description,
                    project=experiment,
                )
                audit_changes = {
                    'experiment_code': {'before': None, 'after': experiment_code},
                    'project_code': {'before': None, 'after': experiment.exp_name},
                    'description': {'before': None, 'after': experiment_description},
                }
                if description_source:
                    audit_changes['description_source_id'] = {
                        'before': None,
                        'after': description_source.id,
                    }
                    audit_changes['description_source_code'] = {
                        'before': None,
                        'after': description_source.full_experiment_code,
                    }

                with transaction.atomic():
                    new_experiment.save()
                    copied_steps = []
                    if description_source:
                        copied_steps = copy_all_steps_to_experiment(description_source, new_experiment)
                        audit_changes['copied_step_count'] = {
                            'before': None,
                            'after': len(copied_steps),
                        }
                        audit_changes['copied_step_ids'] = {
                            'before': None,
                            'after': [step.id for step in copied_steps],
                        }
                    write_audit_event(
                        request, 'create', 'experiment', f'创建 Experiment {new_experiment}',
                        instance=new_experiment,
                        changes=audit_changes,
                    )

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'experiment_id': new_experiment.id,
                        'experiment_code': new_experiment.full_experiment_code,
                        'copied_step_count': len(copied_steps),
                    })
                return redirect('experiment_detail', exp_id=exp_id)
            except ValidationError as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': ' '.join(e.messages),
                    }, status=400)

                search_query = request.GET.get('search', '')
                my_experiments = request.GET.get('my_experiments', '')
                latest_exp = get_experiments_for_user(request.user, search_query, my_experiments)
                page_number = request.GET.get('page', 1)
                paginator = Paginator(latest_exp, 10)
                page_obj = paginator.get_page(page_number)
                return render(request, 'experiment_flow/add_project_experiment.html', {
                    'experiment': experiment,
                    'experiments': page_obj,
                    'page_obj': page_obj,
                    'search_query': search_query,
                    'available_experiment_codes': get_available_experiment_codes(experiment),
                    'submitted_experiment_code': request.POST.get('experiment_code', ''),
                    'submitted_experiment_description': request.POST.get('experiment_description', ''),
                    'error': ' '.join(e.messages),
                })

        # For GET requests or rendering the form
        search_query = request.GET.get('search', '')
        my_experiments = request.GET.get('my_experiments', '')
        latest_exp = get_experiments_for_user(request.user, search_query, my_experiments)

        page_number = request.GET.get('page', 1)
        paginator = Paginator(latest_exp, 10)
        page_obj = paginator.get_page(page_number)

        return render(request, 'experiment_flow/add_project_experiment.html', {
            'experiment': experiment,
            'experiments': page_obj,
            'page_obj': page_obj,
            'search_query': search_query,
            'available_experiment_codes': get_available_experiment_codes(experiment),
        })
    except Project.DoesNotExist:
        return HttpResponse('未找到实验', status=404)

@login_required
def add_step(request, exp_id, experiment_id):

    experiment = get_object_or_404(Project, id=exp_id)
    project_experiment = get_object_or_404(Experiment, id=experiment_id, project=experiment)
    if not user_can_access_experiment(request.user, experiment):
        record_permission_denied(
            request, 'step', f'拒绝在 Experiment {project_experiment} 中创建 Step',
            instance=project_experiment,
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': '无权访问该实验。'}, status=403)
        messages.error(request, '你没有权限修改该实验。')
        return redirect('index')

    if request.method == 'POST':
        form = ExperimentStepForm(request.POST, experiment=project_experiment)
        if form.is_valid():
            try:
                with transaction.atomic():
                    parsed_usages = parse_usage_payload(
                        request.POST.get('raw_material_usages', '[]')
                    )
                    if form.cleaned_data['status'] == 'Completed':
                        validate_usage_records_for_completion(parsed_usages)
                    deltas = completed_usage_delta(
                        None, [], form.cleaned_data['status'], parsed_usages,
                    )
                    shortages = negative_inventory_shortages(deltas)
                    if shortages and not allows_negative(request.POST.get('allow_negative')):
                        return JsonResponse(shortage_response(shortages), status=409)
                    step = form.save(commit=False)
                    step.experiment = project_experiment
                    step.save()
                    form.save_m2m()
                    sync_legacy_parent(step)
                    replace_step_usages(step, parsed_usages)
                    Sample.sync_for_step(step, form.cleaned_data['sample_count'])
                    save_step_cells(step, request.POST.get('cells_payload'))
                    write_audit_event(
                        request, 'create', 'step', f'创建 Step {step.full_step}', instance=step,
                        changes={'after': step_snapshot(step)},
                    )
            except RawMaterialUsageValidationError as exc:
                error_response = raw_material_save_error_response(request, form, exc)
                if error_response:
                    return error_response
            except (ValidationError, IntegrityError) as exc:
                error_response = cell_save_error_response(request, form, exc)
                if error_response:
                    return error_response
            else:
                # Return JSON for AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'redirect_url': f'/experiment/{exp_id}/?expanded_experiment={experiment_id}'
                    })

                return redirect(f'/experiment/{exp_id}/?expanded_experiment={experiment_id}')
        else:
            # Return errors for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    else:
        form = ExperimentStepForm(experiment=project_experiment)

    # Render the form (for both GET and non-AJAX POST with errors)
    return render(request, 'experiment_flow/add_step.html', {
        'experiment': experiment,
        'project_experiment': project_experiment,
        'form': form,
        'raw_materials': selectable_raw_materials(),
        'cells': [],
        'cell_test_items': CellTestItem.objects.filter(is_active=True).order_by('name'),
        'is_add': True  # Flag to indicate this is add mode, not edit mode
    })

@login_required
def edit_step(request, exp_id, experiment_id, step_id):
    project_experiment = get_object_or_404(Experiment, id=experiment_id, project_id=exp_id)
    step = get_object_or_404(ExperimentStep, id=step_id, experiment=project_experiment)
    if not user_can_access_step(request.user, step):
        record_permission_denied(
            request, 'step', f'拒绝修改 Step {step.full_step}', instance=step,
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': '无权访问该步骤。'}, status=403)
        messages.error(request, '你没有权限修改该步骤。')
        return redirect('index')

    if request.method == 'POST':
        before = step_snapshot(step)
        form = ExperimentStepForm(request.POST, instance=step, experiment=project_experiment)
        if form.is_valid():
            try:
                with transaction.atomic():
                    old_status = step.status
                    old_usages = list(step.raw_material_usages.select_related('raw_material'))
                    parsed_usages = parse_usage_payload(
                        request.POST.get('raw_material_usages', '[]'), existing_step=step,
                    )
                    if form.cleaned_data['status'] == 'Completed':
                        validate_usage_records_for_completion(parsed_usages)
                    deltas = completed_usage_delta(
                        old_status, old_usages, form.cleaned_data['status'], parsed_usages,
                    )
                    shortages = negative_inventory_shortages(deltas)
                    if shortages and not allows_negative(request.POST.get('allow_negative')):
                        return JsonResponse(shortage_response(shortages), status=409)
                    step = form.save(commit=False)
                    # Ensure the step is associated with the correct project_experiment
                    step.experiment = project_experiment
                    step.save()
                    form.save_m2m()
                    sync_legacy_parent(step)
                    replace_step_usages(step, parsed_usages)
                    Sample.sync_for_step(step, form.cleaned_data['sample_count'])
                    save_step_cells(step, request.POST.get('cells_payload'))
                    changes = changed_values(before, step_snapshot(step))
                    write_audit_event(
                        request, 'update', 'step', f'修改 Step {step.full_step}', instance=step,
                        changes=changes,
                    )
            except RawMaterialUsageValidationError as exc:
                error_response = raw_material_save_error_response(request, form, exc)
                if error_response:
                    return error_response
            except (ValidationError, IntegrityError) as exc:
                error_response = cell_save_error_response(request, form, exc)
                if error_response:
                    return error_response
            else:
                # Return JSON response for AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'redirect_url': f'/experiment/{exp_id}/?expanded_experiment={experiment_id}'
                    })

                # Regular form submission redirect
                return redirect(f'/experiment/{exp_id}/?expanded_experiment={experiment_id}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
            # If not AJAX, re-render the form with errors
    else:
        form = ExperimentStepForm(instance=step, experiment=project_experiment)

    return render(
        request,
        'experiment_flow/edit_step.html',
        {
            'form': form,
            'step': step,
            'project_experiment': project_experiment,
            'raw_materials': selectable_raw_materials(step),
            'cells': step.cells.select_related('test_item'),
            'cell_test_items': CellTestItem.objects.filter(
                Q(is_active=True) | Q(cells__step=step)
            ).distinct().order_by('name'),
            'samples': step.samples.all(),
        }
    )

@login_required
def step_genealogy(request, step_id):
    step = get_object_or_404(
        ExperimentStep.objects
        .select_related('experiment__project__project__group', 'tool')
        .prefetch_related('raw_material_usages__raw_material', 'cells'),
        id=step_id
    )

    if not user_can_access_step(request.user, step):
        record_permission_denied(request, 'step', f'拒绝访问 Step 谱系 {step.full_step}', instance=step)
        messages.error(request, '你没有权限查看该步骤谱系。')
        return redirect('index')

    ancestor_chain = build_step_ancestor_steps(step, user=request.user)
    ancestor_ids = [ancestor.id for ancestor in ancestor_chain]
    ancestors_qs = (
        ExperimentStep.objects
        .filter(id__in=ancestor_ids)
        .select_related('experiment__project', 'tool')
        .prefetch_related('raw_material_usages__raw_material')
    )
    ancestors = [ancestor for ancestor in ancestors_qs if user_can_access_step(request.user, ancestor)]
    ancestor_by_id = {ancestor.id: ancestor for ancestor in ancestors}
    ancestor_chain = [ancestor_by_id[ancestor_id] for ancestor_id in ancestor_ids if ancestor_id in ancestor_by_id]
    descendant_tree = build_step_descendant_tree(step, user=request.user)

    lineage_steps = ancestor_chain + [step]
    upstream_steps = ancestor_chain
    current_step = step
    downstream_tree = descendant_tree
    genealogy_graph = build_genealogy_graph(step, upstream_steps, downstream_tree, user=request.user)

    template_name = 'experiment_flow/_step_genealogy_content.html' if (
        request.GET.get('partial') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    ) else 'experiment_flow/step_genealogy.html'

    return render(request, template_name, {
        'step': step,
        'lineage_steps': lineage_steps,
        'descendant_tree': descendant_tree,
        'upstream_steps': upstream_steps,
        'current_step': current_step,
        'downstream_tree': downstream_tree,
        'genealogy_graph_json': genealogy_graph,
        'experiment': step.experiment.project,
    })

@login_required
def update_experiment_desc(request, experiment_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        desc = data.get('description', '')
        try:
            project_experiment = Experiment.objects.get(id=experiment_id)
            before = {'description': project_experiment.experiment_description or ''}
            with transaction.atomic():
                project_experiment.experiment_description = desc
                project_experiment.save()
                write_audit_event(
                    request, 'update', 'experiment', f'修改 Experiment {project_experiment} 描述',
                    instance=project_experiment,
                    changes=changed_values(before, {'description': desc}),
                )
            return JsonResponse({'success': True})
        except Experiment.DoesNotExist:
            return JsonResponse({'success': False}, status=404)
    return JsonResponse({'success': False}, status=400)

@login_required
def update_step_desc(request, step_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step = ExperimentStep.objects.get(id=step_id)
            desc = data.get('description', '')
            before = {'description': step.step_description or ''}
            with transaction.atomic():
                step.step_description = desc
                step.save()
                write_audit_event(
                    request, 'update', 'step', f'修改 Step {step.full_step} 描述', instance=step,
                    changes=changed_values(before, {'description': desc}),
                )
            return JsonResponse({'success': True})
        except ExperimentStep.DoesNotExist:
            return JsonResponse({'success': False, 'error': '未找到步骤'})
    return JsonResponse({'success': False, 'error': '无效请求'})

@login_required
def update_step_status(request, step_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step = ExperimentStep.objects.select_related(
                'experiment__project__project__group'
            ).get(id=step_id)
            if not user_can_access_step(request.user, step):
                record_permission_denied(
                    request, 'step', f'拒绝修改 Step {step.full_step} 状态', instance=step,
                )
                return JsonResponse({'success': False, 'error': '无权修改该步骤。'}, status=403)
            new_status = data.get('status', '')

            # Validate status
            valid_statuses = ['Planned', 'Completed', 'Canceled']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'error': '无效状态'})

            before = {'status': step.status, 'completed_on': step.completed_on}
            with transaction.atomic():
                step = ExperimentStep.objects.select_for_update().get(pk=step.pk)
                usages = list(step.raw_material_usages.select_related('raw_material'))
                if new_status == 'Completed':
                    validate_usage_records_for_completion(usages)
                deltas = completed_usage_delta(step.status, usages, new_status, usages)
                shortages = negative_inventory_shortages(deltas)
                if shortages and not allows_negative(data.get('allow_negative')):
                    return JsonResponse(shortage_response(shortages), status=409)
                step.status = new_status
                if new_status == 'Completed':
                    step.completed_on = timezone.now()
                else:
                    step.completed_on = None
                step.save()
                after = {'status': step.status, 'completed_on': step.completed_on}
                write_audit_event(
                    request, 'status', 'step',
                    f'Step {step.full_step} 状态改为 {STATUS_LABELS_ZH.get(new_status, new_status)}',
                    instance=step, changes=changed_values(before, after),
                )

            # Return success with completed_on timestamp if applicable
            response_data = {'success': True}
            if new_status == 'Completed' and step.completed_on:
                response_data['completed_on'] = step.completed_on.strftime('%Y-%m-%d %H:%M:%S')

            return JsonResponse(response_data)
        except ValidationError as exc:
            return JsonResponse({'success': False, 'error': ' '.join(exc.messages)}, status=400)
        except ExperimentStep.DoesNotExist:
            return JsonResponse({'success': False, 'error': '未找到步骤'})
    return JsonResponse({'success': False, 'error': '无效请求'})

@login_required
def bulk_update_status(request, exp_id):
    """Bulk update status for multiple steps"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step_ids = data.get('step_ids', [])
            new_status = data.get('status', '')

            if not step_ids:
                return JsonResponse({'success': False, 'error': '未选择步骤'})

            # Validate status
            valid_statuses = ['Planned', 'Completed', 'Canceled']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'error': '无效状态'})

            # Get all steps and verify they belong to this experiment
            steps = list(ExperimentStep.objects.filter(
                id__in=step_ids,
                experiment__project_id=exp_id
            ).select_related('experiment__project__project__group'))

            if not steps:
                return JsonResponse({'success': False, 'error': '未找到有效步骤'})
            if len({step.id for step in steps}) != len({int(step_id) for step_id in step_ids}):
                return JsonResponse({'success': False, 'error': '包含无效步骤。'}, status=400)
            if any(not user_can_access_step(request.user, step) for step in steps):
                record_permission_denied(
                    request, 'step', '拒绝批量修改 Step 状态',
                    entity_type='Experiment Steps', object_repr='批量步骤',
                )
                return JsonResponse({'success': False, 'error': '无权修改所选步骤。'}, status=403)

            before_steps = [{'id': step.id, 'step_code': step.full_step, 'status': step.status} for step in steps]
            with transaction.atomic():
                locked_steps = list(
                    ExperimentStep.objects.select_for_update()
                    .filter(id__in=[step.id for step in steps])
                    .prefetch_related('raw_material_usages__raw_material')
                )
                combined_deltas = {}
                for step in locked_steps:
                    usages = list(step.raw_material_usages.all())
                    if new_status == 'Completed':
                        validate_usage_records_for_completion(usages)
                    for material_id, quantity in completed_usage_delta(
                        step.status, usages, new_status, usages,
                    ).items():
                        combined_deltas[material_id] = combined_deltas.get(material_id, Decimal('0')) + quantity
                shortages = negative_inventory_shortages(combined_deltas)
                if shortages and not allows_negative(data.get('allow_negative')):
                    return JsonResponse(shortage_response(shortages), status=409)
                updated_count = 0
                for step in locked_steps:
                    step.status = new_status
                    if new_status == 'Completed':
                        step.completed_on = timezone.now()
                    else:
                        step.completed_on = None
                    step.save()
                    updated_count += 1
                write_audit_event(
                    request, 'status', 'step', f'批量修改 {updated_count} 个 Step 状态',
                    entity_type='Experiment Steps', object_id=','.join(str(item['id']) for item in before_steps),
                    object_repr=f'{updated_count} 个步骤',
                    changes={'steps': [{**item, 'new_status': new_status} for item in before_steps]},
                )

            return JsonResponse({
                'success': True,
                'updated_count': updated_count,
                'message': f'已将 {updated_count} 个步骤更新为 {STATUS_LABELS_ZH.get(new_status, new_status)}'
            })

        except ValidationError as exc:
            return JsonResponse({'success': False, 'error': ' '.join(exc.messages)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@transaction.atomic
def copy_steps(request, exp_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step_ids = data.get('step_ids', [])
            target_experiment_code = data.get('target_experiment_code', '')  # Full project_experiment name like "MLO001AA"

            if not step_ids:
                return JsonResponse({'success': False, 'error': '未选择步骤'})

            if not target_experiment_code:
                return JsonResponse({'success': False, 'error': '请输入目标实验编号'})

            # Get all experiments accessible to the user
            experiments = get_experiments_for_user(request.user)

            # Find the target project_experiment by full_experiment_code name across all accessible experiments
            target_experiment = None
            for exp in experiments:
                try:
                    target_experiment = Experiment.objects.get(full_experiment_code=target_experiment_code, project=exp)
                    break
                except Experiment.DoesNotExist:
                    continue

            if not target_experiment:
                return JsonResponse({'success': False, 'error': f'实验 "{target_experiment_code}" 不存在，或你没有访问权限'})

            # Get the selected steps
            steps_to_copy = (
                ExperimentStep.objects
                .filter(id__in=step_ids, experiment__project_id=exp_id)
                .select_related('experiment__project__project__group')
                .prefetch_related('parents', 'raw_material_usages__raw_material')
                .order_by('step_number')
            )

            if not steps_to_copy:
                return JsonResponse({'success': False, 'error': '未找到所选步骤'})
            steps_to_copy = list(steps_to_copy)
            if len({step.id for step in steps_to_copy}) != len({int(step_id) for step_id in step_ids}):
                return JsonResponse({'success': False, 'error': '包含无效步骤。'}, status=400)
            if any(not user_can_access_step(request.user, step) for step in steps_to_copy):
                return JsonResponse({'success': False, 'error': '无权复制所选步骤。'}, status=403)
            invalid_batches = sorted({
                usage.raw_material.batch_number
                for step in steps_to_copy
                for usage in step.raw_material_usages.all()
                if (
                    not inventory_ready(usage.raw_material)
                    or not usage.raw_material.is_active
                    or usage.quantity is None
                    or usage.quantity <= 0
                    or (usage.unit or '').strip() != (usage.raw_material.total_unit or '').strip()
                )
            })
            if invalid_batches:
                return JsonResponse({
                    'success': False,
                    'error': '以下原材料库存资料不完整、已停用或用量单位不一致，不能复制：'
                             + '、'.join(invalid_batches),
                }, status=400)

            copied_count = 0

            # We'll keep a mapping from original step id -> new step instance
            # This allows us to restore parent relationships for copied steps
            orig_to_new = {}

            # Copy each step to the target project_experiment (first pass: create steps)
            for original_step in steps_to_copy:
                # Get the step name (just the 2-letter code, e.g., "MX")
                step_name = original_step.step_name

                # Find existing steps with the same name in target project_experiment
                existing_steps = ExperimentStep.objects.filter(
                    experiment=target_experiment,
                    step_name=step_name
                ).order_by('-step_number')

                # Determine the new step number
                if existing_steps.exists():
                    # Get the highest step number and increment
                    latest_step = existing_steps.first()
                    # Extract number from step_number field (e.g., "01")
                    if latest_step.step_number and latest_step.step_number.isdigit():
                        latest_num = int(latest_step.step_number)
                        new_step_number = f"{latest_num + 1:02d}"
                    else:
                        new_step_number = "00"
                else:
                    new_step_number = "00"

                # Create the copied step (always set status to "Planned" for copied steps)
                new_step = ExperimentStep(
                    step_name=step_name,  # Just the 2-letter code (e.g., "MX")
                    step_number=new_step_number,  # The number part (e.g., "01")
                    step_description=original_step.step_description,
                    experiment=target_experiment,
                    parent=None,  # Parent is assigned after all selected steps are copied.
                    owner=original_step.owner,
                    tool=original_step.tool,  # Copy equipment/tool used for the step
                    recipe=original_step.recipe,
                    notes=original_step.notes,
                    status="Planned",  # Always set to "Planned" regardless of original status
                    started_on=None,  # Reset timestamps for copied steps
                    completed_on=None
                )
                new_step.save()
                for usage in original_step.raw_material_usages.select_related('raw_material').all():
                    StepRawMaterialUsage.objects.create(
                        step=new_step,
                        raw_material=usage.raw_material,
                        quantity=usage.quantity,
                        unit=usage.unit,
                        notes=usage.notes,
                    )
                # record mapping
                orig_to_new[original_step.id] = new_step
                copied_count += 1

            # Second pass: restore upstream genealogy links.
            # If an upstream step was copied in the same batch, point to the copied step.
            # Otherwise keep the original upstream step to preserve traceability.
            for original_step in steps_to_copy:
                new_step = orig_to_new.get(original_step.id)
                if not new_step:
                    continue
                new_parents = [
                    orig_to_new.get(parent.id, parent)
                    for parent in original_step.parents.all()
                ]
                if not new_parents and original_step.parent:
                    new_parents = [orig_to_new.get(original_step.parent.id, original_step.parent)]
                new_step.parents.set(new_parents)
                sync_legacy_parent(new_step)

            target_exp_name = target_experiment.project.exp_name if target_experiment.project else "未知"
            write_audit_event(
                request, 'copy', 'step', f'复制 {copied_count} 个 Step 到 {target_experiment.full_experiment_code}',
                instance=target_experiment, entity_type='Experiment Steps',
                object_repr=f'{copied_count} 个步骤 → {target_experiment.full_experiment_code}',
                changes={
                    'source_steps': [{'id': step.id, 'step_code': step.full_step} for step in steps_to_copy],
                    'created_steps': [{'id': step.id, 'step_code': step.full_step} for step in orig_to_new.values()],
                    'target_experiment': target_experiment.full_experiment_code,
                },
            )
            return JsonResponse({
                'success': True,
                'message': f'已复制 {copied_count} 个步骤到实验 {target_experiment.full_experiment_code}（项目 {target_exp_name}）',
                'copied_count': copied_count
            })

        except Exception as e:
            transaction.set_rollback(True)
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': '无效请求方式'})

@login_required
def delete_steps(request, exp_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step_ids = data.get('step_ids', [])

            if not step_ids:
                return JsonResponse({'success': False, 'error': '未选择步骤'})

            # Get the steps to delete
            steps_to_delete = ExperimentStep.objects.filter(id__in=step_ids)

            if not steps_to_delete:
                return JsonResponse({'success': False, 'error': '未找到所选步骤'})

            blocked_steps = [
                step.full_step or str(step)
                for step in steps_to_delete
                if step_has_downstream_steps(step)
            ]
            if blocked_steps:
                return JsonResponse({
                    'success': False,
                    'error': '以下步骤已有下游关联步骤，无法删除：' + '，'.join(blocked_steps)
                })

            snapshots = [step_snapshot(step) for step in steps_to_delete]
            deleted_count = len(snapshots)
            with transaction.atomic():
                write_audit_event(
                    request, 'delete', 'step', f'批量删除 {deleted_count} 个 Step',
                    entity_type='Experiment Steps',
                    object_id=','.join(str(step.id) for step in steps_to_delete),
                    object_repr=f'{deleted_count} 个步骤', changes={'steps': snapshots},
                )
                steps_to_delete.delete()

            return JsonResponse({
                'success': True,
                'message': f'已删除 {deleted_count} 个步骤',
                'deleted_count': deleted_count
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': '无效请求方式'})


# Equipment views
@login_required
def equipment_list(request):
    search_query = request.GET.get('search', '')
    equipment_list = Equipment.objects.all().select_related('owner').order_by('equipment_name')

    if search_query:
        equipment_list = equipment_list.filter(
            Q(equipment_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(owner__username__icontains=search_query)
        )

    page_number = request.GET.get('page', 1)
    paginator = Paginator(equipment_list, 20)  # 20 equipment per page
    page_obj = paginator.get_page(page_number)

    return render(request, 'experiment_flow/equipment_list.html', {
        'equipment_list': page_obj,
        'page_obj': page_obj,
        'search_query': search_query
    })

@login_required
def equipment_detail(request, equipment_id):
    equipment = get_object_or_404(Equipment, id=equipment_id)
    return render(request, 'experiment_flow/equipment_detail.html', {
        'equipment': equipment
    })

@login_required
def add_equipment(request):
    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                equipment = form.save()
                after = model_snapshot(equipment, EQUIPMENT_FIELDS)
                write_audit_event(
                    request, 'create', 'equipment', f'登记设备 {equipment.equipment_name}',
                    instance=equipment,
                    changes={field: {'before': None, 'after': value} for field, value in after.items()},
                )
            return redirect('equipment_list')
    else:
        form = EquipmentForm()

    return render(request, 'experiment_flow/add_equipment.html', {
        'form': form
    })

@login_required
def edit_equipment(request, equipment_id):
    equipment = get_object_or_404(Equipment, id=equipment_id)

    if request.method == 'POST':
        before = model_snapshot(equipment, EQUIPMENT_FIELDS)
        form = EquipmentForm(request.POST, instance=equipment)
        if form.is_valid():
            with transaction.atomic():
                equipment = form.save()
                write_audit_event(
                    request, 'update', 'equipment', f'修改设备 {equipment.equipment_name}',
                    instance=equipment,
                    changes=changed_values(before, model_snapshot(equipment, EQUIPMENT_FIELDS)),
                )
            return redirect('equipment_detail', equipment_id=equipment_id)
    else:
        form = EquipmentForm(instance=equipment)

    return render(request, 'experiment_flow/edit_equipment.html', {
        'form': form,
        'equipment': equipment
    })

# Raw material views
@login_required
def raw_material_list(request):
    search_query = request.GET.get('search', '')
    raw_material_list = RawMaterial.objects.all().select_related('owner').order_by('material_code', 'batch_number')

    if search_query:
        raw_material_list = raw_material_list.filter(
            Q(material_code__icontains=search_query) |
            Q(batch_number__icontains=search_query) |
            Q(material_type__icontains=search_query) |
            Q(material_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(owner__username__icontains=search_query) |
            Q(owner__first_name__icontains=search_query) |
            Q(owner__last_name__icontains=search_query) |
            Q(supplier__icontains=search_query) |
            Q(location__icontains=search_query)
        )

    page_number = request.GET.get('page', 1)
    paginator = Paginator(raw_material_list, 20)
    page_obj = paginator.get_page(page_number)
    page_obj.object_list = attach_inventory_summaries(page_obj.object_list)
    for material in page_obj.object_list:
        material.can_edit = user_can_edit_raw_material(request.user, material)

    return render(request, 'experiment_flow/raw_material_list.html', {
        'raw_material_list': page_obj,
        'page_obj': page_obj,
        'search_query': search_query
    })

@login_required
def raw_material_detail(request, raw_material_id):
    raw_material = get_object_or_404(RawMaterial, id=raw_material_id)
    totals = inventory_totals([raw_material.id]).get(raw_material.id)
    inventory = inventory_summary(raw_material, totals)
    usages = raw_material.step_usages.select_related(
        'step__experiment__project',
        'raw_material'
    ).order_by('-updated_on')
    return render(request, 'experiment_flow/raw_material_detail.html', {
        'raw_material': raw_material,
        'usages': usages,
        'inventory': inventory,
        'can_edit': user_can_edit_raw_material(request.user, raw_material),
    })

@login_required
def add_raw_material(request):
    if request.method == 'POST':
        form = RawMaterialForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                material = form.save()
                after = model_snapshot(material, RAW_MATERIAL_FIELDS)
                write_audit_event(
                    request, 'create', 'raw_material', f'登记原材料 {material.batch_number}',
                    instance=material,
                    changes={field: {'before': None, 'after': value} for field, value in after.items()},
                )
            return redirect('raw_material_list')
    else:
        form = RawMaterialForm(user=request.user)

    return render(request, 'experiment_flow/add_raw_material.html', {
        'form': form
    })

@login_required
def edit_raw_material(request, raw_material_id):
    raw_material = get_object_or_404(RawMaterial, id=raw_material_id)
    if not user_can_edit_raw_material(request.user, raw_material):
        record_permission_denied(
            request, 'raw_material', f'拒绝修改原材料 {raw_material.batch_number}',
            instance=raw_material,
        )
        return JsonResponse({'success': False, 'error': '只有负责人或管理员可以修改该原材料。'}, status=403)

    if request.method == 'POST':
        before = model_snapshot(raw_material, RAW_MATERIAL_FIELDS)
        form = RawMaterialForm(request.POST, instance=raw_material, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                proposed_total = form.cleaned_data['total_quantity']
                shortages = negative_inventory_shortages(
                    total_overrides={raw_material.id: proposed_total},
                )
                if shortages and not allows_negative(request.POST.get('allow_negative')):
                    return JsonResponse(shortage_response(shortages), status=409)
                raw_material = form.save()
                write_audit_event(
                    request, 'update', 'raw_material', f'修改原材料 {raw_material.batch_number}',
                    instance=raw_material,
                    changes=changed_values(before, model_snapshot(raw_material, RAW_MATERIAL_FIELDS)),
                )
            return redirect('raw_material_detail', raw_material_id=raw_material_id)
    else:
        form = RawMaterialForm(instance=raw_material, user=request.user)

    return render(request, 'experiment_flow/edit_raw_material.html', {
        'form': form,
        'raw_material': raw_material
    })

@login_required
def get_raw_materials(request):
    raw_materials = attach_inventory_summaries(
        RawMaterial.objects.filter(is_active=True).select_related('owner').order_by('material_code', 'batch_number')
    )
    data = []
    for material in raw_materials:
        data.append({
            'id': material.id,
            'material_code': material.material_code,
            'batch_number': material.batch_number,
            'received_date': material.received_date.isoformat() if material.received_date else '',
            'material_type': material.material_type or '',
            'material_name': material.material_name,
            'total_quantity': str(material.total_quantity) if material.total_quantity is not None else '',
            'total_unit': material.total_unit or '',
            'supplier': material.supplier or '',
            'location': material.location or '',
            'owner': material.owner.get_full_name() if material.owner and material.owner.get_full_name() else (material.owner.username if material.owner else ''),
            'completed_quantity': str(material.completed_quantity),
            'remaining_quantity': str(material.remaining_quantity) if material.remaining_quantity is not None else '',
            'planned_quantity': str(material.planned_quantity),
            'projected_remaining_quantity': str(material.projected_remaining_quantity) if material.projected_remaining_quantity is not None else '',
            'inventory_state': material.inventory_state,
            'inventory_ready': material.inventory_ready,
            'label': (
                f'{material.batch_number} · 剩余 {material.remaining_quantity:g} {material.total_unit}'
                if material.inventory_ready else f'{material.batch_number} · 库存未知'
            ),
        })
    return JsonResponse({'raw_materials': data})

@login_required
def get_all_steps(request):
    """API endpoint to get all steps for the current user's research group"""
    # Staff and superusers can see all steps
    if request.user.is_staff or request.user.is_superuser:
        steps = ExperimentStep.objects.all().select_related('experiment', 'experiment__project').order_by('-started_on')
    else:
        # Get user's research group
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return JsonResponse({'steps': []})

        rg = getattr(profile, 'research_group', None)
        if not rg:
            return JsonResponse({'steps': []})

        # Get all steps from experiments in the user's research group
        steps = ExperimentStep.objects.filter(
            experiment__project__project__group=rg
        ).select_related('experiment', 'experiment__project').order_by('-started_on')

    # Format step data
    steps_data = []
    for step in steps:
        steps_data.append({
            'id': step.id,
            'full_step': step.full_step,
            'step_name': f"{step.step_name}{step.step_number}",
            'project_experiment': step.experiment.full_experiment_code if step.experiment else '',
            'experiment': step.experiment.project.exp_name if step.experiment and step.experiment.project else '',
            'selected_parent_ids': list(step.parents.values_list('id', flat=True)),
        })

    return JsonResponse({'steps': steps_data})

@login_required
def get_experiments_with_items(request):
    """API endpoint to get all projects with their experiments for copy step dropdown."""
    # Get experiments visible to user
    experiments = get_experiments_for_user(request.user)

    # Format data
    experiments_data = []
    for exp in experiments:
        project_experiments_data = []
        for project_experiment in exp.experiments.all().order_by('experiment_code'):
            project_experiments_data.append({
                'id': project_experiment.id,
                'full_experiment_code': project_experiment.full_experiment_code,
                'experiment_code': project_experiment.experiment_code,
                'experiment_description': project_experiment.experiment_description or ''
            })

        experiments_data.append({
            'id': exp.id,
            'exp_name': exp.exp_name,
            'exp_description': exp.exp_description or '',
            'experiments': project_experiments_data
        })

    return JsonResponse({'experiments': experiments_data})


@login_required
def global_search(request):
    """
    Resolve exact experiment, step, and barcode identifiers, or list matching cells.
    """
    query = request.GET.get('q', '').strip().upper()

    if not query:
        messages.warning(request, '请输入搜索内容。')
        return redirect('index')

    visible_projects = get_experiments_for_user(request.user)

    project_experiment = (
        Experiment.objects
        .filter(project__in=visible_projects, full_experiment_code=query)
        .first()
    )
    if project_experiment:
        return redirect(f'/experiment/{project_experiment.project.id}/?expanded_experiment={project_experiment.id}')

    step = (
        ExperimentStep.objects
        .filter(experiment__project__in=visible_projects, full_step=query)
        .select_related('experiment__project')
        .first()
    )
    if step:
        return redirect(f'/experiment/{step.experiment.project.id}/?expanded_experiment={step.experiment.id}&highlight_step={step.id}')

    visible_cells = (
        Cell.objects
        .filter(step__experiment__project__in=visible_projects)
        .select_related('step__experiment__project')
    )
    exact_cell = visible_cells.filter(barcode=query).first()
    if exact_cell:
        step = exact_cell.step
        params = urlencode({
            'expanded_experiment': step.experiment_id,
            'highlight_step': step.id,
            'expanded_cells': step.id,
            'highlight_cell': exact_cell.id,
        })
        return redirect(f'/experiment/{step.experiment.project_id}/?{params}')

    cell_matches = visible_cells.filter(
        Q(package_number__icontains=query) | Q(barcode__icontains=query)
    ).order_by(
        'package_number', 'barcode', 'step__experiment__project__exp_name',
        'step__experiment__full_experiment_code', 'step__full_step',
    )
    if cell_matches.exists():
        cell_page_obj = Paginator(cell_matches, 50).get_page(request.GET.get('cell_page', 1))
        sidebar_page_obj = Paginator(
            get_experiments_for_user(request.user, query), 10
        ).get_page(request.GET.get('page', 1))
        return render(request, 'experiment_flow/cell_search_results.html', {
            'cell_results': cell_page_obj,
            'cell_page_obj': cell_page_obj,
            'experiments': sidebar_page_obj,
            'page_obj': sidebar_page_obj,
            'search_query': query,
            'query': query,
        })

    if get_experiments_for_user(request.user, query).exists():
        return redirect(f"{reverse('index')}?{urlencode({'search': query})}")

    messages.error(request, f'未找到匹配 "{query}" 的项目、实验、步骤或电芯。')
    return redirect('index')
