from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Document
import logging

logger = logging.getLogger(__name__)

@login_required
@require_POST
def void_document(request, document_id):
    document = get_object_or_404(Document, pk=document_id)
    
    if not document.can_void(request.user):
        messages.error(request, "You do not have permission to void this document.")
        return redirect('document_approval:document_detail', reference_id=document.document_reference)
        
    reason = request.POST.get('void_reason')
    if not reason:
        messages.error(request, "Void reason is required.")
        return redirect('document_approval:document_detail', reference_id=document.document_reference)
        
    try:
        document.void(request.user, reason)
        messages.success(request, "Document has been voided successfully.")
    except Exception as e:
        logger.error(f"Error voiding document {document_id}: {str(e)}")
        messages.error(request, "An error occurred while voiding the document.")
        
    return redirect('document_approval:document_detail', reference_id=document.document_reference)
