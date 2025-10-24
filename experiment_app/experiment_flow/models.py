from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import re

# Create your models here.

class ResearchGroup(models.Model):

    group_name = models.CharField(max_length = 25)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.group_name) if self.group_name else "Unnamed Group"

class UserProfile(models.Model):
    """Extended user profile linked to research group"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    research_group = models.ForeignKey(ResearchGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.research_group.group_name if self.research_group else 'No Group'}"

class Project(models.Model):
    
    project_name = models.CharField(max_length = 50)
    project_code = models.CharField(max_length = 3, null = True, blank = True)
    group = models.ForeignKey(ResearchGroup, on_delete = models.CASCADE, related_name = 'project', null = True)
    created_on = models.DateTimeField(auto_now_add=True)

    def generate_experiment_name(self):
        # Count existing experiments for this project
        exp_count = self.experiment.count()
        # Generate the 3-digit number
        number = str(exp_count + 1).zfill(3)
        # Combine project code with number
        return f"{self.project_code}{number}"

    def clean(self):
        if self.project_code:
            # Ensure project code is exactly 3 uppercase letters
            if not (len(self.project_code) == 3 and self.project_code.isalpha()):
                raise ValidationError('Project code must be exactly 3 letters.')
            self.project_code = self.project_code.upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.project_name:
            if self.project_code:
                return f"{self.project_name} ({self.project_code})"
            return str(self.project_name)
        return "Unnamed Project"

class Exp(models.Model):

    exp_name = models.CharField(max_length = 30)
    exp_description = models.TextField(blank = True, null = True)
    created_on = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, on_delete = models.CASCADE, related_name = 'experiment', null = True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experiments')

    def __str__(self):
        return str(self.exp_name) if self.exp_name else "Unnamed Experiment"
    
class ExpFlow(models.Model):

    flow_name = models.CharField(max_length = 2)
    flow_description = models.TextField(blank = True, null = True)
    exp = models.ForeignKey(Exp, on_delete = models.CASCADE, related_name = 'flow', null = True)
    created_on = models.DateTimeField(auto_now_add=True, null = True)
    full_flow = models.CharField(max_length=35, editable=False, db_index=True, null = True)  # Adding index for faster queries

    def clean(self):
        if self.flow_name:
            # Check if the input contains exactly 2 alphabetic characters
            if not (len(self.flow_name) == 2 and self.flow_name.isalpha()):
                raise ValidationError('Flow name must be exactly 2 letters.')
            # Convert to uppercase
            self.flow_name = self.flow_name.upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        # Update full_flow before saving
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
        return "Unnamed Flow"
    
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
    components = models.JSONField(default=list, blank=True, help_text="List of components/materials used in this step")

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
            raise ValidationError('Step name must be exactly 2 letters (e.g., AA)')

        super().save(*args, **kwargs)

    def __str__(self):
        if hasattr(self, 'full_step') and self.full_step:
            return str(self.full_step)
        if self.step_name:
            return f"{self.step_name}{self.step_number or '00'}"
        return "Unnamed Step"

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
                raise ValidationError('Step code must be exactly 2 letters.')
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
        return str(self.sample_name) if self.sample_name else "Unnamed Sample"

class Equipment(models.Model):
    """Equipment/Tool database for tracking lab equipment"""
    
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

# Signal to update ExpFlow.full_flow when Exp name changes
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