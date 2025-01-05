from django.urls import path,include
from . import views
from django.conf import settings


app_name = 'document_approval'  # This sets the application namespace

urlpatterns = [

    path('', views.document_list, name='document_list'),
    path('workflows/', views.workflow_list, name='workflow_list'),
    path('<int:reference_id>/', views.document_detail, name='document_detail'),
    path('submit/<int:workflow_id>/', views.submit_document, name='submit_document'),
    path('<int:pk>/resubmit/', views.resubmit_document, name='resubmit_document'),
    path('to-approve/', views.documents_to_approve_to_resubmit, name='documents_to_approve'),
    path('<int:document_id>/withdraw/', views.withdraw_document, name='withdraw_document'),
    path('<int:document_id>/cancel/', views.cancel_document, name='cancel_document'),
    path('generate-pdf-report/<int:reference_id>/<int:template_id>/', views.generate_pdf_report, name='generate_pdf_report'),
    path('delete-attachment/<int:field_id>/<int:document_id>', views.delete_attachment, name='delete_attachment'),
    path('document/<int:document_id>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('favorite-documents/', views.favorite_documents, name='favorite_documents'),
    path('clear-toast/', views.clear_toast, name='clear_toasts'),

]

