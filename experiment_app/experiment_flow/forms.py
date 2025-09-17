from django import forms
from .models import ExpStep, ExpFlow
import re

class ExpFlowForm(forms.ModelForm):
    class Meta:
        model = ExpFlow
        fields = ['flow_name']

class ExpStepForm(forms.ModelForm):
    class Meta:
        model = ExpStep
        fields = ['step_name', 'parent', 'step_description', 'status', 'completed_on', 'tool', 'recipe', 'notes']