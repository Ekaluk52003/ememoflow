from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse, StreamingHttpResponse
from django.db.models import Q, Exists, OuterRef
from django.template.loader import render_to_string
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.db.models import Q
from .models import Document, EditorImage, ApprovalWorkflow, ApprovalStep, DynamicField, DynamicFieldValue, PDFTemplate, ReportConfiguration, Favorite
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import HttpResponse
from django.template import Context, Template
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from .forms import DocumentSubmissionForm
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Exists, OuterRef
from django.shortcuts import render
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django_htmx.http import retarget
import logging
from django.views.decorators.http import require_POST
from django.conf import settings
from pathlib import Path
import traceback
import redis
import json
from django.core.serializers.json import DjangoJSONEncoder
import os
from .utils import get_allowed_documents, get_allowed_document, get_user_bu_groups
from urllib.parse import urlparse
from urllib.request import urlopen
import time
import asyncio

logger = logging.getLogger(__name__)


@login_required
@require_POST
def toggle_favorite(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    favorite, created = Favorite.objects.get_or_create(user=request.user, document=document)

    if not created:
        favorite.delete()
        is_favorite = False
    else:
        is_favorite = True

    return render(request, 'partials/favorite_button.html', {
        'document': document,
        'is_favorite': is_favorite
    })


@login_required
def favorite_documents(request):
    favorite_docs = Document.objects.filter(favorites__user=request.user)
    favorite_docs_with_status = [(doc, True) for doc in favorite_docs]
    return render(request, 'document/favorite_documents.html', {
        'favorite_documents': favorite_docs_with_status
    })

@login_required
@require_http_methods(["DELETE"])
def delete_attachment(request, field_id, document_id):
    field_value = get_object_or_404(DynamicFieldValue, field_id=field_id, document__submitted_by=request.user,  document_id=document_id)

    if field_value.file:
        field_value.file.delete()  # Delete the actual file
        field_value.file = None
        field_value.save()

        return render(request, 'partials/delete_file.html', {'field': field_value  })
    else:
        return HttpResponse("No file to delete", status=400)  # Bad Request


def prepare_dynamic_fields(document):
    prepared_values = []

    for dynamic_value in document.dynamic_values.all().select_related('field'):
        prepared_value = {
            'name': dynamic_value.field.name,
            'field_type': dynamic_value.field.field_type,
            'value': dynamic_value.get_value()  # Using the get_value method
        }

        if dynamic_value.field.field_type == 'product_list':
            prepared_value['value'] = dynamic_value.json_value
        elif dynamic_value.field.field_type == 'table_list':
            prepared_value['value'] = dynamic_value.json_value
        elif dynamic_value.field.field_type == 'attachment':
            prepared_value['value'] = dynamic_value.file.url if dynamic_value.file else 'No file'

        prepared_values.append(prepared_value)

    return prepared_values


@login_required
def generate_pdf_report(request, reference_id, template_id):
    import boto3
    from urllib.parse import urlparse
    import weasyprint
    from django.urls import reverse
    import base64

    document_response = get_allowed_document(request.user, reference_id)
    if isinstance(document_response, HttpResponse):
        return document_response
    document = document_response
    template = get_object_or_404(PDFTemplate, id=template_id)
    report_config = ReportConfiguration.objects.first()
    
    # Create S3 client for generating signed URLs
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
    )

    def url_fetcher(url):
        """Custom URL fetcher to handle S3 URLs"""
        if url.startswith(('http://', 'https://')):
            parsed = urlparse(url)
            if parsed.path.startswith('/document/view-editor-image/'):
                url = parsed.path
            elif parsed.path.startswith('/document/view-file/'):
                url = parsed.path
            else:
                return weasyprint.default_url_fetcher(url)
        
        if url.startswith('/document/view-editor-image/'):
            try:
                image_id = int(url.split('/')[-2])
                editor_image = get_object_or_404(EditorImage, id=image_id)
                signed_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                        'Key': editor_image.image.name,
                    },
                    ExpiresIn=3600
                )
                return weasyprint.default_url_fetcher(signed_url)
            except Exception:
                return weasyprint.default_url_fetcher(url)
        
        if url.startswith('/document/view-file/'):
            try:
                field_value_id = int(url.split('/')[-2])
                dynamic_field_value = get_object_or_404(DynamicFieldValue, pk=field_value_id)
                if not dynamic_field_value.file:
                    return None
                signed_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                        'Key': dynamic_field_value.file.name,
                    },
                    ExpiresIn=3600
                )
                return weasyprint.default_url_fetcher(signed_url)
            except Exception:
                return None
        
        return weasyprint.default_url_fetcher(url)

    # Get the context data and render template
    context_data = document.get_report_context()
    context_data['report_config'] = report_config
    
    # Add logo data URI to context
    if report_config and report_config.company_logo:
        context_data['company_logo_data_uri'] = report_config.logo_data_uri
    
    # Get approvals ordered by most recent first
    approvals = document.approvals.all().order_by('-recorded_at', '-created_at')
    context_data['approvals'] = approvals
    
    # Get users who have approved
    approved_users = document.approvals.filter(
        is_approved=True
    ).select_related('approver')
    
    approver_names = [f"{approval.approver.first_name} {approval.approver.last_name}{' (' + approval.approver.job_title + ')' if approval.approver.job_title else ''}".strip() 
                     for approval in approved_users]
    context_data['approver_names'] = ", ".join(approver_names)
    
    # Prepare dynamic fields with file URLs
    prepared_values = []
    dynamic_values = DynamicFieldValue.objects.filter(document=document).select_related('field')
    
    for value in dynamic_values:
        prepared_value = {
            'name': value.field.name,
            'field_type': value.field.field_type,
            'value': value.value
        }
        
        if value.field.field_type == 'product_list':
            products = value.json_value if value.json_value else []
            prepared_value['value'] = products
            prepared_value['products'] = products
            prepared_value['total_quantity'] = sum(product['quantity'] for product in products)
        elif value.field.field_type == 'table_list':
            # Get the column order from the field
            columns = [col.strip() for col in value.field.table_columns.split('|') if col.strip()]
            
            # Prepare the rows with ordered columns
            ordered_rows = []
            for row in (value.json_value or []):
                # Create a new row with columns in the correct order
                ordered_row = []
                for col in columns:
                    ordered_row.append((col, row.get(col, '')))
                ordered_rows.append(ordered_row)
            
            prepared_value['value'] = ordered_rows
            prepared_value['columns'] = columns
            prepared_value['field'] = value.field  # Make sure field is available in template
        elif value.field.field_type == 'attachment' and value.file:
            file_url = reverse('document_approval:view_file', args=[value.id])
            full_filename = value.file.name.split('/')[-1]
            original_filename = '_'.join(full_filename.split('_')[:-1]) + os.path.splitext(full_filename)[1]
            file_ext = original_filename.split('.')[-1].lower()
            is_image = file_ext in ['jpg', 'jpeg', 'png', 'gif']
            
            prepared_value['file'] = {
                'name': original_filename,
                'url': file_url,
                'is_image': is_image
            }
        
        prepared_values.append(prepared_value)
    
    context_data['prepared_values'] = prepared_values

    html_template = Template(template.html_content)
    context = Context(context_data)
    html_content = html_template.render(context)

    # Generate PDF with embedded fonts
    font_config = FontConfiguration()
    font_regular = '/code/static/fonts/NotoSansThai-Regular.ttf'
    font_bold = '/code/static/fonts/NotoSansThai-Bold.ttf'
    
    # Read and encode fonts
    with open(font_regular, 'rb') as f:
        regular_font_data = f.read()
    with open(font_bold, 'rb') as f:
        bold_font_data = f.read()
    
    regular_font_b64 = base64.b64encode(regular_font_data).decode('utf-8')
    bold_font_b64 = base64.b64encode(bold_font_data).decode('utf-8')
    
    css_content = f'''
    @font-face {{
        font-family: 'NotoSansThai';
        src: url(data:font/truetype;charset=utf-8;base64,{regular_font_b64}) format('truetype');
        font-weight: normal;
        font-style: normal;
    }}

    @font-face {{
        font-family: 'NotoSansThai';
        src: url(data:font/truetype;charset=utf-8;base64,{bold_font_b64}) format('truetype');
        font-weight: bold;
        font-style: normal;
    }}
    
    * {{
        font-family: 'NotoSansThai', Arial, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}
    
    body {{
        font-family: 'NotoSansThai', Arial, sans-serif;
        line-height: 1.5;
    }}

    strong, b {{
        font-weight: bold !important;
    }}
    
    {template.css_content}
    '''

    css = CSS(string=css_content, font_config=font_config)
    html = HTML(string=html_content, base_url=request.build_absolute_uri('/'), url_fetcher=url_fetcher)
    pdf = html.write_pdf(stylesheets=[css], font_config=font_config)
 
    # Create HTTP response
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="document_{reference_id}_report.pdf"'
    return response


