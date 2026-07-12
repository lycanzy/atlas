from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Project, Experiment, ExperimentStep, ExperimentStepLink, ProjectCategory, ResearchGroup, UserProfile, StepNameTemplate, Equipment, RawMaterial, StepRawMaterialUsage
from .forms import ExperimentStepForm, ExperimentForm, EquipmentForm, RawMaterialForm, CustomPasswordChangeForm, TeamManagementForm, ProjectManagementForm, ProjectCreateForm, ManagedUserForm, MemberTeamForm, StepTemplateManagementForm
import json
import string
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.utils import timezone


STATUS_LABELS_ZH = {
    'Planned': '计划中',
    'Completed': '已完成',
    'Canceled': '已取消',
}


management_required = user_passes_test(
    lambda user: user.is_authenticated and (user.is_staff or user.is_superuser),
    login_url='index',
)


@management_required
def management_dashboard(request):
    teams = ResearchGroup.objects.prefetch_related('members__user').order_by('group_name')
    projects = Project.objects.select_related('project__group', 'owner').order_by('-created_on')
    users = User.objects.select_related('profile__research_group').order_by('username')
    step_templates = StepNameTemplate.objects.order_by('category', 'step_code')
    return render(request, 'experiment_flow/management_dashboard.html', {
        'teams': teams,
        'managed_projects': projects,
        'managed_users': users,
        'step_templates': step_templates,
        'team_form': TeamManagementForm(),
        'project_create_form': ProjectCreateForm(),
        'member_form': ManagedUserForm(),
        'step_template_form': StepTemplateManagementForm(),
    })


def management_redirect(tab):
    return redirect(f"{reverse('management_dashboard')}#{tab}")


@management_required
def add_team(request):
    if request.method == 'POST':
        form = TeamManagementForm(request.POST)
        if form.is_valid():
            team = form.save()
            ProjectCategory.objects.get_or_create(
                group=team,
                defaults={'project_name': team.group_name, 'project_code': team.team_code},
            )
            messages.success(request, f'Team {team} 已创建。')
        else:
            messages.error(request, 'Team 创建失败：' + ' '.join(form.non_field_errors() or [str(form.errors)]))
    return management_redirect('teams')


@management_required
def edit_team(request, team_id):
    team = get_object_or_404(ResearchGroup, id=team_id)
    if request.method == 'POST':
        old_code = team.team_code
        form = TeamManagementForm(request.POST, instance=team)
        if form.is_valid():
            team = form.save()
            category = ProjectCategory.objects.filter(group=team).order_by('id').first()
            if category and category.project_code == old_code:
                category.project_code = team.team_code
                category.save(update_fields=['project_code'])
            messages.success(request, f'Team {team} 已更新。')
        else:
            messages.error(request, 'Team 更新失败：' + str(form.errors))
    return management_redirect('teams')


@management_required
def delete_team(request, team_id):
    team = get_object_or_404(ResearchGroup, id=team_id)
    if request.method == 'POST':
        name = str(team)
        team.delete()
        messages.success(request, f'Team {name} 已删除。')
    return management_redirect('teams')


@management_required
def assign_member_team(request, user_id):
    member = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = MemberTeamForm(request.POST)
        if form.is_valid():
            profile, _ = UserProfile.objects.get_or_create(user=member)
            profile.research_group = form.cleaned_data['research_group']
            profile.save(update_fields=['research_group'])
            messages.success(request, f'{member.username} 的 Team 已更新。')
    return management_redirect('members')


@management_required
def edit_managed_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        form = ProjectManagementForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f'项目 {project.exp_name} 已更新。')
        else:
            messages.error(request, '项目更新失败：' + str(form.errors))
    return management_redirect('projects')


@management_required
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
            messages.success(request, f'项目 {project.exp_name} 已创建。')
        else:
            messages.error(request, '项目创建失败：' + str(form.errors))
    return management_redirect('projects')


@management_required
def delete_managed_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        name = project.exp_name
        project.delete()
        messages.success(request, f'项目 {name} 已删除。')
    return management_redirect('projects')


@management_required
def add_managed_user(request):
    if request.method == 'POST':
        form = ManagedUserForm(request.POST)
        if form.is_valid():
            member = form.save()
            messages.success(request, f'成员 {member.username} 已创建。')
        else:
            messages.error(request, '成员创建失败：' + str(form.errors))
    return management_redirect('members')


