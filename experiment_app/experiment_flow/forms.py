from django import forms
from .models import ExpStep, ExpFlow, StepNameTemplate, Equipment, RawMaterial
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
import re

class ExpFlowForm(forms.ModelForm):
    class Meta:
        model = ExpFlow
        fields = ['flow_name']

class ExpStepForm(forms.ModelForm):
    # Override step_name to use a dropdown
    step_name = forms.ChoiceField(
        label='步骤名称',
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_step_name'
        }),
        help_text='选择预设的步骤名称'
    )
    
    # Override parent to use a searchable select for all steps across experiments
    parent = forms.ModelChoiceField(
        label='前置步骤',
        queryset=ExpStep.objects.none(),  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select searchable-select',
            'id': 'id_parent',
            'data-placeholder': '搜索前置步骤...'
        }),
        help_text='可搜索并选择任意实验中的历史步骤'
    )
    
    # Override tool to use equipment dropdown
    tool = forms.ModelChoiceField(
        label='设备',
        queryset=Equipment.objects.none(),  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select searchable-select',
            'id': 'id_tool',
            'data-placeholder': '搜索设备...'
        }),
        help_text='从设备数据库中选择设备'
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
        self.fields['status'].choices = [
            ('Planned', '计划中'),
            ('Completed', '已完成'),
            ('Canceled', '已取消'),
        ]
        
        # Populate step_name choices from StepNameTemplate
        active_templates = StepNameTemplate.objects.filter(is_active=True).order_by('category', 'step_code')
        
        choices = [('', '--- 请选择步骤名称 ---')]
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
        self.fields['parent'].empty_label = "无前置步骤（顶层步骤）"
        
        # Populate equipment choices
        self.fields['tool'].queryset = Equipment.objects.filter(is_active=True).order_by('equipment_name')
        self.fields['tool'].empty_label = "未选择设备"
        
        # Auto-populate description from template if available
        self.step_templates = {t.step_code: t for t in active_templates}
            
    def clean_step_name(self):
        step_name = self.cleaned_data['step_name'].upper()
        if not (len(step_name) == 2 and step_name.isalpha()):
            raise forms.ValidationError('步骤名称必须是 2 个英文字母。')
        return step_name
    
    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        # Additional validation: prevent setting self as parent (in case queryset filtering fails)
        if parent and self.instance and parent.id == self.instance.id:
            raise forms.ValidationError('步骤不能将自己设为前置步骤。')
        if parent and self.instance and self.instance.pk:
            seen_ids = {self.instance.pk}
            current = parent
            while current:
                if current.pk in seen_ids:
                    raise forms.ValidationError('前置步骤不能形成循环谱系。')
                seen_ids.add(current.pk)
                current = current.parent
        return parent
class EquipmentForm(forms.ModelForm):
    # Override owner to use a searchable select
    owner = forms.ModelChoiceField(
        label='负责人',
        queryset=User.objects.none(),  # Will be set in __init__
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select searchable-select',
            'id': 'id_owner',
            'data-placeholder': '搜索负责人...'
        }),
        help_text='选择设备负责人'
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

class RawMaterialForm(forms.ModelForm):
    owner = forms.ModelChoiceField(
        label='负责人',
        queryset=User.objects.none(),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select searchable-select',
            'id': 'id_owner',
            'data-placeholder': '搜索负责人...'
        }),
        help_text='选择原材料负责人'
    )

    class Meta:
        model = RawMaterial
        fields = [
            'material_code', 'received_date', 'material_type', 'material_name',
            'description', 'owner', 'supplier', 'location', 'is_active', 'notes'
        ]
        widgets = {
            'material_code': forms.TextInput(attrs={'class': 'form-control'}),
            'received_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'material_type': forms.TextInput(attrs={'class': 'form-control'}),
            'material_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'supplier': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['owner'].queryset = User.objects.all().order_by('first_name', 'last_name', 'username')
        self.fields['owner'].label_from_instance = lambda obj: obj.get_full_name() if obj.get_full_name() else obj.username
        self.fields['received_date'].required = True
        self.fields['received_date'].input_formats = ['%Y-%m-%d']
        self.fields['material_name'].required = False


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    Custom password change form with styled widgets
    """
    old_password = forms.CharField(
        label="当前密码",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入当前密码'
        })
    )
    new_password1 = forms.CharField(
        label="新密码",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入新密码'
        })
    )
    new_password2 = forms.CharField(
        label="确认新密码",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请再次输入新密码'
        })
    )
