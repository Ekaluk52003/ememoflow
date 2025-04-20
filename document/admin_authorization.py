from django.contrib import admin
from .models_authorization import ApprovalAuthorization


@admin.register(ApprovalAuthorization)
class ApprovalAuthorizationAdmin(admin.ModelAdmin):
    list_display = ('authorizer', 'authorized_user', 'valid_from', 'valid_until', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('authorizer__username', 'authorizer__email', 'authorized_user__username', 'authorized_user__email', 'reason')
    date_hierarchy = 'valid_from'
    ordering = ('-valid_from',)
    
    fieldsets = (
        ('Authorization Details', {
            'fields': ('authorizer', 'authorized_user', 'reason')
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_until', 'is_active')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        # Make authorizer and authorized_user read-only when editing an existing record
        if obj:
            return ('authorizer', 'authorized_user')
        return ()
