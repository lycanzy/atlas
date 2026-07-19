from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Cell, Project, Experiment, ExperimentStep, ExperimentStepLink, ProjectCategory, ResearchGroup, Sample, StepNameTemplate, UserProfile, Equipment, RawMaterial, StepRawMaterialUsage

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


@admin.register(Project)
class ProjectAdmin(BaseModelAdmin):
    readonly_fields = ("created_on",)
    list_display = ("exp_name", "get_team_code", "exp_description", "owner", "created_on")
    search_fields = ("exp_name", "exp_description", "project__project_code", "project__project_name")
    list_filter = ("project__project_code", "owner")

    def get_team_code(self, obj):
        if obj.project and obj.project.group and obj.project.group.team_code:
            return obj.project.group.team_code
        return obj.project.project_code if obj.project else "-"
    get_team_code.short_description = "Team"

@admin.register(Experiment)
class ExperimentAdmin(BaseModelAdmin):
    list_display = ("full_experiment_code", "experiment_code", "project", "experiment_description", "created_on")
    search_fields = ("full_experiment_code", "experiment_code", "experiment_description", "project__exp_name")

@admin.register(ExperimentStep)
class ExperimentStepAdmin(BaseModelAdmin):
    list_display = ("step_name", "experiment", "status", "started_on")


@admin.register(ExperimentStepLink)
class ExperimentStepLinkAdmin(BaseModelAdmin):
    list_display = ("parent_step", "child_step", "created_on")
    search_fields = ("parent_step__full_step", "child_step__full_step")
    readonly_fields = ("created_on",)

@admin.register(ResearchGroup)
class ResearchGroupAdmin(BaseModelAdmin):
    list_display = ("team", "team_code", "created_on")
    search_fields = ("group_name", "team_code")
    readonly_fields = ("created_on",)
    fields = ("group_name", "team_code", "created_on")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "team_code":
            formfield.required = True
            formfield.help_text = "3 uppercase letters, for example PCA."
        return formfield

    def team(self, obj):
        return obj.group_name
    team.short_description = "Team"
    team.admin_order_field = "group_name"

@admin.register(Sample)
class SampleAdmin(BaseModelAdmin):
    list_display = ("sample_name", "sample_number", "step", "created_on")
    search_fields = ("sample_name", "step__full_step")
    readonly_fields = ("sample_number", "created_on")


@admin.register(Cell)
class CellAdmin(BaseModelAdmin):
    list_display = ("barcode", "package_number", "step", "created_on", "updated_on")
    search_fields = ("barcode", "package_number", "step__full_step")
    readonly_fields = ("created_on", "updated_on")

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

@admin.register(RawMaterial)
class RawMaterialAdmin(BaseModelAdmin):
    list_display = ("material_code", "batch_number", "received_date", "material_name", "material_type", "owner", "location", "is_active", "created_on")
    list_filter = ("is_active", "material_type", "owner")
    search_fields = ("material_code", "batch_number", "material_name", "material_type", "description", "supplier", "location")
    readonly_fields = ("batch_number", "created_on", "updated_on")
    fieldsets = (
        ('Basic Information', {
            'fields': ('material_code', 'received_date', 'batch_number', 'material_type', 'material_name', 'description', 'owner', 'is_active')
        }),
        ('Storage and Supplier', {
            'fields': ('supplier', 'location')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_on', 'updated_on'),
            'classes': ('collapse',)
        }),
    )

@admin.register(StepRawMaterialUsage)
class StepRawMaterialUsageAdmin(BaseModelAdmin):
    list_display = ("step", "raw_material", "quantity", "unit", "updated_on")
    search_fields = ("step__full_step", "raw_material__material_code", "raw_material__batch_number", "raw_material__material_name")
    list_filter = ("raw_material__material_type",)
