from django.db import models

# Create your models here.

class Exp(models.Model):

    exp_name = models.CharField(max_length = 30)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.exp_name
    
class ExpFlow(models.Model):

    flow_name = models.CharField(max_length = 20)
    flow_description = models.TextField(blank = True, null = True)
    exp = models.ForeignKey(Exp, on_delete = models.CASCADE, related_name = 'flow', null = True)

    def __str__(self):
        return self.flow_name
    
class ExpStep(models.Model):

    step_name = models.CharField(max_length = 20)
    flow = models.ForeignKey(ExpFlow, on_delete = models.CASCADE, related_name = 'step', null = True)

    def __str__(self):
        return self.step_name