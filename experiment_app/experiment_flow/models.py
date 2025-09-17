from django.db import models
from django.core.exceptions import ValidationError
import re

# Create your models here.

class Exp(models.Model):

    exp_name = models.CharField(max_length = 30)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.exp_name
    
class ExpFlow(models.Model):

    flow_name = models.CharField(max_length = 2)
    flow_description = models.TextField(blank = True, null = True)
    exp = models.ForeignKey(Exp, on_delete = models.CASCADE, related_name = 'flow', null = True)

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