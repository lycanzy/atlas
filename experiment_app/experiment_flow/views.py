from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Exp, ExpFlow, ExpStep
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
# Create your views here.

def index(request):

    latest_exp = Exp.objects.order_by('-created_on')

    return render(request, 'experiment_flow/index.html', {'experiments': latest_exp})

def experiment_detail(request, exp_id):
    
    experiment = Exp.objects.get(id=exp_id)
    
    return render(request, 'experiment_flow/experiment_detail.html', {'experiment': experiment}) 

def delete_flow(request, exp_id, flow_id):

    experiment = Exp.objects.get(id=exp_id)
    flow = ExpFlow.objects.get(id=flow_id)
    flow.delete()

    return redirect('experiment_detail', exp_id=exp_id)

def add_experiment(request):
    if request.method == 'POST':
        exp_name = request.POST.get('exp_name')
        if exp_name:
            new_exp = Exp(exp_name=exp_name)
            new_exp.save()
            return redirect('index')  # Redirect to the index page after adding
    return render(request, 'experiment_flow/add_experiment.html')

def add_flow(request, exp_id):
    
    if request.method == 'POST':
        flow_name = request.POST.get('flow_name')
        if flow_name:
            exp = Exp.objects.get(id=exp_id)
            new_flow = ExpFlow(flow_name=flow_name, exp=exp)
            new_flow.save()
            return redirect('experiment_detail', exp_id=exp_id)
        
    experiment = Exp.objects.get(id=exp_id)

    return render(request, 'experiment_flow/add_flow.html', {'experiment': experiment})

def add_step(request, exp_id, flow_id):
    
    if request.method == 'POST':
        step_name = request.POST.get('step_name')
        if step_name:
            flow = ExpFlow.objects.get(id=flow_id)
            new_step = ExpStep(step_name=step_name, flow=flow)
            new_step.save()
            return redirect('experiment_detail', exp_id=exp_id)
        
    experiment = Exp.objects.get(id=exp_id)
    flow = ExpFlow.objects.get(id=flow_id)

    return render(request, 'experiment_flow/add_step.html', {'experiment': experiment, 'flow': flow})


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

