from django.db import models
from django.core.exceptions import ValidationError
import re

# Create your models here.

class ResearchGroup(models.Model):

    group_name = models.CharField(max_length = 25)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.group_name
    

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
        return f"{self.project_name} ({self.project_code})"

class Exp(models.Model):

    exp_name = models.CharField(max_length = 30)
    exp_description = models.TextField(blank = True, null = True)
    created_on = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, on_delete = models.CASCADE, related_name = 'experiment', null = True)

    def __str__(self):
        return self.exp_name
    
class ExpFlow(models.Model):

    flow_name = models.CharField(max_length = 2)
    flow_description = models.TextField(blank = True, null = True)
    exp = models.ForeignKey(Exp, on_delete = models.CASCADE, related_name = 'flow', null = True)
    created_on = models.DateTimeField(auto_now_add=True, null = True)

    def clean(self):
        if self.flow_name:
            # Check if the input contains exactly 2 alphabetic characters
            if not (len(self.flow_name) == 2 and self.flow_name.isalpha()):
                raise ValidationError('Flow name must be exactly 2 letters.')
            # Convert to uppercase
            self.flow_name = self.flow_name.upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.flow_name
    
class ExpStep(models.Model):

    STATUS_CHOICES = [
        ("Planned", "Planned"),
        ("Canceled", "Canceled"),
        ("Completed", "Completed"),
    ]

    step_name = models.CharField(max_length = 20)
    step_description = models.TextField(blank = True, null = True)
    started_on = models.DateTimeField(auto_now_add=True, null = True)
    completed_on = models.DateTimeField(blank = True, null = True)
    tool = models.CharField(max_length = 20, blank = True, null = True)
    recipe = models.CharField(max_length = 20, blank = True, null = True)

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
        step_num = 0

        current = self.parent
        while current:
            step_num += 1
            current = self.parent()

        return step_num


    def __str__(self):
        return self.step_name