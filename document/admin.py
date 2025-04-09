from django.contrib import admin
from .models import ApprovalWorkflow, ApprovalStep, Document, Approval, DynamicFieldValue, DynamicField, PDFTemplate, ReportConfiguration, ReferenceID
from django.core.exceptions import ValidationError
from .notification_models import Notification

@admin.register(PDFTemplate)
class PDFTemplateAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(ReportConfiguration)
class ReportConfigurationAdmin(admin.ModelAdmin):
    list_display = ('company_name',)

class DynamicFieldValueInline(admin.TabularInline):
    model = DynamicFieldValue
    extra = 1
    readonly_fields = ('field',)

class DynamicFieldInline(admin.TabularInline):
    model = DynamicField
    extra = 1

@admin.register(DynamicField)
class DynamicFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'workflow', 'field_type', 'required', 'order')
    list_filter = ('workflow', 'field_type', 'required')
    search_fields = ('name', 'workflow__name')

class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 1
    filter_horizontal = ('editable_fields', 'approvers')

@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    inlines = [DynamicFieldInline, ApprovalStepInline]
    list_display = ('name', 'created_by', 'created_at')
    search_fields = ('name', 'created_by__username')

@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'name', 'order', 'approval_mode', 'is_conditional', 'requires_edit', 'move_to_next')
    list_filter = ('workflow', 'approval_mode', 'is_conditional', 'requires_edit')
    filter_horizontal = ('approvers', 'editable_fields')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "editable_fields":
            workflow_id = None
            if request.resolver_match.kwargs.get('object_id'):
                approval_step = ApprovalStep.objects.get(pk=request.resolver_match.kwargs['object_id'])
                workflow_id = approval_step.workflow_id
            elif 'workflow' in request.GET:
                workflow_id = request.GET['workflow']

            if workflow_id:
                kwargs["queryset"] = DynamicField.objects.filter(workflow_id=workflow_id)
                print(f"Debug: Filtered queryset for workflow {workflow_id}. Count: {kwargs['queryset'].count()}")
            else:
                kwargs["queryset"] = DynamicField.objects.none()
                print("Debug: No workflow_id found, returning empty queryset")

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj:
            print(f"Debug: Editing existing ApprovalStep. Workflow: {obj.workflow}, Editable fields: {obj.editable_fields.all()}")
        else:
            print("Debug: Creating new ApprovalStep")
        return form

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            print(f"Debug: ValidationError occurred: {str(e)}")
            raise

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'submitted_by', 'workflow', 'current_step', 'status', 'created_at', 'updated_at', 'last_submitted_at')
    list_filter = ('status', 'workflow', 'current_step')
    search_fields = ('title', 'submitted_by__username', 'content')
    date_hierarchy = 'created_at'
    inlines = [DynamicFieldValueInline]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return ('submitted_by', 'created_at')
        return ()

@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ('document', 'step', 'approver', 'is_approved', 'created_at', 'updated_at')
    list_filter = ('is_approved', 'step', 'approver')
    search_fields = ('document__title', 'approver__username', 'comment')
    date_hierarchy = 'created_at'
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return ('document', 'step', 'approver', 'created_at')
        return ()

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'workflow_name', 'timestamp', 'is_read')
    list_filter = ('user', 'workflow_name', 'timestamp', 'is_read')
    search_fields = ('message', 'workflow_name', 'user__username')
    ordering = ('-timestamp',)
    readonly_fields = ('user', 'message', 'document', 'workflow_name', 'url', 'timestamp')

@admin.register(ReferenceID)
class ReferenceIDAdmin(admin.ModelAdmin):
    list_display = ('formatted_reference', 'year', 'last_number')
    readonly_fields = ('formatted_reference',)

    def formatted_reference(self, obj):
        return f"{str(obj.year % 100).zfill(2)}{str(obj.last_number).zfill(5)}"
    formatted_reference.short_description = 'Reference'

    def has_add_permission(self, request):
        # Prevent manual creation of new references
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of references
        return False