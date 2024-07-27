from django.contrib import admin
from .models import ApprovalWorkflow, ApprovalStep, Document, Approval, DynamicFieldValue,  DynamicField

class DynamicFieldValueInline(admin.TabularInline):
    model = DynamicFieldValue
    extra = 1
    readonly_fields = ('field',)

@admin.register(DynamicField)
class DynamicFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'workflow', 'field_type', 'required', 'order')
    list_filter = ('workflow', 'field_type', 'required')
    search_fields = ('name', 'workflow__name')

class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 1

@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    inlines = [ApprovalStepInline]
    # list_display = ('name', 'created_by', 'created_at')
    # search_fields = ('name', 'created_by__username')

@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'name', 'order', 'is_conditional')
    list_filter = ('workflow', 'is_conditional')
    filter_horizontal = ('approvers',)
    fieldsets = (
        (None, {
            'fields': ('workflow', 'name', 'order', 'approvers')
        }),
        ('Conditional Logic', {
            'fields': ('is_conditional', 'condition_field', 'condition_operator', 'condition_value'),
            'classes': ('collapse',),
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "condition_field":
            if 'workflow' in request.GET:
                workflow_id = request.GET['workflow']
                kwargs["queryset"] = DynamicField.objects.filter(workflow_id=workflow_id)
            else:
                kwargs["queryset"] = DynamicField.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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