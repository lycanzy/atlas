from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Exp, ExpFlow, ExpStep, Project, ResearchGroup, Equipment, RawMaterial, StepRawMaterialUsage
from .forms import ExpStepForm, ExpFlowForm, EquipmentForm, RawMaterialForm, CustomPasswordChangeForm
import json
import string
from decimal import Decimal, InvalidOperation


STATUS_LABELS_ZH = {
    'Planned': '计划中',
    'Completed': '已完成',
    'Canceled': '已取消',
}


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
    """Return a queryset of Exp filtered to the user's research group.

    Staff and superusers can see all experiments.
    Regular users see only experiments in their research group.
    If the user has no profile or no research_group, return an empty queryset.
    """
    # Staff and superusers can access all experiments
    if user.is_staff or user.is_superuser:
        qs = Exp.objects.all().order_by('-created_on')
    else:
        # Regular users: filter by research group
        rg = None
        profile = getattr(user, 'profile', None)
        if profile:
            rg = getattr(profile, 'research_group', None)

        if not rg:
            return Exp.objects.none()

        qs = Exp.objects.filter(project__group=rg).order_by('-created_on')

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

# Helper function to generate available flow codes
def get_available_flow_codes(experiment):
    """Generate list of available 2-letter codes not used in this experiment"""
    # Get all existing flow names for this experiment
    existing_flows = ExpFlow.objects.filter(exp=experiment).values_list('flow_name', flat=True)
    existing_flows_set = set(existing_flows)
    
    # Generate all possible 2-letter combinations (AA-ZZ)
    all_codes = [f"{a}{b}" for a in string.ascii_uppercase for b in string.ascii_uppercase]
    
    # Return codes that are not used
    available_codes = [code for code in all_codes if code not in existing_flows_set]
    
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
    experiment = getattr(getattr(step, 'flow', None), 'exp', None)
    return bool(experiment and user_can_access_experiment(user, experiment))


def build_step_ancestor_chain(step):
    ancestors = []
    seen_ids = {step.id}
    current = step.parent
    while current and current.id not in seen_ids:
        ancestors.append(current)
        seen_ids.add(current.id)
        current = current.parent
    ancestors.reverse()
    return ancestors


def build_step_descendant_tree(step, user=None, seen_ids=None):
    seen_ids = seen_ids or set()
    if step.id in seen_ids:
        return []
    seen_ids.add(step.id)

    descendants = []
    children = (
        step.child
        .select_related('flow__exp', 'tool')
        .prefetch_related('raw_material_usages__raw_material')
        .order_by('flow__exp__exp_name', 'flow__flow_name', 'step_name', 'step_number')
    )
    for child in children:
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
            'flow': step.flow.full_flow if step.flow else '',
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


def add_genealogy_descendant_elements(elements, parent_step, descendants, depth, y_cursor, x_origin=220, x_gap=290, y_gap=210):
    parent_node_id = f"step-{parent_step.id}"
    for node in descendants:
        child = node['step']
        y = y_cursor[0]
        x = x_origin + depth * x_gap
        add_genealogy_step_element(elements, child, x, y)
        elements.append({
            'group': 'edges',
            'data': {
                'id': f"step-edge-{parent_step.id}-{child.id}",
                'source': parent_node_id,
                'target': f"step-{child.id}",
                'type': 'step',
            },
            'classes': 'step-edge',
        })
        child_start_y = y_cursor[0]
        y_cursor[0] += y_gap
        if node['children']:
            add_genealogy_descendant_elements(elements, child, node['children'], depth + 1, y_cursor, x_origin=x_origin, x_gap=x_gap, y_gap=y_gap)
            child_end_y = y_cursor[0] - y_gap
            midpoint_y = (child_start_y + child_end_y) / 2
            for element in elements:
                if element.get('data', {}).get('id') == f"step-{child.id}":
                    element['position']['y'] = midpoint_y
                    break


