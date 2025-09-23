from django.contrib import admin
from .models import Exp, ExpFlow, ExpStep, Project, ResearchGroup
# Register your models here.

@admin.register(Exp)
class ExpAdmin(admin.ModelAdmin):
    readonly_fields = ("created_on",)  # make it visible but not editable
    list_display = ("exp_name", "created_on")  # optional: show in list view
admin.site.register(ExpFlow)
admin.site.register(ExpStep)
admin.site.register(Project)
admin.site.register(ResearchGroup)
