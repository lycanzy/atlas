from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Exp, ExpFlow, ExpStep, Project
from .forms import ExpStepForm, ExpFlowForm
import json
import string

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

def index(request):

    search_query = request.GET.get('search', '')
    latest_exp = Exp.objects.order_by('-created_on')
    
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

def experiment_detail(request, exp_id):
    
    experiment = Exp.objects.get(id=exp_id)
    flows = ExpFlow.objects.filter(exp=experiment).order_by('created_on')
    available_flow_codes = get_available_flow_codes(experiment)
    
    search_query = request.GET.get('search', '')
    latest_exp = Exp.objects.order_by('-created_on')
    
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

def delete_flow(request, exp_id, flow_id):

    experiment = Exp.objects.get(id=exp_id)
    flow = ExpFlow.objects.get(id=flow_id)
    flow.delete()

    return redirect('experiment_detail', exp_id=exp_id)

def delete_step(request, exp_id, flow_id, step_id):

    step = ExpStep.objects.get(id=step_id)
    step.delete()

    return redirect('experiment_detail', exp_id=exp_id)

def add_experiment(request):
    projects = Project.objects.all().order_by('project_name')
    
    search_query = request.GET.get('search', '')
    latest_exp = Exp.objects.order_by('-created_on')
    
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
                    exp_description=exp_description
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
                    latest_exp = Exp.objects.order_by('-created_on')
                    
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
        latest_exp = Exp.objects.order_by('-created_on')
        
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

def add_step(request, exp_id, flow_id):
    
    experiment = Exp.objects.get(id=exp_id)
    flow = ExpFlow.objects.get(id=flow_id)
    
    if request.method == 'POST':
        form = ExpStepForm(request.POST, flow=flow)
        if form.is_valid():
            step = form.save(commit=False)
            step.flow = flow
            step.save()
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'redirect_url': f'/experiment/{exp_id}/?expanded_flow={flow_id}'
                })
            
            return redirect('experiment_detail', exp_id=exp_id)
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

@csrf_exempt
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

@csrf_exempt
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