def build_genealogy_graph(step, upstream_steps, downstream_tree):
    elements = []
    x_origin = 220
    x_gap = 290
    upstream_count = len(upstream_steps)
    current_x = x_origin + upstream_count * x_gap
    current_y = 300

    for index, upstream_step in enumerate(upstream_steps):
        x = x_origin + index * x_gap
        add_genealogy_step_element(elements, upstream_step, x, current_y)
        next_step = upstream_steps[index + 1] if index + 1 < upstream_count else step
        elements.append({
            'group': 'edges',
            'data': {
                'id': f"step-edge-{upstream_step.id}-{next_step.id}",
                'source': f"step-{upstream_step.id}",
                'target': f"step-{next_step.id}",
                'type': 'step',
            },
            'classes': 'step-edge',
        })

    add_genealogy_step_element(elements, step, current_x, current_y, is_current=True)
    y_cursor = [current_y]
    add_genealogy_descendant_elements(elements, step, downstream_tree, upstream_count + 1, y_cursor, x_origin=x_origin, x_gap=x_gap)
    return {'elements': elements}

# Create your views here.

@login_required
def index(request):

    search_query = request.GET.get('search', '')
    my_experiments = request.GET.get('my_experiments', '')
    # Use group-restricted queryset helper
    latest_exp = get_experiments_for_user(request.user, search_query, my_experiments)
    
    page_number = request.GET.get('page', 1)
    paginator = Paginator(latest_exp, 10)  # 10 experiments per page
    page_obj = paginator.get_page(page_number)

    return render(request, 'experiment_flow/index.html', {
        'experiments': page_obj, 
        'page_obj': page_obj,
        'search_query': search_query
    })

@login_required
def experiment_detail(request, exp_id):
    
    experiment = Exp.objects.get(id=exp_id)
    # Security: ensure the current user is in the same research group as the experiment's project
    # Staff and superusers can access all experiments
    if not user_can_access_experiment(request.user, experiment):
        messages.error(request, '你没有权限查看该实验。')
        return redirect('index')
    flows = ExpFlow.objects.filter(exp=experiment).order_by('created_on')
    available_flow_codes = get_available_flow_codes(experiment)
    
    search_query = request.GET.get('search', '')
    my_experiments = request.GET.get('my_experiments', '')
    latest_exp = get_experiments_for_user(request.user, search_query, my_experiments)
    
    page_number = request.GET.get('page', 1)
    paginator = Paginator(latest_exp, 10)  # 10 experiments per page
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'experiment_flow/experiment_detail.html', {
        'experiment': experiment, 
        'flows': flows, 
        'available_flow_codes': available_flow_codes,
        'experiments': page_obj, 
        'page_obj': page_obj,
        'search_query': search_query
    }) 

@login_required
def delete_flow(request, exp_id, flow_id):

    experiment = Exp.objects.get(id=exp_id)
    flow = ExpFlow.objects.get(id=flow_id)
    flow.delete()

    return redirect('experiment_detail', exp_id=exp_id)

@login_required
def delete_step(request, exp_id, flow_id, step_id):

    step = ExpStep.objects.get(id=step_id)
    step.delete()

    return redirect(f'/experiment/{exp_id}/?expanded_flow={flow_id}')