@login_required
def workflow_list(request):
    workflows = ApprovalWorkflow.objects.all()

    if request.htmx:
         return render(request, 'document/components/workflow_list.html', {'workflows': workflows})

    return render(request, 'document/workflow_list_full.html', {'workflows': workflows})

@login_required
def document_list(request):
    user = request.user
    search_query = request.GET.get('search', '')
    workflow_id = request.GET.get('workflow', '')
    status = request.GET.get('status', '')
    page_number = request.GET.get('page', 1)

    documents = get_allowed_documents(user)

    if search_query:
        dynamic_fields = DynamicField.objects.all()
        q_objects = Q()
        for field in dynamic_fields:
            q_objects |= Q(dynamic_values__field=field, dynamic_values__value__icontains=search_query)

        documents = documents.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(document_reference__icontains=search_query) |
            q_objects
        ).distinct()

    if workflow_id:
        documents = documents.filter(workflow_id=workflow_id)

    if status:
        documents = documents.filter(status=status)

    paginator = Paginator(documents, 5)  # Show 5 documents per page
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Calculate the range of page numbers to display
    # Number of page links to show
    max_pages = 5  # Number of page links to show
    current_page = page_obj.number
    page_range = list(paginator.page_range)


    if len(page_range) > max_pages:
        start = max(0, current_page - max_pages // 2 - 1)
        end = start + max_pages
        if end > len(page_range):
            end = len(page_range)
            start = end - max_pages
        page_range = page_range[start:end]

    workflows = ApprovalWorkflow.objects.all()

    context = {
        'documents': page_obj,
        'page_range': page_range,
        'search_query': search_query,
        'selected_workflow': int(workflow_id) if workflow_id else None,
        'selected_status': status,
        'workflows': workflows,
        'status_choices': Document.STATUS_CHOICES,  # Add this line
    }

    if request.htmx:
        return render(request, 'partials/document_list_partial.html', context)
    return render(request, 'document/document_list.html', context)


from django.urls import reverse

@login_required
def document_detail(request, reference_id):
    try:

        document = get_allowed_document(request.user, reference_id)
        # document = get_object_or_404(Document, document_reference=reference_id)
        is_favorite = Favorite.objects.filter(user=request.user, document=document).exists()
        dynamic_values = DynamicFieldValue.objects.filter(document=document).select_related('field')
        user_approval = document.approvals.filter(approver=request.user, step=document.current_step, is_approved__isnull=True).first()
        prepared_values = []
        for value in dynamic_values:
            prepared_value = {
                'name': value.field.name,
                'field_type': value.field.field_type,
            }
            if value.field.field_type == 'product_list':
                products = value.json_value if value.json_value else []
                prepared_value['value'] = products
                prepared_value['total_quantity'] = sum(product['quantity'] for product in products)
                prepared_value['products'] = products  # Add this for template compatibility
            elif value.field.field_type == 'table_list':
                # Get the column order from the field
                columns = [col.strip() for col in value.field.table_columns.split('|') if col.strip()]
                
                # Prepare the rows with ordered columns
                ordered_rows = []
                for row in (value.json_value or []):
                    # Create a new row with columns in the correct order
                    ordered_row = []
                    for col in columns:
                        ordered_row.append((col, row.get(col, '')))
                    ordered_rows.append(ordered_row)
                
                prepared_value['value'] = ordered_rows
                prepared_value['columns'] = columns
                prepared_value['field'] = value.field  # Make sure field is available in template
            elif value.field.field_type == 'attachment' and value.file:
               file_url = reverse('document_approval:view_file', args=[value.id])
               full_file_name = os.path.basename(value.file.name)
               original_file_name = os.path.basename(value.file.name).split("_", 1)[0] + os.path.splitext(full_file_name)[1]
               is_image = value.file.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'))
               prepared_value['file_url'] = file_url
               prepared_value['is_image'] = is_image
               prepared_value['original_file_name'] = original_file_name



            elif value.field.field_type in ['choice', 'multiple_choice']:
                prepared_value['choices'] = value.field.get_choices()
                if value.field.field_type == 'multiple_choice':
                    # Split the comma-separated string and join with nice formatting
                    choices = value.value.split(',') if value.value else []
                    prepared_value['value'] = ', '.join(choices)
                else:
                    prepared_value['value'] = value.value
            else:
                prepared_value['value'] = value.value
            prepared_values.append(prepared_value)

        if request.method == 'POST' and user_approval and document.status == 'in_review':
            errors = {}
            is_approved = request.POST.get('is_approved') == 'true'
            comment = request.POST.get('comment', '')

            edited_values = {}
            uploaded_files = {}

            if user_approval.step.requires_edit:
                for field in user_approval.step.editable_fields.all():
                    field_name = f'dynamic_{field.id}'
                    if field.field_type == 'attachment':
                        file = request.FILES.get(field_name)
                        existing_file = DynamicFieldValue.objects.filter(document=document, field=field).first()
                        if field.required and not file and not (existing_file and existing_file.file):
                            errors[field.name] = ["This attachment is required."]
                        elif file:
                            try:
                                field.validate_file(file)
                                uploaded_files[field_name] = file
                            except ValidationError as e:
                                errors[field.name] = e.messages
                    elif field.field_type == 'choice':
                        value = request.POST.get(field_name)
                        if value:
                            if value not in field.get_choices():
                                errors[field.name] = ["Invalid choice."]
                            else:
                                edited_values[field_name] = value
                        elif field.required:
                            errors[field.name] = ["This field is required."]


                    elif field.field_type == 'multiple_choice':
                        values = request.POST.getlist(f'{field_name}[]')
                        if field.required and not values:
                            errors[field.name] = ["At least one option must be selected"]
                        elif values:
                            edited_values[field_name] = ','.join(values)





                    else:
                        value = request.POST.get(field_name)
                        if value:
                            edited_values[field_name] = value
                        elif field.required:
                            errors[field.name] = ["This field is required."]

            if errors:
                context = {
                    'document': document,
                    'user_approval': user_approval,
                    'errors': errors,
                    'form_data': request.POST,
                }
                html = render_to_string('document/form_errors.html', context)
                return HttpResponse(html, headers={'HX-Retarget': '#form-errors'})

            try:
                document.handle_approval(
                    user=request.user,
                    is_approved=is_approved,
                    comment=comment,
                    edited_values=edited_values,
                    uploaded_files=uploaded_files
                )
                messages.success(request, "Thank you for reviewing the document")

                if request.htmx:
                    response = render(request, 'partials/submit_success.html', {'document': document})
                    return retarget(response, '#content-div')
                return redirect('document_approval:document_detail', reference_id=document.document_reference)

            except ValidationError as ve:
                errors = {field: [str(error)] for field, error in ve.message_dict.items()}
            except Exception as e:
                print(f"Error processing approval: {str(e)}")
                print(traceback.format_exc())
                errors['__all__'] = [f"An unexpected error occurred while processing your approval: {str(e)}"]

            if errors:
                context = {
                    'document': document,
                    'user_approval': user_approval,
                    'errors': errors,
                    'form_data': request.POST,
                }
                html = render_to_string('document/form_errors.html', context)
                return HttpResponse(html, headers={'HX-Retarget': '#form-errors'})

        editable_fields = user_approval.step.editable_fields.all() if user_approval and user_approval.step.requires_edit else []

        ordered_approvals = document.approvals.order_by('-created_at', '-step__order')
        context = {
            'document': document,
            'prepared_values': prepared_values,
            'user_approval': user_approval,
            'can_approve': user_approval and document.status == 'in_review',
            'can_resubmit': document.status in ['rejected','pending'] and request.user == document.submitted_by,
            'can_draw' : document.can_withdraw(request.user),
            'can_cancel' : document.can_cancel(request.user),
            'is_favorite': is_favorite,
            'ordered_approvals':ordered_approvals,
            'editable_fields': editable_fields,
        }

        if request.htmx:
            return render(request, 'document/components/detail_document.html', context)

        return render(request, 'document/document_detail.html', context)
    except Exception as e:

        if request.htmx:
            return HttpResponse("you are not auhtorize", status=500)
        return render(request, 'error.html', {'message': "you are not auhtorize"})


@login_required
def resubmit_document(request, pk):
    document = get_object_or_404(Document, pk=pk)
    workflow = document.workflow
    all_dynamic_fields = workflow.dynamic_fields.all()

    editable_fields = DynamicField.objects.filter(
        approval_steps__workflow=workflow
    ).distinct()

    non_editable_fields = all_dynamic_fields.exclude(id__in=editable_fields)

    prepared_fields = []
    for field in non_editable_fields:
        field_data = {
            'id': field.id,
            'name': field.name,
            'field_type': field.field_type,
            'required': field.required,
            'input_width': field.input_width,
            'textarea_rows': field.textarea_rows,
        }
        field_value = document.dynamic_values.filter(field=field).first()
        if field.field_type == 'product_list':
            field_data['products'] = field_value.json_value if field_value else []
        elif field.field_type == 'table_list':
            field_data['table_columns'] = field.table_columns
            field_data['rows'] = field_value.json_value if field_value else []
        elif field.field_type == 'attachment' and field_value and field_value.file:
            file_url = reverse('document_approval:view_file', args=[field_value.id])
            full_file_name = os.path.basename(field_value.file.name)
            original_file_name = os.path.basename(field_value.file.name).split("_", 1)[0] + os.path.splitext(full_file_name)[1]
            is_image = field_value.file.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'))
            field_data['file_url'] = file_url
            field_data['is_image'] = is_image
            field_data['original_file_name'] = original_file_name
            field_data['file'] = field_value.file
        elif field.field_type in ['choice', 'multiple_choice']:
            field_data['choices'] = field.get_choices()
            if field_value:
                if field.field_type == 'multiple_choice':
                    field_data['value'] = field_value.value.split(',') if field_value.value else []
                else:
                    field_data['value'] = field_value.value
        else:
            field_data['value'] = field_value.value if field_value else ''
        prepared_fields.append(field_data)

    if request.user != document.submitted_by or document.status not in ['pending', 'rejected']:
        return render(request, 'error.html', {'message': "you are not authirized to resubmit this document"})

    if request.method == 'POST':

        form = DocumentSubmissionForm(request.POST, instance=document)
        errors = {}
        dynamic_field_values = []  # Initialize the list here
        total_quantity = 0

        # Validate form fields
        if not form.is_valid():
            errors.update(form.errors)

        # Validate dynamic fields
        for field in non_editable_fields:
            field_key = f'dynamic_{field.id}'
            is_required_for_submission = field.required and field not in editable_fields

            if field.field_type == 'table_list':
                # Get the column names from the field in the correct order
                columns = [col.strip() for col in field.table_columns.split('|') if col.strip()]
                
                # Initialize data structure for rows
                rows = []
                field_errors = []
                
                # Determine the number of rows by checking the first column's data
                if columns:
                    first_col = columns[0].strip()
                    row_count = len(request.POST.getlist(f'table_{field.id}_{first_col}[]'))
                    
                    # Process each row
                    for row_idx in range(row_count):
                        # Create a list of tuples to preserve column order
                        row_items = []
                        row_has_data = False
                        
                        # Process each column in this row in the specified order
                        for col in columns:
                            col_name = col.strip()
                            col_values = request.POST.getlist(f'table_{field.id}_{col_name}[]')
                            
                            if row_idx < len(col_values):
                                col_value = col_values[row_idx]
                                row_items.append((col_name, col_value))
                                if col_value.strip():
                                    row_has_data = True
                            else:
                                row_items.append((col_name, ''))
                        
                        # Only add rows that have at least some data
                        if row_has_data:
                            # Convert the list of tuples to a dictionary while preserving order
                            row_data = {}
                            for col_name, col_value in row_items:
                                row_data[col_name] = col_value
                            rows.append(row_data)
                
                if rows:
                    dynamic_field_values.append(DynamicFieldValue(
                        field=field,
                        json_value=rows
                    ))
                elif is_required_for_submission:
                    field_errors.append("At least one row is required")
                
                if field_errors:
                    errors[field.name] = field_errors
                    
            elif field.field_type == 'product_list':
                product_ids = request.POST.getlist(f'product_id_{field.id}[]')
                product_codes = request.POST.getlist(f'product_code_{field.id}[]')
                product_names = request.POST.getlist(f'product_name_{field.id}[]')
                product_quantities = request.POST.getlist(f'product_quantity_{field.id}[]')
                products = []
                field_errors = []

                for id,code, name, quantity in zip( product_ids,product_codes, product_names, product_quantities):
                    if id or code or name or quantity:
                        if not id:
                            field_errors.append("Id is required")
                        if not code:
                            field_errors.append("Code name is required")
                        if not name:
                            field_errors.append("Product name is required")
                        if not quantity:
                            field_errors.append("Product quantity is required")
                        else:
                            try:
                                qty = int(quantity)
                                products.append({ 'id':id , 'code':code, 'name': name, 'quantity': qty})
                                total_quantity += qty
                            except ValueError:
                                field_errors.append(f"Invalid quantity for product {name}")

                if products:
                    DynamicFieldValue.objects.update_or_create(
                        document=document,
                        field=field,
                        defaults={'json_value': products}
                    )
                elif is_required_for_submission:
                    field_errors.append("At least one product is required")

                if field_errors:
                    errors[field.name] = field_errors
            elif field.name == 'Total Quantity':
                # Get the value from the form directly instead of calculating it
                total_qty_value = request.POST.get(f'dynamic_{field.id}', '0')
                DynamicFieldValue.objects.update_or_create(
                    document=document,
                    field=field,
                    defaults={'value': total_qty_value}
                )


            elif field.field_type == 'attachment':
                file = request.FILES.get(f'dynamic_{field.id}')
                if file:
                    try:
                        field.validate_file(file)
                        
                        # Create DynamicFieldValue without file
                        field_value = DynamicFieldValue(
                            field=field,
                            document=None  # Will be set after document is saved
                        )
                        
                        # Read file content
                        file_content = file.read()
                        
                        # Store the file info for async upload
                        dynamic_field_values.append((field_value, file_content, file.name))
                        
                    except ValidationError as e:
                        errors[field.name] = [str(e)]
                elif is_required_for_submission:
                    errors[field.name] = ["This field is required"]



            elif field.field_type == 'multiple_choice':
                values = request.POST.getlist(f'{field_key}[]')
                if field.required and not values:
                    errors[field.name] = ["At least one option must be selected"]
                elif not all(value in field.get_choices() for value in values):
                    errors[field.name] = ["Invalid choice"]
                else:
                    DynamicFieldValue.objects.update_or_create(
                        document=document,
                        field=field,
                        defaults={'value': ','.join(values)}
                    )

            else:
                value = request.POST.get(f'dynamic_{field.id}')
                if field.required and not value:
                    errors[field.name] = ["This field is required."]
                else:
                    try:
                        # For boolean fields, the value is only present in POST data if checked
                        if field.field_type == 'boolean':
                            value = 'on' if value else ''
                        DynamicFieldValue.objects.update_or_create(
                            document=document,
                            field=field,
                            defaults={'value': value if value is not None else ''}
                        )
                    except Exception as e:
                        errors[field.name] = [f"Error saving field: {str(e)}"]

        if not errors:
            document.resubmit(form.cleaned_data['title'], form.cleaned_data['content'])
            # Save all the DynamicFieldValue objects and start async uploads
            from .tasks import upload_file_to_s3_task
            
            # Track upload tasks
            upload_tasks = []
            
            for field_value_data in dynamic_field_values:
                if isinstance(field_value_data, tuple):
                    # This is a file field
                    field_value, file_content, filename = field_value_data
                    field_value, created = DynamicFieldValue.objects.update_or_create(
                        document=document,
                        field=field_value.field,
                        defaults={'file': None}  # Clear existing file before upload
                    )
                    
                    # Start async upload task
                    task = upload_file_to_s3_task.delay(field_value.id, file_content, filename)
                    upload_tasks.append(task)
                else:
                    # Regular field value
                    DynamicFieldValue.objects.update_or_create(
                        document=document,
                        field=field_value_data.field,
                        defaults={
                            'value': field_value_data.value,
                            'json_value': field_value_data.json_value
                        }
                    )
            
            # Store task IDs in session for status checking
            if upload_tasks:
                request.session['upload_tasks'] = [task.id for task in upload_tasks]
                
            custom_approvers = {}
            for step in workflow.steps.all():
                if step.allow_custom_approver:
                    approver_id = request.POST.get(f'approver_{step.id}')
                    if approver_id:
                        custom_approvers[step.id] = CustomUser.objects.get(id=approver_id)                     
                                    
                                    
            if request.POST.get('save_draft'):
                document.save()
                document.save_draft()
                
                return render(request, 'partials/submit_success.html', {'document': document})
            
            document.create_approvals(custom_approvers)
            messages.success(request, "Document re-submitted successfully")

            response = render(request, 'partials/submit_success.html', {'document': document})
            return retarget(response, '#content-div')

        context = {
            'workflow': workflow,
            'prepared_fields': prepared_fields,
            'errors': errors,
            'form_data': request.POST,
        }
        html = render_to_string('document/form_errors.html', context)
        return HttpResponse(html, headers={'HX-Retarget': '#form-errors'})

    form = DocumentSubmissionForm(instance=document)


    steps_with_approvers = []
    for step in workflow.steps.all():
        potential_approvers = CustomUser.objects.none()  # Initialize with empty queryset
        if step.allow_custom_approver and step.approver_group:
            # Get current user's BU groups
            user_bu_groups = get_user_bu_groups(request.user)
            
            # Get all users in the approver group
            approvers = CustomUser.objects.filter(groups=step.approver_group).distinct()
            potential_approvers = []
            
            # Filter approvers who share any BU with current user
            for approver in approvers:
                approver_bu_groups = get_user_bu_groups(approver)
                if any(bu in user_bu_groups for bu in approver_bu_groups):
                    potential_approvers.append(approver)
            
            potential_approvers = CustomUser.objects.filter(id__in=[u.id for u in potential_approvers])

        if potential_approvers.exists():
            previous_approver = document.approvals.filter(step=step).first()
            # Convert potential approvers to JSON-serializable format
            potential_approvers_json = [
                {
                    'id': user.id,
                    'full_name': user.get_full_name() or user.username,
                    'username': user.username,
                    'email': user.email
                } for user in potential_approvers
            ]
            steps_with_approvers.append({
                'step': step,
                'potential_approvers': potential_approvers,
                'potential_approvers_json': potential_approvers_json,
                'previous_approver': previous_approver.approver if previous_approver else None
            })

    context = {
        'form': form,
        'document': document,
        'workflow': document.workflow,
        'prepared_fields': prepared_fields,
       'steps_with_approvers': steps_with_approvers,
    }

    if request.htmx:
        return render(request, 'document/components/resubmit_document.html', context)

    return render(request, 'document/resubmit_document_full.html', context)



@login_required
def withdraw_document(request, document_id):
    document = get_object_or_404(Document, pk=document_id)

    if request.method == 'POST':
        if document.can_withdraw(request.user):
            document.withdraw()
            messages.success(request, "Document has been successfully withdrawn.")

            if request.htmx:

                user_approval = document.approvals.filter(
                    approver=request.user,
                    step=document.current_step,
                    is_approved__isnull=True
                ).first()

                context = {
                    'document': document,
                    'can_resubmit': document.status in ['rejected','pending'] and request.user == document.submitted_by,
                    'can_draw' : document.can_withdraw(request.user),
                    'can_cancel': document.can_cancel(request.user),
                    'user_approval': None,   # might not need
                    'can_approve': False,
                }
                status_html = render_to_string('partials/document_status.html', context, request=request)
                actions_html = render_to_string('partials/document_actions.html', context, request=request)
                approval_form_html = render_to_string('partials/approval_form.html', context, request=request)
                return HttpResponse(
                    status_html +
                    '<div id="document-actions" hx-swap-oob="true">' + actions_html + '</div>'
                     '<div id="approval-form" hx-swap-oob="true">' + approval_form_html + '</div>'
                     '<div id="user-approvals" hx-swap-oob="true"></div>' # remove approval step 
                )
            else:
                return redirect('document_approval:document_detail', reference_id=document.document_reference)
        else:
            messages.error(request, "You don't have permission to withdraw this document.")

            if request.htmx:
                return HttpResponse(
                    '<div class="mb-2 text-red-500">You don\'t have permission to withdraw this document.</div>',
                    status=200
                )
            else:
                return redirect('document_approval:document_detail', reference_id=document.document_reference)

    # If it's not a POST request, redirect to document detail
    return redirect('document_approval:document_detail', reference_id=document.document_reference)

@login_required
def cancel_document(request, document_id):
    document = get_object_or_404(Document, id=document_id, submitted_by=request.user)

    if request.method == 'POST':
        try:
            document.cancel()
            messages.success(request, "Document is Cancel")
        except ValidationError as e:
            messages.error(request, str(e))

    # return redirect('document_approval:document_detail', pk=document.pk)

    response = render(request, 'partials/submit_success.html', {'document':document})

    return retarget(response, '#content-div')

@login_required
def submit_document(request, workflow_id):
    workflow = get_object_or_404(ApprovalWorkflow, id=workflow_id)
    all_dynamic_fields = workflow.dynamic_fields.all()

    editable_fields = DynamicField.objects.filter(
        approval_steps__workflow=workflow
    ).distinct()

    non_editable_fields = all_dynamic_fields.exclude(id__in=editable_fields)

    prepared_fields = []
    for field in non_editable_fields:
        field_data = {
            'id': field.id,
            'name': field.name,
            'field_type': field.field_type,
            'required': field.required,
            'editable_in_steps': field in editable_fields,
            'input_width': field.input_width,
            'textarea_rows': field.textarea_rows,
        }
        if field.field_type in ['choice', 'multiple_choice']:
            field_data['choices'] = [choice.strip() for choice in field.choices.split(',') if choice.strip()]
        elif field.field_type == 'product_list':
            field_data['default_products'] = [{'id':'','code':'','name': '', 'quantity': ''} for _ in range(2)]
        elif field.field_type == 'table_list':
            field_data['table_columns'] = field.table_columns
        prepared_fields.append(field_data)

    if request.method == 'POST':
        form = DocumentSubmissionForm(request.POST)
        total_quantity = 0
        errors = {}
        dynamic_field_values = []

        # Validate form fields
        if not form.is_valid():
            errors.update(form.errors)

        # Validate dynamic fields
        for field in non_editable_fields:
            field_key = f'dynamic_{field.id}'
            is_required_for_submission = field.required and field not in editable_fields

            if field.field_type == 'table_list':
                # Get the column names from the field in the correct order
                columns = [col.strip() for col in field.table_columns.split('|') if col.strip()]
                
                # Initialize data structure for rows
                rows = []
                field_errors = []
                
                # Determine the number of rows by checking the first column's data
                if columns:
                    first_col = columns[0].strip()
                    row_count = len(request.POST.getlist(f'table_{field.id}_{first_col}[]'))
                    
                    # Process each row
                    for row_idx in range(row_count):
                        # Create a list of tuples to preserve column order
                        row_items = []
                        row_has_data = False
                        
                        # Process each column in this row in the specified order
                        for col in columns:
                            col_name = col.strip()
                            col_values = request.POST.getlist(f'table_{field.id}_{col_name}[]')
                            
                            if row_idx < len(col_values):
                                col_value = col_values[row_idx]
                                row_items.append((col_name, col_value))
                                if col_value.strip():
                                    row_has_data = True
                            else:
                                row_items.append((col_name, ''))
                        
                        # Only add rows that have at least some data
                        if row_has_data:
                            # Convert the list of tuples to a dictionary while preserving order
                            row_data = {}
                            for col_name, col_value in row_items:
                                row_data[col_name] = col_value
                            rows.append(row_data)
                
                if rows:
                    dynamic_field_values.append(DynamicFieldValue(
                        field=field,
                        json_value=rows
                    ))
                elif is_required_for_submission:
                    field_errors.append("At least one row is required")
                
                if field_errors:
                    errors[field.name] = field_errors
                    
            elif field.field_type == 'product_list':
                product_ids = request.POST.getlist(f'product_id_{field.id}[]')
                product_codes = request.POST.getlist(f'product_code_{field.id}[]')
                product_names = request.POST.getlist(f'product_name_{field.id}[]')
                product_quantities = request.POST.getlist(f'product_quantity_{field.id}[]')
                products = []
                field_errors = []

                for id,code, name, quantity in zip( product_ids,product_codes, product_names, product_quantities):
                    if id or code or name or quantity:
                        if not id:
                            field_errors.append("Id is required")
                        if not code:
                            field_errors.append("Code name is required")
                        if not name:
                            field_errors.append("Product name is required")
                        if not quantity:
                            field_errors.append("Product quantity is required")
                        else:
                            try:
                                qty = int(quantity)
                                products.append({ 'id':id , 'code':code, 'name': name, 'quantity': qty})
                                total_quantity += qty
                            except ValueError:
                                field_errors.append(f"Invalid quantity for product {name}")

                if products:
                    dynamic_field_values.append(DynamicFieldValue(
                        field=field,
                        json_value=products
                    ))
                elif is_required_for_submission:
                    field_errors.append("At least one product is required")

                if field_errors:
                    errors[field.name] = field_errors

            elif field.name == 'Total Quantity':
                # Try to get the value from the form first
                form_total = request.POST.get(f'dynamic_{field.id}')
                
                # If not provided in the form, use the calculated total
                final_total = form_total if form_total else str(total_quantity)
                
                dynamic_field_values.append(DynamicFieldValue(
                    field=field,
                    value=final_total
                ))

            elif field.field_type == 'attachment':
                file = request.FILES.get(f'dynamic_{field.id}')
                if file:
                    try:
                        field.validate_file(file)
                        
                        # Create DynamicFieldValue without file
                        field_value = DynamicFieldValue(
                            field=field,
                            document=None  # Will be set after document is created
                        )
                        
                        # Read file content
                        file_content = file.read()
                        
                        # Store the file info for async upload
                        dynamic_field_values.append((field_value, file_content, file.name))
                        
                    except ValidationError as e:
                        errors[field.name] = [str(e)]
                elif is_required_for_submission:
                    errors[field.name] = ["This field is required"]

            elif field.field_type == 'multiple_choice':
                values = request.POST.getlist(f'{field_key}[]')
                if is_required_for_submission and not values:
                    errors[field.name] = ["At least one option must be selected"]
                elif not all(value in field.get_choices() for value in values):
                    errors[field.name] = ["Invalid choice"]
                else:
                    dynamic_field_values.append(DynamicFieldValue(
                        field=field,
                        value=','.join(values)  # Store as comma-separated string
                    ))

            else:
                value = request.POST.get(f'dynamic_{field.id}')
                if field.required and not value:
                    errors[field.name] = ["This field is required."]
                else:
                    try:
                        # For boolean fields, the value is only present in POST data if checked
                        if field.field_type == 'boolean':
                            value = 'on' if value else ''
                        dynamic_field_values.append(DynamicFieldValue(
                            field=field,
                            value=value
                        ))
                    except Exception as e:
                        errors[field.name] = [f"Error saving field: {str(e)}"]

        if errors:
            context = {
                'workflow': workflow,
                'prepared_fields': prepared_fields,
                'errors': errors,
                'form_data': request.POST,
            }
            html = render_to_string('document/form_errors.html', context)
            return HttpResponse(html, headers={'HX-Retarget': '#form-errors'})

        # If there are no errors, proceed with saving the document
        document = form.save(commit=False)
        document.submitted_by = request.user
        document.workflow = workflow
        document.save()

        # Save all the DynamicFieldValue objects and start async uploads
        from .tasks import upload_file_to_s3_task
        
        # Track upload tasks
        upload_tasks = []
        
        for field_value_data in dynamic_field_values:
            if isinstance(field_value_data, tuple):
                # This is a file field
                field_value, file_content, filename = field_value_data
                field_value.document = document
                field_value.save()
                
                # Start async upload task
                task = upload_file_to_s3_task.delay(field_value.id, file_content, filename)
                upload_tasks.append(task)
            else:
                # Regular field value
                field_value_data.document = document
                field_value_data.save()
        
        # Store task IDs in session for status checking
        if upload_tasks:
            request.session['upload_tasks'] = [task.id for task in upload_tasks]

        custom_approvers = {}
        for step in workflow.steps.all():
                if step.allow_custom_approver:
                    approver_id = request.POST.get(f'approver_{step.id}')
                    if approver_id:
                        custom_approvers[step.id] = CustomUser.objects.get(id=approver_id)

        try:
            
            if request.POST.get('save_draft'):
                document.save()
                document.save_draft()
                
                return render(request, 'partials/submit_success.html', {'document': document})
            
            else :
                document.create_approvals(custom_approvers)
                print(f"Approvals created for document {document.id}")
                messages.success(request, "Document submitted successfully")
                response = render(request, 'partials/submit_success.html', {'document': document})
                return retarget(response, '#content-div')
            
        except Exception as e:
            print(f"Error creating approvals for document {document.id}: {str(e)}")
            document.delete()
            messages.error(request, "Error creating approvals. Please try again.")
            context = {
                'workflow': workflow,
                'prepared_fields': prepared_fields,
                'form_data': request.POST,
            }
            return render(request, 'document/components/submit_document.html', context)

    else:
        form = DocumentSubmissionForm()

        steps_with_approvers = []
        for step in workflow.steps.all():
            if step.allow_custom_approver and step.approver_group:         
                
                # Get current user's BU groups
                user_bu_groups = get_user_bu_groups(request.user)                
                # Get all users in the approver group
                approvers = CustomUser.objects.filter(groups=step.approver_group).distinct()
                potential_approvers = []
                
                # Filter approvers who share any BU with current user
                for approver in approvers:
                    approver_bu_groups = get_user_bu_groups(approver)
                    if any(bu in user_bu_groups for bu in approver_bu_groups):
                        potential_approvers.append({
                            'id': approver.id,
                            'username': approver.username,
                            'first_name': approver.first_name,
                            'last_name': approver.last_name,
                            'full_name': approver.get_full_name() or approver.username
                        })
                
                steps_with_approvers.append({
                    'step': step,
                    'potential_approvers': potential_approvers

                })
        context = {
            'form': form,
            'workflow': workflow,
            'prepared_fields': prepared_fields,
            # 'potential_approvers': CustomUser.objects.all(),
            'steps_with_approvers': steps_with_approvers,
        }

        if request.htmx:
            return render(request, 'document/components/submit_document.html', context)

        return render(request, 'document/submit_document_full.html', context)


from django.db import models

@login_required
def documents_to_approve_to_resubmit(request):
    # Documents waiting for current user's approval
    documents_to_approve = Document.objects.filter(
        status='in_review',
        current_step__isnull=False,  # Ensure there is a current step
        approvals__step=models.F('current_step'),  # Approval matches current step
        approvals__approver=request.user,  # User is the approver
        approvals__is_approved__isnull=True  # Approval is pending
    )

    # Documents rejected that the user can resubmit
    documents_reject = Document.objects.filter(
        submitted_by=request.user,
        status='rejected'
    )

     # Documents rejected that the user can resubmit
    documents_to_resubmit = Document.objects.filter(
        submitted_by=request.user,
        status='pending'
    )

    # Combine both querysets and order by newest first
    documents = (documents_to_approve | documents_reject | documents_to_resubmit).distinct().order_by('-updated_at')

    context = {
        'documents': documents,
    }
    return render(request, 'document/documents_to_action.html', context)


def clear_toast(request):
    return HttpResponse("")

import boto3

@login_required
def view_file(request, field_value_id):
    """
    Serve a file from S3 if the user has access to the related document.
    """
    from document.models import DynamicFieldValue  # Ensure this import matches your model's location
    dynamic_field_value = get_object_or_404(DynamicFieldValue, pk=field_value_id)

    # Check if the user has access to this file
    if not dynamic_field_value.has_access(request.user):
        return HttpResponseForbidden("You do not have permission to view this file.")

    # Check if the file exists
    if not dynamic_field_value.file:
        return HttpResponseForbidden("No file is associated with this field value.")

    # Generate a signed URL for the file
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,  # Custom S3-compatible endpoint
    )

    try:
        # Ensure the Key matches the exact file path in your bucket
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': dynamic_field_value.file.name,  # Full path of the file
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        return HttpResponseRedirect(signed_url)
    except Exception as e:
        # Handle errors in generating the signed URL
        return HttpResponseForbidden(f"Error generating URL: {e}")

