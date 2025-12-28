from django.urls import path, include
from . import views
from . import views_void
from django.conf import settings
from . import views_authorization
from . import views_workflow
from . import views_dynamic_fields
from .views_statistics import approval_statistics

app_name = 'document_approval'  # This sets the application namespace

urlpatterns = [

    path('', views.document_list, name='document_list'),
    path('<int:reference_id>/', views.document_detail, name='document_detail'),
    path('submit/<int:workflow_id>/', views.submit_document, name='submit_document'),
    path('<int:pk>/resubmit/', views.resubmit_document, name='resubmit_document'),
    path('to-approve/', views.documents_to_approve_to_resubmit, name='documents_to_approve'),
    path('<int:document_id>/withdraw/', views.withdraw_document, name='withdraw_document'),
    path('<int:document_id>/cancel/', views.cancel_document, name='cancel_document'),
    path('<int:document_id>/void/', views_void.void_document, name='void_document'),
    path('generate-pdf-report/<int:reference_id>/<int:template_id>/', views.generate_pdf_report, name='generate_pdf_report'),
    path('delete-attachment/<int:field_id>/<int:document_id>', views.delete_attachment, name='delete_attachment'),
    path('document/<int:document_id>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('favorite-documents/', views.favorite_documents, name='favorite_documents'),
    path('clear-toast/', views.clear_toast, name='clear_toasts'),
    path('view-file/<int:field_value_id>/', views.view_file, name='view_file'),
    path('view-editor-image/<int:image_id>/', views.view_editor_image, name='view_editor_image'),
    path('notifications/load/', views.load_notifications, name='load_notifications'),
    path('notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/clear-all/', views.clear_all_notifications, name='clear_all_notifications'),
    path('notifications/<int:notification_id>/delete/', views.delete_notification, name='delete_notification'),
    # Workflow management
    path('workflows/', views_workflow.workflow_list, name='workflow_list'),
    path('workflows/create/', views_workflow.create_workflow, name='create_workflow'),
    path('workflows/<int:workflow_id>/edit/', views_workflow.edit_workflow, name='edit_workflow'),
    path('workflows/<int:workflow_id>/delete/', views_workflow.delete_workflow, name='delete_workflow'),
    path('workflow/<int:workflow_id>/steps/', views_workflow.workflow_steps, name='workflow_steps'),
    path('workflow/<int:workflow_id>/steps/create/', views_workflow.create_workflow_step, name='create_workflow_step'),
    path('workflow/steps/<int:step_id>/edit/', views_workflow.edit_workflow_step, name='edit_workflow_step'),
    path('workflow/steps/<int:step_id>/delete/', views_workflow.delete_workflow_step, name='delete_workflow_step'),
    path('workflow/<int:workflow_id>/steps/reorder/', views_workflow.reorder_workflow_steps, name='reorder_workflow_steps'),
    # Dynamic field management
    path('fields/', views_dynamic_fields.field_list, name='field_list'),
    path('fields/create/', views_dynamic_fields.create_field, name='create_field'),
    path('fields/<int:field_id>/edit/', views_dynamic_fields.edit_field, name='edit_field'),
    path('fields/<int:field_id>/delete/', views_dynamic_fields.delete_field, name='delete_field'),
    path('fields/<int:field_id>/preview/', views_dynamic_fields.field_preview, name='field_preview'),
    path('fields/preview/', views_dynamic_fields.field_preview, name='field_preview_ajax'),
    path('fields/<int:field_id>/edit-ajax/', views_dynamic_fields.edit_field_ajax, name='edit_field_ajax'),
    path('fields/<int:field_id>/delete-ajax/', views_dynamic_fields.delete_field_ajax, name='delete_field_ajax'),
    # Authorization URLs
   


    path('authorizations/', views_authorization.authorization_list, name='authorization_list'),
    path('authorizations/create/', views_authorization.create_authorization, name='create_authorization'),
    # Alternative direct authorization path
    path('authorizations/direct-create/', views_authorization.direct_create_authorization, name='direct_create_authorization'),
    path('authorizations/<int:pk>/delete/', views_authorization.delete_authorization, name='delete_authorization'),
    path('authorizations/<int:pk>/toggle/', views_authorization.toggle_authorization, name='toggle_authorization'),
    
    # API endpoints
    path('api/users/', views_authorization.api_users, name='api_users'),
    path('search-users/', views.search_users, name='search_users'),
    path('api/user/<int:user_id>/', views.get_user_details, name='get_user_details'),
    path('api/document/<int:document_id>/authorized-users/', views.get_document_authorized_users, name='get_document_authorized_users'),
    
    # Statistics
    path('statistics/', approval_statistics, name='approval_statistics'),

    path('user-group-diagram/', views.user_group_diagram, name='user_group_diagram'),

]
