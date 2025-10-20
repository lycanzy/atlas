from django import forms
from .models import ExpStep, ExpFlow, StepNameTemplate
import re

class ExpFlowForm(forms.ModelForm):
    class Meta:
        model = ExpFlow
        fields = ['flow_name']

class ExpStepForm(forms.ModelForm):
    # Override step_name to use a dropdown
    step_name = forms.ChoiceField(
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_step_name'
        }),
        help_text='Select a predefined step name'
    )
    
    class Meta:
        model = ExpStep
        fields = ['step_name', 'parent', 'step_description', 'status', 'completed_on', 'tool', 'recipe', 'notes']
        widgets = {
            'parent': forms.Select(attrs={
                'class': 'form-select'
            }),
            'step_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter a detailed description of this step...',
                'id': 'id_step_description'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'completed_on': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'tool': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Stepper, Etcher'
            }),
            'recipe': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Recipe001'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add any additional notes, observations, or comments...'
            }),
        }
        
    def __init__(self, *args, flow=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate step_name choices from StepNameTemplate
        active_templates = StepNameTemplate.objects.filter(is_active=True).order_by('category', 'step_code')
        
        choices = [('', '--- Select a step name ---')]
        current_category = None
        
        for template in active_templates:
            if template.category and template.category != current_category:
                # Add a separator/optgroup for category
                if current_category is not None:
                    choices.append(('', '---'))
                current_category = template.category
            
            # Create the choice as (code, "CODE - Label")
            display_text = f"{template.step_code} - {template.step_label}" if template.step_label else template.step_code
            choices.append((template.step_code, display_text))
        
        self.fields['step_name'].choices = choices
        
        # Set initial value if editing existing step
        if self.instance and self.instance.pk:
            self.fields['step_name'].initial = self.instance.step_name
        
        if flow:
            # Only show potential parents from the same flow
            self.fields['parent'].queryset = ExpStep.objects.filter(flow=flow).exclude(id=self.instance.id if self.instance else None)
        
        # Make parent field have a blank option
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = "No parent (top-level step)"
        
        # Auto-populate description from template if available
        self.step_templates = {t.step_code: t for t in active_templates}
            
    def clean_step_name(self):
        step_name = self.cleaned_data['step_name'].upper()
        if not (len(step_name) == 2 and step_name.isalpha()):
            raise forms.ValidationError('Step name must be exactly 2 letters.')
        return step_name