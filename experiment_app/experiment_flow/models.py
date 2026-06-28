from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import re

# Create your models here.

class ResearchGroup(models.Model):

    group_name = models.CharField(max_length = 25)
    team_code = models.CharField(max_length=3, unique=True, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"

    def clean(self):
        if self.team_code:
            if not (len(self.team_code) == 3 and self.team_code.isalpha()):
                raise ValidationError('团队代码必须是 3 个英文字母。')
            self.team_code = self.team_code.upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.group_name and self.team_code:
            return f"{self.group_name} ({self.team_code})"
        return str(self.group_name) if self.group_name else "未命名研究组"

class UserProfile(models.Model):
    """Extended user profile linked to research group"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    research_group = models.ForeignKey(ResearchGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.research_group.group_name if self.research_group else '无研究组'}"

class Project(models.Model):
    
    project_name = models.CharField(max_length = 50)
    project_code = models.CharField(max_length = 3, null = True, blank = True)
    group = models.ForeignKey(ResearchGroup, on_delete = models.CASCADE, related_name = 'project', null = True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Team Code"
        verbose_name_plural = "Team Codes"

    def generate_experiment_name(self):
        # Business naming: team code (e.g. PCA) + sequence => project code (e.g. PCA001).
        exp_count = self.experiment.count()
        number = str(exp_count + 1).zfill(3)
        team_code = self.group.team_code if self.group and self.group.team_code else self.project_code
        return f"{team_code}{number}"

    def clean(self):
        if self.project_code:
            # Ensure project code is exactly 3 uppercase letters
            if not (len(self.project_code) == 3 and self.project_code.isalpha()):
                raise ValidationError('项目代码必须是 3 个英文字母。')
            self.project_code = self.project_code.upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.project_name:
            if self.project_code:
                return f"{self.project_name} ({self.project_code})"
            return str(self.project_name)
        return "未命名项目"

class Exp(models.Model):

    exp_name = models.CharField(max_length = 30)
    exp_description = models.TextField(blank = True, null = True)
    created_on = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, on_delete = models.CASCADE, related_name = 'experiment', null = True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experiments')

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self):
        return str(self.exp_name) if self.exp_name else "未命名实验"
    
class ExpFlow(models.Model):

    flow_name = models.CharField(max_length = 2)
    flow_description = models.TextField(blank = True, null = True)
    exp = models.ForeignKey(Exp, on_delete = models.CASCADE, related_name = 'flow', null = True)
    created_on = models.DateTimeField(auto_now_add=True, null = True)
    full_flow = models.CharField(max_length=35, editable=False, db_index=True, null = True)  # Adding index for faster queries

    class Meta:
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"

    def clean(self):
        if self.flow_name:
            # Check if the input contains exactly 2 alphabetic characters
            if not (len(self.flow_name) == 2 and self.flow_name.isalpha()):
                raise ValidationError('流程代码必须是 2 个英文字母。')
            # Convert to uppercase
            self.flow_name = self.flow_name.upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        # Business naming: project code (e.g. PCA001) + experiment suffix (e.g. AA).
        if self.exp:
            self.full_flow = f"{self.exp.exp_name}{self.flow_name}"
        else:
            self.full_flow = self.flow_name
        super().save(*args, **kwargs)

    def __str__(self):
        if self.full_flow:
            return str(self.full_flow)
        if self.flow_name:
            return str(self.flow_name)
        return "未命名流程"
    
    @property
    def flow(self):
        """Returns the full flow identifier combining experiment name and flow name"""
        if self.exp:
            return f"{self.exp.exp_name}{self.flow_name}"
        return self.flow_name
    
class ExpStep(models.Model):

    STATUS_CHOICES = [
        ("Planned", "Planned"),
        ("Canceled", "Canceled"),
        ("Completed", "Completed"),
    ]

    step_name = models.CharField(max_length=2)  # Base name like 'AA'
    step_number = models.CharField(max_length=2, editable=False, null=True, blank=True)  # Sequential number like '00', '01'
    full_step = models.CharField(max_length=50, editable=False, db_index=True, null=True)  # Full identifier like 'AAA001AA-AA00'
    step_description = models.TextField(blank=True, null=True)
    started_on = models.DateTimeField(auto_now_add=True, null=True)
    completed_on = models.DateTimeField(blank=True, null=True)
    tool = models.ForeignKey('Equipment', on_delete=models.SET_NULL, blank=True, null=True, related_name='steps', help_text="Equipment/tool used for this step")
    recipe = models.CharField(max_length=20, blank=True, null=True)

    @property
    def full_step_name(self):
        """Returns the complete step name (e.g., 'AA00')"""
        return f"{self.step_name}{self.step_number}"

    notes = models.TextField(blank = True, null = True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="Planned"
    )

    flow = models.ForeignKey(ExpFlow, on_delete = models.CASCADE, related_name = 'step', null = True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, related_name='child', null=True, blank=True)

    def clean(self):
        super().clean()
        if not self.parent:
            return
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({'parent': '步骤不能将自己设为前置步骤。'})

        seen_ids = {self.pk} if self.pk else set()
        current = self.parent
        while current:
            if current.pk in seen_ids:
                raise ValidationError({'parent': '前置步骤不能形成循环谱系。'})
            seen_ids.add(current.pk)
            current = current.parent

    @property
    def step_num(self):
        """Count the number of previous steps within the current flow only"""
        step_num = 0
        current = self.parent
        while current:
            # Only count if the parent is in the same flow
            if current.flow == self.flow:
                step_num += 1
            current = current.parent   # ✅ move up to the next parent
        return f"{step_num:02d}"


    def save(self, *args, **kwargs):
        if not self.step_number:  # Only set number if it's not already set
            # Get the highest number for this step name in this flow
            existing_steps = ExpStep.objects.filter(
                flow=self.flow,
                step_name=self.step_name
            ).exclude(pk=self.pk)  # Exclude self if updating
            
            if existing_steps.exists():
                # Get all step numbers and find the highest
                numbers = [int(step.step_number) for step in existing_steps if step.step_number.isdigit()]
                next_number = max(numbers) + 1 if numbers else 0
            else:
                next_number = 0
            
            # Format as two digits
            self.step_number = f"{next_number:02d}"
        
        # Update full_step
        if self.flow and self.flow.exp and self.step_number:
            self.full_step = f"{self.flow.full_flow}-{self.full_step_name}"
        elif self.step_number:
            self.full_step = self.full_step_name

        # Clean step name
        self.step_name = self.step_name.upper()
        if len(self.step_name) != 2 or not self.step_name.isalpha():
            raise ValidationError('步骤名称必须是 2 个英文字母（例如 AA）。')

        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if hasattr(self, 'full_step') and self.full_step:
            return str(self.full_step)
        if self.step_name:
            return f"{self.step_name}{self.step_number or '00'}"
        return "未命名步骤"

class StepNameTemplate(models.Model):
    """Predefined step name templates that can be selected when adding/editing steps"""
    
    step_code = models.CharField(max_length=2, unique=True, help_text="Two-letter code (e.g., AA, BB, CV)")
    step_label = models.CharField(max_length=100, help_text="Descriptive name (e.g., Cleaning, Deposition)")
    category = models.CharField(max_length=50, blank=True, null=True, help_text="Category for grouping (e.g., Preparation, Lithography)")
    default_description = models.TextField(blank=True, null=True, help_text="Default description template for this step")
    is_active = models.BooleanField(default=True, help_text="Whether this step template is available for selection")
    created_on = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['category', 'step_code']
        verbose_name = "Step Name Template"
        verbose_name_plural = "Step Name Templates"
    
    def clean(self):
        if self.step_code:
            # Ensure step code is exactly 2 uppercase letters
            if not (len(self.step_code) == 2 and self.step_code.isalpha()):
                raise ValidationError('步骤代码必须是 2 个英文字母。')
            self.step_code = self.step_code.upper()
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.step_code} - {self.step_label}" if self.step_label else self.step_code

class Sample(models.Model):

    sample_name = models.CharField(max_length = 50)
    created_on = models.DateTimeField(auto_now_add=True)
    flow = models.ForeignKey(ExpStep, on_delete = models.CASCADE, related_name = 'sample', null = True)

    def __str__(self):
        return str(self.sample_name) if self.sample_name else "未命名样品"

class Equipment(models.Model):
    """Equipment/Tool database for tracking lab equipment"""
    
    equipment_id = models.CharField(max_length=30, unique=True, blank=True, null=True, help_text="Unique equipment ID or serial number")
    equipment_name = models.CharField(max_length=100, unique=True, help_text="Name of the equipment")
    description = models.TextField(blank=True, null=True, help_text="Detailed description of the equipment")
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='equipment', help_text="Equipment owner/responsible person")
    location = models.CharField(max_length=200, blank=True, null=True, help_text="Current location (e.g., Lab 101, Room A)")
    
    # Physical specifications
    size = models.CharField(max_length=100, blank=True, null=True, help_text="Physical dimensions (e.g., 60cm x 80cm x 120cm)")
    
    # Power requirements
    power_requirement = models.CharField(max_length=100, blank=True, null=True, help_text="Power requirement (e.g., 5kW, 3-phase)")
    voltage = models.CharField(max_length=50, blank=True, null=True, help_text="Voltage requirement (e.g., 220V, 380V)")
    current = models.CharField(max_length=50, blank=True, null=True, help_text="Current requirement (e.g., 15A, 20A)")
    
    # Utilities
    water_requirement = models.CharField(max_length=200, blank=True, null=True, help_text="Water requirement (e.g., DI water, 5L/min)")
    gas_input = models.CharField(max_length=200, blank=True, null=True, help_text="Gas input requirements (e.g., N2, Ar, 2 SLM)")
    exhaust_requirement = models.CharField(max_length=200, blank=True, null=True, help_text="Exhaust requirements (e.g., Acid exhaust, 500 CFM)")
    
    # Metadata
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Whether the equipment is currently active/available")
    
    class Meta:
        ordering = ['equipment_name']
        verbose_name = "Equipment"
        verbose_name_plural = "Equipment"
    
    def __str__(self):
        return self.equipment_name

class RawMaterial(models.Model):
    """Raw material database for tracking material batches used in steps"""

    material_code = models.CharField(max_length=50, help_text="Raw material code")
    batch_number = models.CharField(max_length=80, blank=True, help_text="Raw material batch number generated from material code and received date")
    received_date = models.DateField(blank=True, null=True, help_text="Date this raw material batch was received")
    material_type = models.CharField(max_length=100, blank=True, null=True, help_text="Raw material type/category")
    material_name = models.CharField(max_length=100, blank=True, null=True, help_text="Raw material name")
    description = models.TextField(blank=True, null=True, help_text="Detailed description of the raw material")
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='raw_materials', help_text="Raw material owner/responsible person")
    supplier = models.CharField(max_length=200, blank=True, null=True, help_text="Supplier/vendor")
    location = models.CharField(max_length=200, blank=True, null=True, help_text="Storage location")
    notes = models.TextField(blank=True, null=True, help_text="Additional notes")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Whether the raw material is currently active/available")

    class Meta:
        ordering = ['material_code', 'batch_number']
        verbose_name = "Raw Material"
        verbose_name_plural = "Raw Materials"
        constraints = [
            models.UniqueConstraint(fields=['material_code', 'batch_number'], name='unique_raw_material_code_batch')
        ]

    def clean(self):
        if self.material_code:
            self.material_code = self.material_code.strip().upper()
        if self.material_code and self.received_date:
            self.batch_number = f"{self.material_code}-{self.received_date.strftime('%m%d%y')}"
        elif self.batch_number:
            self.batch_number = self.batch_number.strip().upper()
        if not self.material_name:
            self.material_name = None

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def display_label(self):
        type_label = f" ({self.material_type})" if self.material_type else ""
        name_label = f" - {self.material_name}" if self.material_name else ""
        return f"{self.material_code} - {self.batch_number}{name_label}{type_label}"

    def __str__(self):
        return self.display_label

class StepRawMaterialUsage(models.Model):
    """Raw material usage record for a specific experiment step"""

    step = models.ForeignKey(ExpStep, on_delete=models.CASCADE, related_name='raw_material_usages')
    raw_material = models.ForeignKey(RawMaterial, on_delete=models.PROTECT, related_name='step_usages')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['raw_material__material_code', 'raw_material__batch_number']
        verbose_name = "Step Raw Material Usage"
        verbose_name_plural = "Step Raw Material Usages"
        constraints = [
            models.UniqueConstraint(fields=['step', 'raw_material'], name='unique_step_raw_material_usage')
        ]

    def __str__(self):
        amount = f" - {self.quantity:g} {self.unit or ''}".strip() if self.quantity is not None else ""
        return f"{self.step} uses {self.raw_material}{amount}"

# Signal to update all flow identifiers when experiment changes
@receiver(post_save, sender=Exp)
def update_flow_identifiers(sender, instance, **kwargs):
    # Update all related flows
    for flow in instance.flow.all():
        flow.full_flow = f"{instance.exp_name}{flow.flow_name}"
        flow.save()
        # Update all steps in this flow
        for step in flow.step.all():
            step.full_step = f"{flow.full_flow}-{step.full_step_name}"
            step.save(update_fields=['full_step'])

# Signal to update ExpStep.full_step when flow changes
@receiver(post_save, sender=ExpFlow)
def update_step_identifiers(sender, instance, **kwargs):
    # Update all related steps
    for step in instance.step.all():
        step.full_step = f"{instance.full_flow}-{step.full_step_name}"
        step.save(update_fields=['full_step'])