@management_required
def edit_managed_user(request, user_id):
    member = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = ManagedUserForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, f'成员 {member.username} 已更新。')
        else:
            messages.error(request, '成员更新失败：' + str(form.errors))
    return management_redirect('members')


@management_required
def delete_managed_user(request, user_id):
    member = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        if member == request.user:
            messages.error(request, '不能删除当前登录账号。')
        elif member.is_superuser and not request.user.is_superuser:
            messages.error(request, '只有超级管理员可以删除超级管理员账号。')
        else:
            username = member.username
            member.delete()
            messages.success(request, f'成员 {username} 已删除。')
    return management_redirect('members')


@management_required
def add_step_template(request):
    if request.method == 'POST':
        form = StepTemplateManagementForm(request.POST)
        if form.is_valid():
            template = form.save()
            messages.success(request, f'步骤模板 {template} 已创建。')
        else:
            messages.error(request, '步骤模板创建失败：' + str(form.errors))
    return management_redirect('steps')


@management_required
def edit_step_template(request, template_id):
    template = get_object_or_404(StepNameTemplate, id=template_id)
    if request.method == 'POST':
        form = StepTemplateManagementForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, f'步骤模板 {template} 已更新。')
        else:
            messages.error(request, '步骤模板更新失败：' + str(form.errors))
    return management_redirect('steps')


@management_required
def delete_step_template(request, template_id):
    template = get_object_or_404(StepNameTemplate, id=template_id)
    if request.method == 'POST':
        name = str(template)
        template.delete()
        messages.success(request, f'步骤模板 {name} 已删除。')
    return management_redirect('steps')


def step_has_downstream_steps(step):
    """Return True when another step depends on this step."""
    return step.children.exists() or step.child.exists()


def save_raw_material_usages(step, usages_json):
    """Replace structured raw material usage records for a step."""
    try:
        usages = json.loads(usages_json or '[]')
    except json.JSONDecodeError:
        usages = []

    StepRawMaterialUsage.objects.filter(step=step).delete()
    seen_material_ids = set()

    for usage in usages:
        try:
            raw_material_id = int(usage.get('raw_material_id'))
        except (TypeError, ValueError):
            continue
        if not raw_material_id or raw_material_id in seen_material_ids:
            continue

        try:
            raw_material = RawMaterial.objects.get(id=raw_material_id)
        except RawMaterial.DoesNotExist:
            continue

        seen_material_ids.add(raw_material_id)
        quantity = usage.get('quantity')
        if quantity == '':
            quantity = None
        elif quantity is not None:
            try:
                quantity = Decimal(str(quantity))
            except (InvalidOperation, ValueError):
                quantity = None

        StepRawMaterialUsage.objects.create(
            step=step,
            raw_material=raw_material,
            quantity=quantity,
            unit=(usage.get('unit') or '').strip() or None,
            notes=(usage.get('notes') or '').strip() or None,
        )


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
            Q(project__group__group_name__icontains=search_query)
        )

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
            # Redirect to 'next' parameter if present, otherwise to index
            next_url = request.GET.get('next', 'index')
            return redirect(next_url)
        else:
            messages.error(request, '用户名或密码不正确。')

    return render(request, 'experiment_flow/login.html')

def logout_view(request):
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
        messages.error(request, '你没有权限查看该实验。')
        return redirect('index')
    project_experiments = Experiment.objects.filter(project=experiment).order_by('created_on')
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
        'search_query': search_query
    })

@login_required
def delete_project_experiment(request, exp_id, experiment_id):

    experiment = Project.objects.get(id=exp_id)
    project_experiment = Experiment.objects.get(id=experiment_id)
    project_experiment.delete()

    return redirect('experiment_detail', exp_id=exp_id)