from django.http import JsonResponse
from .notification_models import Notification

@login_required
def load_notifications(request):
    """Load notifications and return both notifications and unread count"""
    # Get the latest notifications
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-timestamp')[:10]
    
    # Get unread count from database with debug info
    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    )
    unread_count = unread_notifications.count()    
  
    
    # Prepare notification data
    notification_data = [{
        'id': n.id,
        'message': n.message,
        'workflow_name': n.workflow_name,
        'url': n.url,
        'timestamp': n.timestamp.isoformat(),
        'is_read': n.is_read
    } for n in notifications]    

    return JsonResponse({
        'notifications': notification_data,
        'unread_count': unread_count
    })

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a notification as read and return updated counts"""
    try:
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        
        # Get updated unread count
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        return JsonResponse({
            'status': 'success',
            'unread_count': unread_count
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_POST
def delete_notification(request, notification_id):
    """Delete a single notification"""
    try:
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.delete()
        
        # Get updated unread count
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Notification deleted',
            'unread_count': unread_count
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_POST
def clear_all_notifications(request):
    """Delete all notifications for the current user"""
    try:
        # Delete all notifications for the user
        deleted_count = Notification.objects.filter(
            user=request.user
        ).delete()[0]
        
        return JsonResponse({
            'status': 'success',
            'message': f'Deleted {deleted_count} notifications',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def view_editor_image(request, image_id):
    """
    Serve an editor image from S3 if the user has access to the related document.
    """
    editor_image = get_object_or_404(EditorImage, pk=image_id)

    # Check if the user has access to this image
    if not editor_image.has_access(request.user):
        return HttpResponseForbidden("You do not have permission to view this image.")

    # Check if the file exists
    if not editor_image.image:
        return HttpResponseForbidden("No image file found.")

    # Generate a signed URL for the file
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
    )

    try:
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': editor_image.image.name,
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        return HttpResponseRedirect(signed_url)
    except Exception as e:
        return HttpResponseForbidden(f"Error generating URL: {e}")

@login_required
def check_upload_status(request):
    """Check the status of file uploads"""
    from celery.result import AsyncResult
    
    task_ids = request.session.get('upload_tasks', [])
    if not task_ids:
        return JsonResponse({
            'status': 'complete',
            'message': 'No uploads in progress'
        })
    
    # Check each task
    results = []
    all_complete = True
    
    for task_id in task_ids:
        result = AsyncResult(task_id)
        if result.ready():
            task_result = result.get()
            results.append({
                'status': task_result['status'],
                'message': task_result['message']
            })
        else:
            all_complete = False
            results.append({
                'status': 'in_progress',
                'message': 'Upload in progress...'
            })
    
    # Clear session if all complete
    if all_complete:
        del request.session['upload_tasks']
    
    return JsonResponse({
        'status': 'complete' if all_complete else 'in_progress',
        'uploads': results
    })
