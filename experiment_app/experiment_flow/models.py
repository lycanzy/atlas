from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
import re
from decimal import Decimal

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


class AuditLog(models.Model):
    """Immutable application audit event shown in the management center."""

    ACTION_CHOICES = [
        ('create', '新增'),
        ('update', '修改'),
        ('delete', '删除'),
        ('copy', '复制'),
        ('status', '状态变化'),
        ('login', '登录'),
        ('login_failed', '登录失败'),
        ('logout', '退出'),
        ('password_change', '修改密码'),
        ('permission_denied', '权限拒绝'),
    ]
    CATEGORY_CHOICES = [
        ('auth', '认证'),
        ('project', 'Project'),
        ('experiment', 'Experiment'),
        ('step', 'Step'),
        ('equipment', '设备'),
        ('raw_material', '原材料'),
        ('member', '成员'),
        ('management', '系统管理'),
    ]
    OUTCOME_CHOICES = [
        ('success', '成功'),
        ('failed', '失败'),
        ('denied', '拒绝'),
    ]

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events',
    )
    actor_username = models.CharField(max_length=150, blank=True, db_index=True)
    actor_team = models.CharField(max_length=100, blank=True, db_index=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='management', db_index=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES, default='success', db_index=True)
    entity_type = models.CharField(max_length=50, db_index=True)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=200)
    summary = models.CharField(max_length=500)
    changes = models.JSONField(default=dict, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_on', '-id']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        actor = self.actor_username or (self.actor.username if self.actor else '匿名用户')
        return f"{actor} {self.get_action_display()} {self.entity_type} {self.object_repr}"

class ProjectCategory(models.Model):
    """Project category/program metadata used to group generated project records."""
    
    project_name = models.CharField(max_length = 50)
    project_code = models.CharField(max_length = 3, null = True, blank = True)
    group = models.ForeignKey(ResearchGroup, on_delete = models.CASCADE, related_name = 'project', null = True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "experiment_flow_project"
        verbose_name = "Project Category"
        verbose_name_plural = "Project Categories"

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

class Project(models.Model):
    """Generated project record, such as AFE001."""

    exp_name = models.CharField(max_length = 30)
    exp_description = models.TextField(blank = True, null = True)
    created_on = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(ProjectCategory, on_delete = models.CASCADE, related_name = 'experiment', null = True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experiments')

    class Meta:
        db_table = "experiment_flow_exp"
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self):
        return str(self.exp_name) if self.exp_name else "未命名项目"
    
class Experiment(models.Model):
    """Experiment under a project, such as AFE001AA."""

    experiment_code = models.CharField(max_length = 2)
    experiment_description = models.TextField(blank = True, null = True)
    project = models.ForeignKey(Project, on_delete = models.CASCADE, related_name = 'experiments', null = True)
    created_on = models.DateTimeField(auto_now_add=True, null = True)
    full_experiment_code = models.CharField(max_length=35, editable=False, db_index=True, null = True)  # Adding index for faster queries

    class Meta:
        db_table = "experiment_flow_expflow"
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"

    def clean(self):
        if self.experiment_code:
            # Check if the input contains exactly 2 alphabetic characters
            if not (len(self.experiment_code) == 2 and self.experiment_code.isalpha()):
                raise ValidationError('实验代码必须是 2 个英文字母。')
            # Convert to uppercase
            self.experiment_code = self.experiment_code.upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        # Business naming: project code (e.g. PCA001) + experiment suffix (e.g. AA).
        if self.project:
            self.full_experiment_code = f"{self.project.exp_name}{self.experiment_code}"
        else:
            self.full_experiment_code = self.experiment_code
        super().save(*args, **kwargs)

    def __str__(self):
        if self.full_experiment_code:
            return str(self.full_experiment_code)
        if self.experiment_code:
            return str(self.experiment_code)
        return "未命名实验"

class ExperimentStep(models.Model):
    """Process step inside an experiment, such as AFE001AA-MX00."""

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

    experiment = models.ForeignKey(Experiment, on_delete = models.CASCADE, related_name = 'steps', null = True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, related_name='child', null=True, blank=True)
    parents = models.ManyToManyField(
        'self',
        through='ExperimentStepLink',
        through_fields=('child_step', 'parent_step'),
        symmetrical=False,
        related_name='children',
        blank=True,
    )

    class Meta:
        db_table = "experiment_flow_expstep"
        verbose_name = "Experiment Step"
        verbose_name_plural = "Experiment Steps"

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
        """Count the number of previous steps within the current experiment only"""
        def chain_length(step, seen_ids=None):
            seen_ids = seen_ids or set()
            if not step or step.id in seen_ids:
                return 0
            seen_ids.add(step.id)

            parents = list(step.parents.all()) if step.pk else []
            if not parents and step.parent:
                parents = [step.parent]

            lengths = []
            for parent in parents:
                if parent.experiment == self.experiment:
                    lengths.append(1 + chain_length(parent, seen_ids.copy()))
            return max(lengths, default=0)

        return f"{chain_length(self):02d}"


    def save(self, *args, **kwargs):
        if self.status == "Completed" and not self.completed_on:
            self.completed_on = timezone.now()
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"completed_on"}

        if not self.step_number:  # Only set number if it's not already set
            # Get the highest number for this step name in this experiment
            existing_steps = ExperimentStep.objects.filter(
                experiment=self.experiment,
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
        if self.experiment and self.experiment.project and self.step_number:
            self.full_step = f"{self.experiment.full_experiment_code}-{self.full_step_name}"
        elif self.step_number:
            self.full_step = self.full_step_name

        # Clean step name
        self.step_name = self.step_name.upper()
        if len(self.step_name) != 2 or not self.step_name.isalpha():
            raise ValidationError('步骤名称必须是 2 个英文字母（例如 AA）。')

        self.clean()
        super().save(*args, **kwargs)

        if self.parent_id and not self.parents.filter(id=self.parent_id).exists():
            ExperimentStepLink.objects.get_or_create(
                parent_step_id=self.parent_id,
                child_step_id=self.id,
            )

    def __str__(self):
        if hasattr(self, 'full_step') and self.full_step:
            return str(self.full_step)
        if self.step_name:
            return f"{self.step_name}{self.step_number or '00'}"
        return "未命名步骤"


class ExperimentStepLink(models.Model):
    """Directed genealogy edge from an upstream step to a downstream step."""

    parent_step = models.ForeignKey(
        ExperimentStep,
        on_delete=models.CASCADE,
        related_name='outgoing_links',
    )
    child_step = models.ForeignKey(
        ExperimentStep,
        on_delete=models.CASCADE,
        related_name='incoming_links',
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "experiment_flow_expsteplink"
        verbose_name = "Experiment Step Link"
        verbose_name_plural = "Experiment Step Links"
        constraints = [
            models.UniqueConstraint(
                fields=['parent_step', 'child_step'],
                name='unique_experiment_step_link',
            )
        ]

    def clean(self):
        super().clean()
        if self.parent_step_id and self.parent_step_id == self.child_step_id:
            raise ValidationError('步骤不能将自己设为前置步骤。')
        if self.parent_step_id and self.child_step_id and step_link_would_create_cycle(
            self.parent_step_id,
            self.child_step_id,
            exclude_link_id=self.pk,
        ):
            raise ValidationError('前置步骤不能形成循环谱系。')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent_step} -> {self.child_step}"


def step_link_would_create_cycle(parent_step_id, child_step_id, exclude_link_id=None):
    """Return True when adding parent -> child would create a directed cycle."""
    if parent_step_id == child_step_id:
        return True

    links = ExperimentStepLink.objects.all()
    if exclude_link_id:
        links = links.exclude(id=exclude_link_id)

    adjacency = {}
    for source_id, target_id in links.values_list('parent_step_id', 'child_step_id'):
        adjacency.setdefault(source_id, set()).add(target_id)

    stack = list(adjacency.get(child_step_id, set()))
    seen = set()
    while stack:
        current_id = stack.pop()
        if current_id == parent_step_id:
            return True
        if current_id in seen:
            continue
        seen.add(current_id)
        stack.extend(adjacency.get(current_id, set()))
    return False


@receiver(m2m_changed, sender=ExperimentStep.parents.through)
def validate_experiment_step_parent_links(sender, instance, action, reverse, pk_set, **kwargs):
    if action == 'pre_add' and pk_set:
        for related_step_id in pk_set:
            parent_step_id = instance.id if reverse else related_step_id
            child_step_id = related_step_id if reverse else instance.id
            if step_link_would_create_cycle(parent_step_id, child_step_id):
                raise ValidationError('前置步骤不能形成循环谱系。')
        return

    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return

    affected_steps = []
    if reverse:
        affected_steps = list(ExperimentStep.objects.filter(id__in=pk_set or []))
    else:
        affected_steps = [instance]

    for step in affected_steps:
        first_parent = step.parents.order_by(
            'experiment__project__exp_name',
            'experiment__experiment_code',
            'step_name',
            'step_number',
        ).first()
        ExperimentStep.objects.filter(id=step.id).update(
            parent_id=first_parent.id if first_parent else None
        )

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
    MAX_SAMPLES_PER_STEP = 200

    sample_name = models.CharField(max_length=54, db_index=True)
    sample_number = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    created_on = models.DateTimeField(auto_now_add=True)
    step = models.ForeignKey(ExperimentStep, on_delete=models.CASCADE, related_name='samples', null=True)

    class Meta:
        ordering = ['sample_number', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['step', 'sample_number'],
                name='unique_sample_number_per_step',
            ),
            models.CheckConstraint(
                condition=models.Q(sample_number__isnull=True) | (
                    models.Q(sample_number__gte=1) & models.Q(sample_number__lte=200)
                ),
                name='sample_number_between_1_and_200',
            ),
        ]

    @classmethod
    def sync_for_step(cls, step, target_count):
        """Create missing numbered samples up to target_count without deleting history."""
        if not 0 <= target_count <= cls.MAX_SAMPLES_PER_STEP:
            raise ValidationError({'sample_count': '样品数量必须在 0 到 200 之间。'})

        existing_samples = {
            sample.sample_number: sample
            for sample in cls.objects.filter(
                step=step,
                sample_number__isnull=False,
            )
        }
        samples_to_create = []
        samples_to_rename = []
        for sample_number in range(1, target_count + 1):
            sample_name = f"{step.full_step}-{sample_number:02d}"
            sample = existing_samples.get(sample_number)
            if sample is None:
                samples_to_create.append(cls(
                    step=step,
                    sample_number=sample_number,
                    sample_name=sample_name,
                ))
            elif sample.sample_name != sample_name:
                sample.sample_name = sample_name
                samples_to_rename.append(sample)

        if samples_to_create:
            cls.objects.bulk_create(samples_to_create)
        if samples_to_rename:
            cls.objects.bulk_update(samples_to_rename, ['sample_name'])

        return cls.objects.filter(step=step, sample_number__isnull=False).count()

    def __str__(self):
        return str(self.sample_name) if self.sample_name else "未命名样品"


class CellTestItem(models.Model):
    """Administrator-managed test option assignable to battery cells."""

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']

    def clean(self):
        super().clean()
        self.name = (self.name or '').strip()
        if not self.name:
            raise ValidationError({'name': '测试项目名称不能为空。'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Cell(models.Model):
    """A physical battery cell assigned to exactly one experiment step."""

    step = models.ForeignKey(
        ExperimentStep,
        on_delete=models.CASCADE,
        related_name='cells',
    )
    package_number = models.CharField(max_length=100, db_index=True)
    barcode = models.CharField(max_length=100, unique=True)
    test_item = models.ForeignKey(
        CellTestItem,
        on_delete=models.PROTECT,
        related_name='cells',
        null=True,
        blank=True,
    )
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['package_number', 'barcode', 'id']

    def clean(self):
        super().clean()
        self.package_number = (self.package_number or '').strip().upper()
        self.barcode = (self.barcode or '').strip().upper()
        errors = {}
        if not self.package_number:
            errors['package_number'] = 'Package 号不能为空。'
        if not self.barcode:
            errors['barcode'] = 'Barcode 不能为空。'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.barcode

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


class RawMaterialType(models.Model):
    """Managed choices used by the raw material type dropdown."""

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Raw Material Type"
        verbose_name_plural = "Raw Material Types"

    def clean(self):
        if self.name:
            self.name = self.name.strip()
        if not self.name:
            raise ValidationError({'name': '原材料种类名称不能为空。'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RawMaterial(models.Model):
    """Raw material database for tracking material batches used in steps"""

    material_code = models.CharField(max_length=50, help_text="Raw material code")
    batch_number = models.CharField(max_length=80, blank=True, help_text="Raw material batch number generated from material code and received date")
    received_date = models.DateField(blank=True, null=True, help_text="Date this raw material batch was received")
    material_type = models.CharField(max_length=100, blank=True, null=True, help_text="Raw material type/category")
    material_name = models.CharField(max_length=100, blank=True, null=True, help_text="Raw material name")
    description = models.TextField(blank=True, null=True, help_text="Detailed description of the raw material")
    total_quantity = models.DecimalField(max_digits=14, decimal_places=4, blank=True, null=True, validators=[MinValueValidator(Decimal('0'))], help_text="Total quantity received")
    total_unit = models.CharField(max_length=50, blank=True, null=True, help_text="Unit for the total quantity")
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

    step = models.ForeignKey(ExperimentStep, on_delete=models.CASCADE, related_name='raw_material_usages')
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

# Signal to update all experiment identifiers when project code changes
@receiver(post_save, sender=Project)
def update_experiment_identifiers(sender, instance, **kwargs):
    for experiment in instance.experiments.all():
        experiment.full_experiment_code = f"{instance.exp_name}{experiment.experiment_code}"
        experiment.save()
        for step in experiment.steps.all():
            step.full_step = f"{experiment.full_experiment_code}-{step.full_step_name}"
            step.save(update_fields=['full_step'])

# Signal to update ExperimentStep.full_step when experiment changes
@receiver(post_save, sender=Experiment)
def update_step_identifiers(sender, instance, **kwargs):
    for step in instance.steps.all():
        step.full_step = f"{instance.full_experiment_code}-{step.full_step_name}"
        step.save(update_fields=['full_step'])
