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
        
    def __init__(self, *args, flow=None, **kwargs):
        super().__init__(*args, **kwargs)
        if flow:
            # Only show potential parents from the same flow
            self.fields['parent'].queryset = ExpStep.objects.filter(flow=flow).exclude(id=self.instance.id if self.instance else None)
            
    def clean_step_name(self):
        step_name = self.cleaned_data['step_name'].upper()
        if not (len(step_name) == 2 and step_name.isalpha()):
            raise forms.ValidationError('Step name must be exactly 2 letters.')
        return step_name