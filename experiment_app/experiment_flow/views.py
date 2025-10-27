from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Exp, ExpFlow, ExpStep, Project, Equipment
from .forms import ExpStepForm, ExpFlowForm, EquipmentForm, CustomPasswordChangeForm
import json
import string

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
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'experiment_flow/login.html')

def logout_view(request):
    auth_logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')

@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session auth hash to prevent logout
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('index')
        else:
            messages.error(request, 'Please correct the errors below.')
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

# Create your views here.

@login_required
def index(request):

    search_query = request.GET.get('search', '')
    my_experiments = request.GET.get('my_experiments', '')
    latest_exp = Exp.objects.order_by('-created_on')
    
    # Filter by owner if my_experiments is set
    if my_experiments == '1':
        latest_exp = latest_exp.filter(owner=request.user)
    
    if search_query:
        latest_exp = latest_exp.filter(
            Q(exp_name__icontains=search_query) | 
            Q(exp_description__icontains=search_query) |
            Q(project__project_name__icontains=search_query)
        )
    
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
    flows = ExpFlow.objects.filter(exp=experiment).order_by('created_on')
    available_flow_codes = get_available_flow_codes(experiment)
    
    search_query = request.GET.get('search', '')
    my_experiments = request.GET.get('my_experiments', '')
    latest_exp = Exp.objects.order_by('-created_on')
    
    # Filter by owner if my_experiments is set
    if my_experiments == '1':
        latest_exp = latest_exp.filter(owner=request.user)
    
    if search_query:
        latest_exp = latest_exp.filter(
            Q(exp_name__icontains=search_query) | 
            Q(exp_description__icontains=search_query) |
            Q(project__project_name__icontains=search_query)
        )
    
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
    projects = Project.objects.all().order_by('project_name')
    
    search_query = request.GET.get('search', '')
    my_experiments = request.GET.get('my_experiments', '')
    latest_exp = Exp.objects.order_by('-created_on')
    
    # Filter by owner if my_experiments is set
    if my_experiments == '1':
        latest_exp = latest_exp.filter(owner=request.user)
    
    if search_query:
        latest_exp = latest_exp.filter(
            Q(exp_name__icontains=search_query) | 
            Q(exp_description__icontains=search_query) |
            Q(project__project_name__icontains=search_query)
        )
    
    page_number = request.GET.get('page', 1)
    paginator = Paginator(latest_exp, 10)
    page_obj = paginator.get_page(page_number)

    if request.method == 'POST':
        project_id = request.POST.get('project')
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
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
            except Project.DoesNotExist:
                return render(request, 'experiment_flow/add_experiment.html', {
                    'projects': projects,
                    'experiments': page_obj,
                    'page_obj': page_obj,
                    'search_query': search_query,
                    'error': 'Selected project not found.'
                })
            except ValidationError as e:
                return render(request, 'experiment_flow/add_experiment.html', {
                    'projects': projects,
                    'experiments': page_obj,
                    'page_obj': page_obj,
                    'search_query': search_query,
                    'error': str(e)
                })
        
    return render(request, 'experiment_flow/add_experiment.html', {
        'projects': projects, 
        'experiments': page_obj, 
        'page_obj': page_obj,
        'search_query': search_query
    })

@login_required
def add_flow(request, exp_id):
    try:
        experiment = get_object_or_404(Exp, id=exp_id)
        
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
                    latest_exp = Exp.objects.order_by('-created_on')
                    
                    # Filter by owner if my_experiments is set
                    if my_experiments == '1':
                        latest_exp = latest_exp.filter(owner=request.user)
                    
                    if search_query:
                        latest_exp = latest_exp.filter(
                            Q(exp_name__icontains=search_query) | 
                            Q(exp_description__icontains=search_query) |
                            Q(project__project_name__icontains=search_query)
                        )
                    
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
        latest_exp = Exp.objects.order_by('-created_on')
        
        # Filter by owner if my_experiments is set
        if my_experiments == '1':
            latest_exp = latest_exp.filter(owner=request.user)
        
        if search_query:
            latest_exp = latest_exp.filter(
                Q(exp_name__icontains=search_query) | 
                Q(exp_description__icontains=search_query) |
                Q(project__project_name__icontains=search_query)
            )
        
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
        return HttpResponse('Experiment not found', status=404)

@login_required
def add_step(request, exp_id, flow_id):
    
    experiment = Exp.objects.get(id=exp_id)
    flow = ExpFlow.objects.get(id=flow_id)
    
    if request.method == 'POST':
        form = ExpStepForm(request.POST, flow=flow)
        if form.is_valid():
            step = form.save(commit=False)
            step.flow = flow
            
            # Handle components data from JSON
            components_json = request.POST.get('components', '[]')
            try:
                step.components = json.loads(components_json)
            except json.JSONDecodeError:
                step.components = []
            
            step.save()
            
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
            
            # Handle components data from JSON
            components_json = request.POST.get('components', '[]')
            try:
                step.components = json.loads(components_json)
            except json.JSONDecodeError:
                step.components = []
            
            step.save()
            
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
        }
    )

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
            return JsonResponse({'success': False, 'error': 'Step not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

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
                return JsonResponse({'success': False, 'error': 'Invalid status'})
            
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
            return JsonResponse({'success': False, 'error': 'Step not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def copy_steps(request, exp_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step_ids = data.get('step_ids', [])
            target_flow_name = data.get('target_flow_name', '')
            
            if not step_ids:
                return JsonResponse({'success': False, 'error': 'No steps selected'})
            
            if not target_flow_name:
                return JsonResponse({'success': False, 'error': 'Target flow name is required'})
            
            # Get the experiment
            experiment = get_object_or_404(Exp, id=exp_id)
            
            # Find the target flow by full_flow name (e.g., "MLO001AB")
            try:
                target_flow = ExpFlow.objects.get(full_flow=target_flow_name, exp=experiment)
            except ExpFlow.DoesNotExist:
                return JsonResponse({'success': False, 'error': f'Flow "{target_flow_name}" does not exist in this experiment'})
            
            # Get the selected steps
            steps_to_copy = ExpStep.objects.filter(id__in=step_ids).order_by('step_number')
            
            if not steps_to_copy:
                return JsonResponse({'success': False, 'error': 'Selected steps not found'})
            
            copied_count = 0
            
            # Copy each step to the target flow
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
                    parent=None,  # Parent relationships are flow-specific, so reset
                    recipe=original_step.recipe,
                    notes=original_step.notes,
                    status="Planned",  # Always set to "Planned" regardless of original status
                    started_on=None,  # Reset timestamps for copied steps
                    completed_on=None
                )
                new_step.save()
                copied_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully copied {copied_count} step(s) to flow {target_flow.full_flow}',
                'copied_count': copied_count
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def delete_steps(request, exp_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            step_ids = data.get('step_ids', [])
            
            if not step_ids:
                return JsonResponse({'success': False, 'error': 'No steps selected'})
            
            # Get the steps to delete
            steps_to_delete = ExpStep.objects.filter(id__in=step_ids)
            
            if not steps_to_delete:
                return JsonResponse({'success': False, 'error': 'Selected steps not found'})
            
            # Count before deletion
            deleted_count = steps_to_delete.count()
            
            # Delete the steps
            steps_to_delete.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully deleted {deleted_count} step(s)',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


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