@login_required
def add_experiment(request):
    # Show Teams directly. The Project row is now an internal backing record
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

                project = Project.objects.filter(group=team).order_by("id").first()
                if not project:
                    project = Project.objects.create(
                        group=team,
                        project_code=team.team_code,
                        project_name=team.group_name,
                    )
                elif project.project_code != team.team_code:
                    project.project_code = team.team_code
                    project.save(update_fields=["project_code"])
                
                exp_name = project.generate_experiment_name()
                exp_description = request.POST.get('exp_description')
                new_exp = Exp(
                    exp_name=exp_name,
                    project=project,
                    exp_description=exp_description,
                    owner=request.user  # Automatically set the logged-in user as owner
                )
                new_exp.save()
                return redirect('index')
            except ResearchGroup.DoesNotExist:
                return render(request, 'experiment_flow/add_experiment.html', {
                    'teams': teams,
                    'experiments': page_obj,
                    'page_obj': page_obj,
                    'search_query': search_query,
                    'error': '未找到所选 Team。Selected team not found.'
                })
            except ValidationError as e:
                return render(request, 'experiment_flow/add_experiment.html', {
                    'teams': teams,
                    'experiments': page_obj,
                    'page_obj': page_obj,
                    'search_query': search_query,
                    'error': str(e)
                })
        
    return render(request, 'experiment_flow/add_experiment.html', {
        'teams': teams,
        'experiments': page_obj, 
        'page_obj': page_obj,
        'search_query': search_query
    })

@login_required
def add_flow(request, exp_id):
    try:
        experiment = get_object_or_404(Exp, id=exp_id)
        # Security: ensure the user is in the same research group as the experiment
        # Staff and superusers can access all experiments
        if not (request.user.is_staff or request.user.is_superuser):
            profile = getattr(request.user, 'profile', None)
            user_group = getattr(profile, 'research_group', None)
            if not user_group or not getattr(experiment, 'project', None) or experiment.project.group != user_group:
                messages.error(request, "你没有权限访问该实验。")
                return redirect('index')
        
        if request.method == 'POST':
            flow_name = request.POST.get('flow_name')
            if flow_name:
                try:
                    new_flow = ExpFlow(flow_name=flow_name, exp=experiment)
                    new_flow.save()
                    
                    # Return JSON for AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'flow_id': new_flow.id,
                            'flow_name': new_flow.full_flow
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

                    return render(request, 'experiment_flow/add_flow.html', {
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
        
        return render(request, 'experiment_flow/add_flow.html', {
            'experiment': experiment, 
            'experiments': page_obj, 
            'page_obj': page_obj,
            'search_query': search_query
        })
    except Exp.DoesNotExist:
        return HttpResponse('未找到实验', status=404)

@login_required
def add_step(request, exp_id, flow_id):
    
    experiment = Exp.objects.get(id=exp_id)
    flow = ExpFlow.objects.get(id=flow_id)
    
    if request.method == 'POST':
        form = ExpStepForm(request.POST, flow=flow)
        if form.is_valid():
            step = form.save(commit=False)
            step.flow = flow
            step.save()
            save_raw_material_usages(step, request.POST.get('raw_material_usages', '[]'))
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'redirect_url': f'/experiment/{exp_id}/?expanded_flow={flow_id}'
                })
            
            return redirect(f'/experiment/{exp_id}/?expanded_flow={flow_id}')
        else:
            # Return errors for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    else:
        form = ExpStepForm(flow=flow)
    
    # Render the form (for both GET and non-AJAX POST with errors)
    return render(request, 'experiment_flow/add_step.html', {
        'experiment': experiment,
        'flow': flow,
        'form': form,
        'raw_materials': RawMaterial.objects.filter(is_active=True).order_by('material_code', 'batch_number'),
        'is_add': True  # Flag to indicate this is add mode, not edit mode
    })

