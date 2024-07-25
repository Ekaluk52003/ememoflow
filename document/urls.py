from django.urls import path
from . import views

app_name = 'document_approval'  # This sets the application namespace

urlpatterns = [

    path('', views.document_list, name='document_list'),
    path('<int:pk>/', views.document_detail, name='document_detail'),
    path('submit/', views.submit_document, name='submit_document'),
    path('<int:pk>/resubmit/', views.resubmit_document, name='resubmit_document'),
    path('to-approve/', views.documents_to_approve_to_resubmit, name='documents_to_approve'),
]