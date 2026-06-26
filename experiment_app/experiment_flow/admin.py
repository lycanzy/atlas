from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Exp, ExpFlow, ExpStep, Project, ResearchGroup, Sample, StepNameTemplate, UserProfile, Equipment

# Base admin class with custom CSS
class BaseModelAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

# Inline admin for UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Team Profile'
    fk_name = 'user'

# Extended User Admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_research_group')
    
    # Make first_name and last_name appear in the add/edit forms
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'email', 'password1', 'password2'),
        }),
    )
    
    def get_research_group(self, obj):
        return obj.profile.research_group if hasattr(obj, 'profile') and obj.profile.research_group else 'No Team'
    get_research_group.short_description = 'Team'

# Unregister the original User admin and register the new one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class TeamCodeInline(admin.TabularInline):
    model = Project
    extra = 0
    fields = ("project_code", "project_name", "created_on")
    readonly_fields = ("created_on",)
    verbose_name = "Team Code"
    verbose_name_plural = "Team Codes"

@admin.register(Exp)
class ExpAdmin(BaseModelAdmin):
    readonly_fields = ("created_on",)
    list_display = ("exp_name", "get_team_code", "exp_description", "owner", "created_on")
    search_fields = ("exp_name", "exp_description", "project__project_code", "project__project_name")
    list_filter = ("project__project_code", "owner")

    def get_team_code(self, obj):
        return obj.project.project_code if obj.project else "-"
    get_team_code.short_description = "Team"

@admin.register(ExpFlow)
class ExpFlowAdmin(BaseModelAdmin):
    list_display = ("full_flow", "flow_name", "exp", "flow_description", "created_on")
    search_fields = ("full_flow", "flow_name", "flow_description", "exp__exp_name")

@admin.register(ExpStep)
class ExpStepAdmin(BaseModelAdmin):
    list_display = ("step_name", "flow", "status", "started_on")

@admin.register(ResearchGroup)
class ResearchGroupAdmin(BaseModelAdmin):
    list_display = ("team", "team_codes", "created_on")
    search_fields = ("group_name", "project__project_code")
    inlines = (TeamCodeInline,)

    def team(self, obj):
        return obj.group_name
    team.short_description = "Team"
    team.admin_order_field = "group_name"

    def team_codes(self, obj):
        codes = obj.project.exclude(project_code__isnull=True).exclude(project_code="").values_list("project_code", flat=True)
        return ", ".join(codes) if codes else "-"
    team_codes.short_description = "Team Codes"

@admin.register(Sample)
class SampleAdmin(BaseModelAdmin):
    list_display = ("sample_name", "flow", "created_on")
    readonly_fields = ("created_on",)

@admin.register(StepNameTemplate)
class StepNameTemplateAdmin(BaseModelAdmin):
    list_display = ("step_code", "step_label", "category", "is_active", "created_on")
    list_filter = ("is_active", "category")
    search_fields = ("step_code", "step_label", "category")
    readonly_fields = ("created_on",)
    fieldsets = (
        ('Step Information', {
            'fields': ('step_code', 'step_label', 'category', 'is_active')
        }),
        ('Template Details', {
            'fields': ('default_description',)
        }),
        ('Metadata', {
            'fields': ('created_on',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Equipment)
class EquipmentAdmin(BaseModelAdmin):
    list_display = ("equipment_name", "equipment_id", "owner", "location", "is_active", "created_on")
    list_filter = ("is_active", "owner")
    search_fields = ("equipment_name", "equipment_id", "description", "location")
    readonly_fields = ("created_on", "updated_on")
    fieldsets = (
        ('Basic Information', {
            'fields': ('equipment_name', 'description', 'owner', 'location', 'is_active')
        }),
        ('Physical Specifications', {
            'fields': ('size',)
        }),
        ('Power Requirements', {
            'fields': ('power_requirement', 'voltage', 'current')
        }),
        ('Utility Requirements', {
            'fields': ('water_requirement', 'gas_input', 'exhaust_requirement')
        }),
        ('Metadata', {
            'fields': ('created_on', 'updated_on'),
            'classes': ('collapse',)
        }),
    )