@login_required
def delete_step(request, exp_id, experiment_id, step_id):

    step = ExperimentStep.objects.get(id=step_id, experiment_id=experiment_id)
    if step_has_downstream_steps(step):
        messages.error(request, '该步骤已有下游关联步骤，无法删除。请先移除下游步骤的前置关系。')
        return redirect(f'/experiment/{exp_id}/?expanded_experiment={experiment_id}')

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
                new_exp.save()
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'experiment_id': new_exp.id,
                        'experiment_name': new_exp.exp_name,
                        'redirect_url': reverse('experiment_detail', args=[new_exp.id])
                    })
                return redirect('index')
            except ResearchGroup.DoesNotExist:
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
                messages.error(request, "你没有权限访问该实验。")
                return redirect('index')

        if request.method == 'POST':
            experiment_code = request.POST.get('experiment_code')
            if experiment_code:
                try:
                    new_experiment = Experiment(experiment_code=experiment_code, project=experiment)
                    new_experiment.save()

                    # Return JSON for AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'experiment_id': new_experiment.id,
                            'experiment_code': new_experiment.full_experiment_code
                        })

                    return redirect('experiment_detail', exp_id=exp_id)
                except ValidationError as e:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': str(e)
                        })

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
                        'error': str(e)
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
            'search_query': search_query
        })
    except Project.DoesNotExist:
        return HttpResponse('未找到实验', status=404)

@login_required
def add_step(request, exp_id, experiment_id):

    experiment = Project.objects.get(id=exp_id)
    project_experiment = Experiment.objects.get(id=experiment_id)

    if request.method == 'POST':
        form = ExperimentStepForm(request.POST, experiment=project_experiment)
        if form.is_valid():
            step = form.save(commit=False)
            step.experiment = project_experiment
            step.save()
            form.save_m2m()
            sync_legacy_parent(step)
            save_raw_material_usages(step, request.POST.get('raw_material_usages', '[]'))

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
        'raw_materials': RawMaterial.objects.filter(is_active=True).order_by('material_code', 'batch_number'),
        'is_add': True  # Flag to indicate this is add mode, not edit mode
    })

@login_required
def edit_step(request, exp_id, experiment_id, step_id):
    step = get_object_or_404(ExperimentStep, id=step_id, experiment_id=experiment_id)
    project_experiment = get_object_or_404(Experiment, id=experiment_id)

    if request.method == 'POST':
        form = ExperimentStepForm(request.POST, instance=step, experiment=project_experiment)
        if form.is_valid():
            step = form.save(commit=False)
            # Ensure the step is associated with the correct project_experiment
            step.experiment = project_experiment
            step.save()
            form.save_m2m()
            sync_legacy_parent(step)
            save_raw_material_usages(step, request.POST.get('raw_material_usages', '[]'))

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
            'raw_materials': RawMaterial.objects.filter(Q(is_active=True) | Q(step_usages__step=step)).distinct().order_by('material_code', 'batch_number'),
        }
    )

@login_required
def step_genealogy(request, step_id):
    step = get_object_or_404(
        ExperimentStep.objects
        .select_related('experiment__project__project__group', 'tool')
        .prefetch_related('raw_material_usages__raw_material'),
        id=step_id
    )

    if not user_can_access_step(request.user, step):
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
            project_experiment.experiment_description = desc
            project_experiment.save()
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
            step.step_description = data.get('description', '')
            step.save()
            return JsonResponse({'success': True})
        except ExperimentStep.DoesNotExist:
            return JsonResponse({'success': False, 'error': '未找到步骤'})
    return JsonResponse({'success': False, 'error': '无效请求'})