@login_required
def edit_step(request, exp_id, flow_id, step_id):
    step = get_object_or_404(ExpStep, id=step_id, flow_id=flow_id)
    flow = get_object_or_404(ExpFlow, id=flow_id)
    
    if request.method == 'POST':
        form = ExpStepForm(request.POST, instance=step, flow=flow)
        if form.is_valid():
            step = form.save(commit=False)
            # Ensure the step is associated with the correct flow
            step.flow = flow
            step.save()
            save_raw_material_usages(step, request.POST.get('raw_material_usages', '[]'))
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'redirect_url': f'/experiment/{exp_id}/?expanded_flow={flow_id}'
                })
            # Regular form submission redirect
            return redirect(f'/experiment/{exp_id}/?expanded_flow={flow_id}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
            # If not AJAX, re-render the form with errors
    else:
        form = ExpStepForm(instance=step, flow=flow)
    
    return render(
        request,
        'experiment_flow/edit_step.html',
        {
            'form': form,
            'step': step,
            'flow': flow,
            'raw_materials': RawMaterial.objects.filter(Q(is_active=True) | Q(step_usages__step=step)).distinct().order_by('material_code', 'batch_number'),
        }
    )

@login_required
def step_genealogy(request, step_id):
    step = get_object_or_404(
        ExpStep.objects
        .select_related('flow__exp__project__group', 'parent', 'tool')
        .prefetch_related('raw_material_usages__raw_material'),
        id=step_id
    )

    if not user_can_access_step(request.user, step):
        messages.error(request, '你没有权限查看该步骤谱系。')
        return redirect('index')

    ancestor_chain = build_step_ancestor_chain(step)
    ancestor_ids = [ancestor.id for ancestor in ancestor_chain]
    ancestors_qs = (
        ExpStep.objects
        .filter(id__in=ancestor_ids)
        .select_related('flow__exp', 'tool')
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
    genealogy_graph = build_genealogy_graph(step, upstream_steps, downstream_tree)

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
        'experiment': step.flow.exp,
    })

