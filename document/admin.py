from django.contrib import admin
from .models import ApprovalWorkflow, ApprovalStep, Document, Approval

@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at')
    search_fields = ('name', 'created_by__username')

@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'name', 'order')
    list_filter = ('workflow',)
    search_fields = ('name', 'workflow__name')
    ordering = ('workflow', 'order')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'submitted_by', 'workflow', 'current_step', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'workflow', 'current_step')
    search_fields = ('title', 'submitted_by__username', 'content')
    date_hierarchy = 'created_at'

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