@login_required
def update_step_status(request, step_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step = ExperimentStep.objects.get(id=step_id)
            new_status = data.get('status', '')

            # Validate status
            valid_statuses = ['Planned', 'Completed', 'Canceled']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'error': '无效状态'})

            # Update status
            step.status = new_status

            # If status is Completed, update completed_on timestamp
            if new_status == 'Completed':
                from django.utils import timezone
                step.completed_on = timezone.now()

            step.save()

            # Return success with completed_on timestamp if applicable
            response_data = {'success': True}
            if new_status == 'Completed' and step.completed_on:
                response_data['completed_on'] = step.completed_on.strftime('%Y-%m-%d %H:%M:%S')

            return JsonResponse(response_data)
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
            steps = ExperimentStep.objects.filter(
                id__in=step_ids,
                experiment__project_id=exp_id
            )

            if not steps.exists():
                return JsonResponse({'success': False, 'error': '未找到有效步骤'})

            # Update all steps
            from django.utils import timezone
            updated_count = 0
            for step in steps:
                step.status = new_status
                if new_status == 'Completed':
                    step.completed_on = timezone.now()
                step.save()
                updated_count += 1

            return JsonResponse({
                'success': True,
                'updated_count': updated_count,
                'message': f'已将 {updated_count} 个步骤更新为 {STATUS_LABELS_ZH.get(new_status, new_status)}'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
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
                .filter(id__in=step_ids)
                .prefetch_related('parents', 'raw_material_usages__raw_material')
                .order_by('step_number')
            )

            if not steps_to_copy:
                return JsonResponse({'success': False, 'error': '未找到所选步骤'})

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
            return JsonResponse({
                'success': True,
                'message': f'已复制 {copied_count} 个步骤到实验 {target_experiment.full_experiment_code}（项目 {target_exp_name}）',
                'copied_count': copied_count
            })

        except Exception as e:
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

            # Count before deletion
            deleted_count = steps_to_delete.count()

            # Delete the steps
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
            form.save()
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
        form = EquipmentForm(request.POST, instance=equipment)
        if form.is_valid():
            form.save()
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

    return render(request, 'experiment_flow/raw_material_list.html', {
        'raw_material_list': page_obj,
        'page_obj': page_obj,
        'search_query': search_query
    })

@login_required
def raw_material_detail(request, raw_material_id):
    raw_material = get_object_or_404(RawMaterial, id=raw_material_id)
    usages = raw_material.step_usages.select_related(
        'step__experiment__project',
        'raw_material'
    ).order_by('-updated_on')
    return render(request, 'experiment_flow/raw_material_detail.html', {
        'raw_material': raw_material,
        'usages': usages
    })

@login_required
def add_raw_material(request):
    if request.method == 'POST':
        form = RawMaterialForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('raw_material_list')
    else:
        form = RawMaterialForm()

    return render(request, 'experiment_flow/add_raw_material.html', {
        'form': form
    })

@login_required
def edit_raw_material(request, raw_material_id):
    raw_material = get_object_or_404(RawMaterial, id=raw_material_id)

    if request.method == 'POST':
        form = RawMaterialForm(request.POST, instance=raw_material)
        if form.is_valid():
            form.save()
            return redirect('raw_material_detail', raw_material_id=raw_material_id)
    else:
        form = RawMaterialForm(instance=raw_material)

    return render(request, 'experiment_flow/edit_raw_material.html', {
        'form': form,
        'raw_material': raw_material
    })

@login_required
def get_raw_materials(request):
    raw_materials = RawMaterial.objects.filter(is_active=True).select_related('owner').order_by('material_code', 'batch_number')
    data = []
    for material in raw_materials:
        data.append({
            'id': material.id,
            'material_code': material.material_code,
            'batch_number': material.batch_number,
            'received_date': material.received_date.isoformat() if material.received_date else '',
            'material_type': material.material_type or '',
            'material_name': material.material_name,
            'supplier': material.supplier or '',
            'location': material.location or '',
            'owner': material.owner.get_full_name() if material.owner and material.owner.get_full_name() else (material.owner.username if material.owner else ''),
            'label': material.batch_number,
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
    Global search for experiments and steps by their full codes.
    Searches full_experiment_code (e.g., MLO001AB) or full_step (e.g., MLO001AB-MX00).
    Redirects to the project detail page with the experiment expanded.
    """
    query = request.GET.get('q', '').strip().upper()

    if not query:
        messages.warning(request, '请输入搜索内容。')
        return redirect('index')

    # First, try to find an experiment by full_experiment_code code
    try:
        project_experiment = Experiment.objects.get(full_experiment_code=query)
        # Redirect to the project with the experiment expanded
        return redirect(f'/experiment/{project_experiment.project.id}/?expanded_experiment={project_experiment.id}')
    except Experiment.DoesNotExist:
        pass

    # Next, try to find a step by full_step code
    try:
        step = ExperimentStep.objects.get(full_step=query)
        # Redirect to the project with the experiment expanded
        return redirect(f'/experiment/{step.experiment.project.id}/?expanded_experiment={step.experiment.id}&highlight_step={step.id}')
    except ExperimentStep.DoesNotExist:
        pass

    # If nothing found, show error and redirect back
    messages.error(request, f'未找到匹配 "{query}" 的实验或步骤。')
    return redirect('index')
