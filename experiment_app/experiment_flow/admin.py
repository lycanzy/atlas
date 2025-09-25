from django.contrib import admin
from .models import Exp, ExpFlow, ExpStep, Project, ResearchGroup

# Base admin class with custom CSS
class BaseModelAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

@admin.register(Exp)
class ExpAdmin(BaseModelAdmin):
    readonly_fields = ("created_on",)
    list_display = ("exp_name", "created_on")

@admin.register(ExpFlow)
class ExpFlowAdmin(BaseModelAdmin):
    list_display = ("flow_name", "exp", "created_on")

@admin.register(ExpStep)
class ExpStepAdmin(BaseModelAdmin):
    list_display = ("step_name", "flow", "status", "started_on")

@admin.register(Project)
class ProjectAdmin(BaseModelAdmin):
    list_display = ("project_name", "project_code", "created_on")

@admin.register(ResearchGroup)
class ResearchGroupAdmin(BaseModelAdmin):
    list_display = ("group_name", "created_on")
