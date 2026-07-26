from django import forms
from .models import (
    ExperimentStep, Experiment, Project, ProjectCategory, ResearchGroup, StepNameTemplate,
    Equipment, RawMaterial, RawMaterialType, UserProfile, step_link_would_create_cycle,
)
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Q
import re


class TeamManagementForm(forms.ModelForm):
    class Meta:
        model = ResearchGroup
        fields = ['group_name', 'team_code']
        labels = {'group_name': 'Team 名称', 'team_code': 'Team 代码'}
        widgets = {
            'group_name': forms.TextInput(attrs={'class': 'form-control'}),
            'team_code': forms.TextInput(attrs={
                'class': 'form-control', 'maxlength': 3,
                'placeholder': '例如 PCA',
            }),
        }


class ProjectManagementForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['exp_description', 'owner']
        labels = {'exp_description': '项目描述', 'owner': '负责人'}
        widgets = {
            'exp_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'owner': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        team = getattr(getattr(self.instance, 'project', None), 'group', None)
        member_ids = UserProfile.objects.filter(research_group=team).values_list('user_id', flat=True)
        self.fields['owner'].queryset = User.objects.filter(
            Q(id__in=member_ids) | Q(is_staff=True) | Q(is_superuser=True)
        ).distinct().order_by('username')


class ProjectCreateForm(forms.Form):
    team = forms.ModelChoiceField(
        label='Team', queryset=ResearchGroup.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    exp_description = forms.CharField(
        label='项目描述', required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )
    owner = forms.ModelChoiceField(
        label='负责人', queryset=User.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['team'].queryset = ResearchGroup.objects.exclude(
            team_code__isnull=True
        ).exclude(team_code='').order_by('group_name')
        self.fields['owner'].queryset = User.objects.filter(is_active=True).order_by('username')

    def clean(self):
        cleaned = super().clean()
        team, owner = cleaned.get('team'), cleaned.get('owner')
        if team and owner and not (owner.is_staff or owner.is_superuser):
            if getattr(getattr(owner, 'profile', None), 'research_group_id', None) != team.id:
                self.add_error('owner', '负责人必须属于所选 Team。')
        return cleaned


class ManagedUserForm(forms.ModelForm):
    research_group = forms.ModelChoiceField(
        label='所属 Team', queryset=ResearchGroup.objects.none(), required=False,
        empty_label='未分配', widget=forms.Select(attrs={'class': 'form-select'}),
    )
    password = forms.CharField(
        label='密码', required=False, min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='新增成员时必填；编辑时留空表示不修改。',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff']
        labels = {
            'username': '用户名', 'first_name': '名', 'last_name': '姓',
            'email': '邮箱', 'is_active': '启用', 'is_staff': '管理权限',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['research_group'].queryset = ResearchGroup.objects.order_by('group_name')
        if self.instance.pk:
            self.fields['research_group'].initial = getattr(
                getattr(self.instance, 'profile', None), 'research_group', None
            )

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.instance.pk and not password:
            raise forms.ValidationError('新增成员时必须设置密码。')
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.research_group = self.cleaned_data.get('research_group')
            profile.save(update_fields=['research_group'])
        return user


class StepTemplateManagementForm(forms.ModelForm):
    class Meta:
        model = StepNameTemplate
        fields = ['step_code', 'step_label', 'category', 'default_description', 'is_active']
        labels = {
            'step_code': '步骤代码', 'step_label': '步骤名称', 'category': '分类',
            'default_description': '默认描述', 'is_active': '启用',
        }
        widgets = {
            'step_code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 2}),
            'step_label': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'default_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RawMaterialTypeManagementForm(forms.ModelForm):
    class Meta:
        model = RawMaterialType
        fields = ['name', 'description', 'is_active']
        labels = {
            'name': '种类名称', 'description': '说明', 'is_active': '启用',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MemberTeamForm(forms.Form):
    research_group = forms.ModelChoiceField(
        label='所属 Team', queryset=ResearchGroup.objects.none(), required=False,
        empty_label='未分配', widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['research_group'].queryset = ResearchGroup.objects.order_by('group_name')

class ExperimentForm(forms.ModelForm):
    class Meta:
        model = Experiment
        fields = ['experiment_code']

class ExperimentStepForm(forms.ModelForm):
    sample_count = forms.IntegerField(
        label='样品数量',
        required=False,
        min_value=0,
        max_value=200,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 0,
            'max': 200,
            'step': 1,
        }),
        help_text='保存后自动生成 0–200 个样品编号',
    )

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
    
    # Override parents to use a searchable multi-select for all steps across experiments
    parents = forms.ModelMultipleChoiceField(
        label='前置步骤',
        queryset=ExperimentStep.objects.none(),  # Will be set in __init__
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select searchable-select lineage-parent-select',
            'id': 'id_parents',
            'data-placeholder': '搜索并选择一个或多个前置步骤...'
        }),
        help_text='可搜索并选择任意实验中的一个或多个历史步骤'
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
        model = ExperimentStep
        fields = ['step_name', 'parents', 'step_description', 'status', 'completed_on', 'tool', 'recipe', 'notes']
        widgets = {
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
        
    def __init__(self, *args, experiment=None, **kwargs):
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
            self.fields['sample_count'].initial = self.instance.samples.filter(
                sample_number__isnull=False
            ).count()
        
        # Allow upstream parents to be any step from any experiment, except itself
        if self.instance and self.instance.pk:
            # Exclude the step itself when editing
            self.fields['parents'].queryset = ExperimentStep.objects.all().exclude(id=self.instance.id).select_related(
                'experiment__project'
            ).order_by('experiment__project__exp_name', 'experiment__experiment_code', 'step_name', 'step_number')
            self.fields['parents'].initial = self.instance.parents.all()
        else:
            # When adding a new step, show all existing steps
            self.fields['parents'].queryset = ExperimentStep.objects.all().select_related(
                'experiment__project'
            ).order_by('experiment__project__exp_name', 'experiment__experiment_code', 'step_name', 'step_number')
        
        # Populate equipment choices by equipment number so Select2 searches by the visible identifier.
        self.fields['tool'].queryset = Equipment.objects.filter(is_active=True).order_by('equipment_id', 'equipment_name')
        self.fields['tool'].label_from_instance = lambda obj: obj.equipment_id or obj.equipment_name
        self.fields['tool'].empty_label = "未选择设备"
        
        # Auto-populate description from template if available
        self.step_templates = {t.step_code: t for t in active_templates}
            
    def clean_step_name(self):
        step_name = self.cleaned_data['step_name'].upper()
        if not (len(step_name) == 2 and step_name.isalpha()):
            raise forms.ValidationError('步骤名称必须是 2 个英文字母。')
        return step_name
    
    def clean_parents(self):
        parents = self.cleaned_data.get('parents')
        if not parents:
            return parents

        if self.instance and self.instance.pk:
            child_id = self.instance.pk
            existing_parent_ids = set(self.instance.parents.values_list('id', flat=True))
            selected_parent_ids = {parent.id for parent in parents}

            for parent in parents:
                if parent.id == child_id:
                    raise forms.ValidationError('步骤不能将自己设为前置步骤。')
                if parent.id not in existing_parent_ids and step_link_would_create_cycle(parent.id, child_id):
                    raise forms.ValidationError('前置步骤不能形成循环谱系。')

            removed_parent_ids = existing_parent_ids - selected_parent_ids
            added_parent_ids = selected_parent_ids - existing_parent_ids
            if removed_parent_ids and added_parent_ids:
                for parent_id in added_parent_ids:
                    if step_link_would_create_cycle(parent_id, child_id):
                        raise forms.ValidationError('前置步骤不能形成循环谱系。')
        return parents

    def clean_sample_count(self):
        sample_count = self.cleaned_data.get('sample_count')
        sample_count = 0 if sample_count is None else sample_count
        if self.instance and self.instance.pk:
            current_count = self.instance.samples.filter(sample_number__isnull=False).count()
            if sample_count < current_count:
                raise forms.ValidationError(
                    f'为保留实验追溯记录，样品数量不能低于当前的 {current_count}。'
                )
        return sample_count
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
    material_type = forms.ChoiceField(
        label='原材料种类',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

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
        type_names = list(
            RawMaterialType.objects.filter(is_active=True)
            .order_by('name')
            .values_list('name', flat=True)
        )
        current_type = self.instance.material_type if self.instance and self.instance.pk else None
        if current_type and current_type not in type_names:
            type_names.append(current_type)
        self.fields['material_type'].choices = [
            ('', '--- 请选择原材料种类 ---'),
            *((name, name) for name in type_names),
        ]


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