@login_required
def update_flow_desc(request, flow_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        desc = data.get('description', '')
        try:
            flow = ExpFlow.objects.get(id=flow_id)
            flow.flow_description = desc
            flow.save()
            return JsonResponse({'success': True})
        except ExpFlow.DoesNotExist:
            return JsonResponse({'success': False}, status=404)
    return JsonResponse({'success': False}, status=400)

@login_required
def update_step_desc(request, step_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step = ExpStep.objects.get(id=step_id)
            step.step_description = data.get('description', '')
            step.save()
            return JsonResponse({'success': True})
        except ExpStep.DoesNotExist:
            return JsonResponse({'success': False, 'error': '未找到步骤'})
    return JsonResponse({'success': False, 'error': '无效请求'})

@login_required
def update_step_status(request, step_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step = ExpStep.objects.get(id=step_id)
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
        except ExpStep.DoesNotExist:
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
            steps = ExpStep.objects.filter(
                id__in=step_ids,
                flow__exp_id=exp_id
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
            target_flow_name = data.get('target_flow_name', '')  # Full flow name like "MLO001AA"
            
            if not step_ids:
                return JsonResponse({'success': False, 'error': '未选择步骤'})
            
            if not target_flow_name:
                return JsonResponse({'success': False, 'error': '请输入目标实验编号'})
            
            # Get all experiments accessible to the user
            experiments = get_experiments_for_user(request.user)
            
            # Find the target flow by full_flow name across all accessible experiments
            target_flow = None
            for exp in experiments:
                try:
                    target_flow = ExpFlow.objects.get(full_flow=target_flow_name, exp=exp)
                    break
                except ExpFlow.DoesNotExist:
                    continue
            
            if not target_flow:
                return JsonResponse({'success': False, 'error': f'实验 "{target_flow_name}" 不存在，或你没有访问权限'})
            
            # Get the selected steps
            steps_to_copy = ExpStep.objects.filter(id__in=step_ids).order_by('step_number')
            
            if not steps_to_copy:
                return JsonResponse({'success': False, 'error': '未找到所选步骤'})
            
            copied_count = 0

            # We'll keep a mapping from original step id -> new step instance
            # This allows us to restore parent relationships for copied steps
            orig_to_new = {}

            # Copy each step to the target flow (first pass: create steps)
            for original_step in steps_to_copy:
                # Get the step name (just the 2-letter code, e.g., "MX")
                step_name = original_step.step_name
                
                # Find existing steps with the same name in target flow
                existing_steps = ExpStep.objects.filter(
                    flow=target_flow,
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
                new_step = ExpStep(
                    step_name=step_name,  # Just the 2-letter code (e.g., "MX")
                    step_number=new_step_number,  # The number part (e.g., "01")
                    step_description=original_step.step_description,
                    flow=target_flow,
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
            
            # Second pass: restore parent relationships.
            # If the parent was copied in the same batch, point to the copied parent.
            # Otherwise keep the original parent so a copied child still preserves traceability.
            for original_step in steps_to_copy:
                new_step = orig_to_new.get(original_step.id)
                if not new_step:
                    continue
                if original_step.parent:
                    new_step.parent = orig_to_new.get(original_step.parent.id, original_step.parent)
                    new_step.save()

            target_exp_name = target_flow.exp.exp_name if target_flow.exp else "未知"
            return JsonResponse({
                'success': True,
                'message': f'已复制 {copied_count} 个步骤到实验 {target_flow.full_flow}（项目 {target_exp_name}）',
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
            steps_to_delete = ExpStep.objects.filter(id__in=step_ids)
            
            if not steps_to_delete:
                return JsonResponse({'success': False, 'error': '未找到所选步骤'})
            
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
        'step__flow__exp',
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
        steps = ExpStep.objects.all().select_related('flow', 'flow__exp').order_by('-started_on')
    else:
        # Get user's research group
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return JsonResponse({'steps': []})
        
        rg = getattr(profile, 'research_group', None)
        if not rg:
            return JsonResponse({'steps': []})
        
        # Get all steps from experiments in the user's research group
        steps = ExpStep.objects.filter(
            flow__exp__project__group=rg
        ).select_related('flow', 'flow__exp').order_by('-started_on')
    
    # Format step data
    steps_data = []
    for step in steps:
        steps_data.append({
            'id': step.id,
            'full_step': step.full_step,
            'step_name': f"{step.step_name}{step.step_number}",
            'flow': step.flow.full_flow if step.flow else '',
            'experiment': step.flow.exp.exp_name if step.flow and step.flow.exp else ''
        })
    
    return JsonResponse({'steps': steps_data})

@login_required
def get_experiments_with_flows(request):
    """API endpoint to get all experiments with their flows for copy step dropdown"""
    # Get experiments visible to user
    experiments = get_experiments_for_user(request.user)
    
    # Format data
    experiments_data = []
    for exp in experiments:
        flows_data = []
        for flow in exp.flow.all().order_by('flow_name'):
            flows_data.append({
                'id': flow.id,
                'full_flow': flow.full_flow,
                'flow_name': flow.flow_name,
                'flow_description': flow.flow_description or ''
            })
        
        experiments_data.append({
            'id': exp.id,
            'exp_name': exp.exp_name,
            'exp_description': exp.exp_description or '',
            'flows': flows_data
        })
    
    return JsonResponse({'experiments': experiments_data})


@login_required
def global_search(request):
    """
    Global search for flows and steps by their full codes.
    Searches full_flow (e.g., MLO001AB) or full_step (e.g., MLO001AB-MX00).
    Redirects to the experiment detail page with the flow expanded.
    """
    query = request.GET.get('q', '').strip().upper()
    
    if not query:
        messages.warning(request, '请输入搜索内容。')
        return redirect('index')
    
    # First, try to find a flow by full_flow code
    try:
        flow = ExpFlow.objects.get(full_flow=query)
        # Redirect to the experiment with the flow expanded
        return redirect(f'/experiment/{flow.exp.id}/?expanded_flow={flow.id}')
    except ExpFlow.DoesNotExist:
        pass
    
    # Next, try to find a step by full_step code
    try:
        step = ExpStep.objects.get(full_step=query)
        # Redirect to the experiment with the flow expanded
        return redirect(f'/experiment/{step.flow.exp.id}/?expanded_flow={step.flow.id}&highlight_step={step.id}')
    except ExpStep.DoesNotExist:
        pass
    
    # If nothing found, show error and redirect back
    messages.error(request, f'未找到匹配 "{query}" 的实验或步骤。')
    return redirect('index')
