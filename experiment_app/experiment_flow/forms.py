from django import forms
from .models import ExpStep, ExpFlow, StepNameTemplate, Equipment
from django.contrib.auth.models import User
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
    
    # Override parent to use a searchable select for all steps across experiments
    parent = forms.ModelChoiceField(
        queryset=ExpStep.objects.none(),  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select searchable-select',
            'id': 'id_parent',
            'data-placeholder': 'Search for a previous step...'
        }),
        help_text='Search and select any step from any experiment'
    )
    
    # Override tool to use equipment dropdown
    tool = forms.ModelChoiceField(
        queryset=Equipment.objects.none(),  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select searchable-select',
            'id': 'id_tool',
            'data-placeholder': 'Search for equipment...'
        }),
        help_text='Select equipment from database'
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
                'class': 'form-control'
            }),
            'recipe': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
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
        
        # Allow parent to be any step from any experiment, except itself
        if self.instance and self.instance.pk:
            # Exclude the step itself when editing
            self.fields['parent'].queryset = ExpStep.objects.all().exclude(id=self.instance.id).select_related(
                'flow__exp'
            ).order_by('flow__exp__exp_name', 'flow__flow_name', 'step_name', 'step_number')
        else:
            # When adding a new step, show all existing steps
            self.fields['parent'].queryset = ExpStep.objects.all().select_related(
                'flow__exp'
            ).order_by('flow__exp__exp_name', 'flow__flow_name', 'step_name', 'step_number')
        
        # Make parent field have a blank option
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = "No parent (top-level step)"
        
        # Populate equipment choices
        self.fields['tool'].queryset = Equipment.objects.filter(is_active=True).order_by('equipment_name')
        self.fields['tool'].empty_label = "No equipment selected"
        
        # Auto-populate description from template if available
        self.step_templates = {t.step_code: t for t in active_templates}
            
    def clean_step_name(self):
        step_name = self.cleaned_data['step_name'].upper()
        if not (len(step_name) == 2 and step_name.isalpha()):
            raise forms.ValidationError('Step name must be exactly 2 letters.')
        return step_name
class EquipmentForm(forms.ModelForm):
    # Override owner to use a searchable select
    owner = forms.ModelChoiceField(
        queryset=User.objects.none(),  # Will be set in __init__
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select searchable-select',
            'id': 'id_owner',
            'data-placeholder': 'Search for owner...'
        }),
        help_text='Select the equipment owner'
    )
    
    class Meta:
        model = Equipment
        fields = [
            'equipment_name', 'equipment_id', 'description', 'owner', 'location',
            'size', 'power_requirement', 'voltage', 'current',
            'water_requirement', 'gas_input', 'exhaust_requirement', 'is_active'
        ]
        widgets = {
            'equipment_name': forms.TextInput(attrs={'class': 'form-control'}),
            'equipment_id': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_equipment_id'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'size': forms.TextInput(attrs={'class': 'form-control'}),
            'power_requirement': forms.TextInput(attrs={'class': 'form-control'}),
            'voltage': forms.TextInput(attrs={'class': 'form-control'}),
            'current': forms.TextInput(attrs={'class': 'form-control'}),
            'water_requirement': forms.TextInput(attrs={'class': 'form-control'}),
            'gas_input': forms.TextInput(attrs={'class': 'form-control'}),
            'exhaust_requirement': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate owner choices with all users, ordered by first name then last name
        self.fields['owner'].queryset = User.objects.all().order_by('first_name', 'last_name', 'username')
        self.fields['owner'].label_from_instance = lambda obj: obj.get_full_name() if obj.get_full_name() else obj.username
