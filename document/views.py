from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Q
from .models import Document, Approval, ApprovalWorkflow, ApprovalStep, DynamicField, DynamicFieldValue, PDFTemplate, ReportConfiguration, Favorite
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import HttpResponse
from django.template import Context, Template
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
import requests
from .forms import DocumentSubmissionForm
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Exists, OuterRef
from django.shortcuts import render
from django.core.paginator import Paginator
from .tasks import upload_file_task
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django_htmx.http import retarget
import logging
from django.views.decorators.http import require_POST
import time

logger = logging.getLogger(__name__)


def load_editor(request, content):
    context = {
            content: content
        }
    return render(request, 'document/components/quill_editor.html',   context)

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

@require_http_methods(["GET"])
def add_product_field(request, field_id):
    context = {
        'field_id': field_id,
        'product_index': request.GET.get('index', 0)
    }
    return render(request, 'partials/product_field.html', context)

def generate_pdf_report(request, document_id, template_id):
    document = get_object_or_404(Document, id=document_id)
    template = get_object_or_404(PDFTemplate, id=template_id)
    report_config = ReportConfiguration.objects.first()  # Assuming you have only one configuration

    # Get the context data from the document
    context_data = document.get_report_context()

    # Add report configuration to context
    context_data['report_config'] = report_config

    # Render the template with the document data
    html_template = Template(template.html_content)
    context = Context(context_data)
    html_content = html_template.render(context)

    # Fetch Bootstrap 5 CSS
    bootstrap_css = requests.get('https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css').text

    # Generate PDF
    font_config = FontConfiguration()
    html = HTML(string=html_content)
    css = CSS(string=bootstrap_css + template.css_content, font_config=font_config)

    pdf = html.write_pdf(stylesheets=[css], font_config=font_config)

    # Create HTTP response
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="document_{document_id}_report.pdf"'
    return response


@login_required
def workflow_list(request):
    workflows = ApprovalWorkflow.objects.all()

    if request.htmx:
         return render(request, 'document/components/workflow_list.html', {'workflows': workflows})

    return render(request, 'document/workflow_list_full.html', {'workflows': workflows})



def get_allowed_documents(user):
    # Check if the user is in the "super user" group
    is_superuser = user.groups.filter(name='super user').exists()

    # Base queryset
    documents = Document.objects.all()

    if not is_superuser:
        # If not a superuser, filter documents where the user is an approver or the submitter
        approver_documents = Approval.objects.filter(
            document=OuterRef('pk'),
            approver=user
        )
        documents = documents.filter(
            Q(Exists(approver_documents)) |  # User is an approver
            Q(submitted_by=user)  # User is the submitter
        )

    # Order the documents by creation date, most recent first
    return documents.order_by('-created_at')

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
            q_objects
        ).distinct()

    if workflow_id:
        documents = documents.filter(workflow_id=workflow_id)

    if status:
        documents = documents.filter(status=status)

    paginator = Paginator(documents, 10)  # Show 10 documents per page
    page_obj = paginator.get_page(page_number)

    workflows = ApprovalWorkflow.objects.all()

    context = {
        'documents': page_obj,
        'search_query': search_query,
        'selected_workflow': int(workflow_id) if workflow_id else None,
        'selected_status': status,
        'workflows': workflows,
        'status_choices': Document.STATUS_CHOICES,  # Add this line
    }

    if request.htmx:
        return render(request, 'partials/document_list_partial.html', context)
    return render(request, 'document/document_list.html', context)

@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
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
            prepared_value['value'] = value.json_value
            prepared_value['total_quantity'] = sum(product['quantity'] for product in value.json_value)
        elif value.field.field_type == 'attachment':
            prepared_value['file'] = value.file
        else:
            prepared_value['value'] = value.value
        prepared_values.append(prepared_value)

    if request.method == 'POST' and user_approval and document.status == 'in_review':
        try:
            document.handle_approval(
                user=request.user,
                is_approved=request.POST.get('is_approved') == 'true',
                comment=request.POST.get('comment', ''),
                user_input=request.POST.get('user_input', ''),
                uploaded_file=request.FILES.get('user_input_file')
            )
            messages.success(request, "Approval decision recorded successfully.")
        except Approval.MultipleObjectsReturned as e:
            logger.error(f"MultipleObjectsReturned in handle_approval for document {document.id}, user {request.user.id}, step {document.current_step.id}")
            # Log the conflicting approvals
            conflicting_approvals = document.approvals.filter(
                approver=request.user,
                step=document.current_step,
                is_approved__isnull=True
            )
            logger.error(f"Conflicting approvals: {list(conflicting_approvals.values('id', 'created_at'))}")
            messages.error(request, "An error occurred due to multiple pending approvals. Please contact support.")
        except ValidationError as e:
            messages.error(request, str(e))
        return redirect('document_approval:document_detail', pk=document.pk)
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
        'ordered_approvals':ordered_approvals
    }

    return render(request, 'document/document_detail.html', context)


@login_required
def resubmit_document(request, pk):
    document = get_object_or_404(Document, pk=pk)
    workflow = document.workflow
    dynamic_fields = workflow.dynamic_fields.all()

    if request.user != document.submitted_by or document.status not in ['pending', 'rejected']:
        return HttpResponseForbidden("You don't have permission to resubmit this document.")

    if request.method == 'POST':
        form = DocumentSubmissionForm(request.POST, instance=document)
        if form.is_valid():
            title = form.cleaned_data['title']
            content = form.cleaned_data['content']
            document.resubmit(title, content)

        total_quantity = 0

        for field in dynamic_fields:
            if field.field_type == 'product_list':
                product_names = request.POST.getlist(f'product_name_{field.id}[]')
                product_quantities = request.POST.getlist(f'product_quantity_{field.id}[]')
                products = []
                for name, quantity in zip(product_names, product_quantities):
                    if name and quantity:
                        try:
                            qty = int(quantity)
                            products.append({'name': name, 'quantity': qty})
                            total_quantity += qty
                        except ValueError:
                            messages.error(request, f"Invalid quantity for product {name}")
                            return render(request, 'resubmit_document.html', {'document': document, 'workflow': workflow, 'dynamic_fields': dynamic_fields})

                DynamicFieldValue.objects.update_or_create(
                    document=document,
                    field=field,
                    defaults={'json_value': products}
                )
            elif field.field_type == 'attachment':

                file = request.FILES.get(f'dynamic_{field.id}')
                print('atachment processing')
                print('atachment processing', file)
                if file:
                    DynamicFieldValue.objects.update_or_create(
                        document=document,
                        field=field,
                        defaults={'file': file}
                    )

            # elif field.field_type == 'attachment':

            #             file = request.FILES.get(f'dynamic_{field.id}')
            #             if file:
            #                 DynamicFieldValue.objects.create(
            #                 document=document,
            #                 field=field,
            #                 file=file
            #         )

            elif field.field_type == 'number' and field.name == 'Total Quantity':
                # Update the Total Quantity field with the calculated total
                print('total--------', total_quantity)
                DynamicFieldValue.objects.update_or_create(
                    document=document,
                    field=field,
                    defaults={'value': str(total_quantity)}
                )
            else:
                value = request.POST.get(f'dynamic_{field.id}')
                if field.required and not value:
                    messages.error(request, f"{field.name} is required.")
                    return render(request, 'resubmit_document.html', {'document': document, 'workflow': workflow, 'dynamic_fields': dynamic_fields})

                DynamicFieldValue.objects.update_or_create(
                    document=document,
                    field=field,
                    defaults={'value': value}
                )



        custom_approvers = {}
        if workflow.allow_custom_approvers:
                for step in workflow.steps.all():
                    approver_id = request.POST.get(f'approver_{step.id}')
                    if approver_id:
                        custom_approvers[step.id] = CustomUser.objects.get(id=approver_id)

        document.create_approvals(custom_approvers)
        messages.success(request, "Document submitted successfully, but no approver was found for the first step.")

        return redirect('document_approval:document_detail', pk=document.pk)


    form = DocumentSubmissionForm(instance=document)

    prepared_fields = []
    for field in dynamic_fields:
        field_data = {
            'id': field.id,
            'name': field.name,
            'field_type': field.field_type,
            'required': field.required,
        }
        field_value = document.dynamic_values.filter(field=field).first()
        if field.field_type == 'product_list':
            field_data['products'] = field_value.json_value if field_value else []
        elif field.field_type == 'attachment':
            field_data['file'] = field_value.file if field_value else None
        elif field.field_type == 'choice':
            field_data['choices'] = [choice.strip() for choice in field.choices.split(',') if choice.strip()]
            field_data['value'] = field_value.value if field_value else ''
        else:
            field_data['value'] = field_value.value if field_value else ''
        prepared_fields.append(field_data)


    context = {
            'form': form,
            'document': document,
            'workflow': document.workflow,
            'prepared_fields': prepared_fields,
            'potential_approvers': CustomUser.objects.all(),
        }
    return render(request, 'document/resubmit_document.html', context)



@login_required
def withdraw_document(request, document_id):
    document = get_object_or_404(Document, id=document_id, submitted_by=request.user)

    if request.method == 'POST':
        try:
            document.withdraw()
            messages.success(request, "Document has been successfully withdrawn.")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect('document_approval:document_detail', pk=document.pk)

@login_required
def cancel_document(request, document_id):
    document = get_object_or_404(Document, id=document_id, submitted_by=request.user)

    if request.method == 'POST':
        try:
            document.cancel()
            messages.success(request, "Document has been successfully withdrawn.")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect('document_approval:document_detail', pk=document.pk)


@login_required
def submit_document(request, workflow_id):
    workflow = get_object_or_404(ApprovalWorkflow, id=workflow_id)
    dynamic_fields = workflow.dynamic_fields.all()


    prepared_fields = []
    for field in dynamic_fields:
        field_data = {
            'id': field.id,
            'name': field.name,
            'field_type': field.field_type,
            'required': field.required,
        }
        if field.field_type == 'choice':
            field_data['choices'] = [choice.strip() for choice in field.choices.split(',') if choice.strip()]
        elif field.field_type == 'product_list':
            field_data['default_products'] = [{'name': '', 'quantity': ''} for _ in range(2)]
        prepared_fields.append(field_data)


    if request.method == 'POST':
        form = DocumentSubmissionForm(request.POST)
        print('posting')
        if form.is_valid():
            document = form.save(commit=False)
            document.submitted_by = request.user
            document.workflow = workflow
            document.status = 'in_review'
            document.current_step = workflow.steps.first()
            document.save()

            total_quantity = 0
            errors = []
            for field in dynamic_fields:
                if field.field_type == 'product_list':
                    product_names = request.POST.getlist(f'product_name_{field.id}[]')
                    product_quantities = request.POST.getlist(f'product_quantity_{field.id}[]')
                    products = []
                    for name, quantity in zip(product_names, product_quantities):
                        if name and quantity:
                            try:
                                qty = int(quantity)
                                products.append({'name': name, 'quantity': qty})
                                total_quantity += qty  # Add to total quantity
                            except ValueError:
                                messages.error(request, f"Invalid quantity for product {name}")
                                document.delete()
                                errors.append(f"Invalid quantity for product {name}")

                    DynamicFieldValue.objects.create(
                            document=document,
                            field=field,
                            json_value=products
                        )

                elif field.name == 'Total Quantity':  # Assuming you have a field named 'Total Quantity'
                    DynamicFieldValue.objects.create(
                    document=document,
                    field=field,
                    value=str(total_quantity)  # Store the calculated total quantity
                )

                elif field.field_type == 'attachment':
                    file = request.FILES.get(f'dynamic_{field.id}')
                    if file:
                        try:
                            DynamicFieldValue.objects.create(
                            document=document,
                            field=field,
                            file=file
                             )
                        except Exception as e:
                            errors.append(f"Error uploading file for {field.name}: {str(e)}")
                    elif field.required:
                        errors.append(f"{field.name} is required.")


                else:
                    value = request.POST.get(f'dynamic_{field.id}')
                    if field.required and not value:
                        document.delete()
                        messages.error(request, f"{field.name} is required.")
                        errors.append(f"{field.name} is required.")

                    DynamicFieldValue.objects.create(
                        document=document,
                        field=field,
                        value=value
                    )

            if errors:
                context = {
                    'workflow': workflow,
                    'prepared_fields': prepared_fields,
                    'errors': errors,
                    'form_data': request.POST,
                }
                html = render_to_string('document/form_errors.html', context)
                return HttpResponse(html, headers={'HX-Retarget': '#form-errors'})

            custom_approvers = {}
            if workflow.allow_custom_approvers:
                for step in workflow.steps.all():
                    approver_id = request.POST.get(f'approver_{step.id}')
                    if approver_id:
                        custom_approvers[step.id] = CustomUser.objects.get(id=approver_id)
            try:
                document.create_approvals(custom_approvers)
                logger.info(f"Approvals created for document {document.id}")
            except Exception as e:
                logger.error(f"Error creating approvals for document {document.id}: {str(e)}")
                document.delete()  # Delete the document if approval creation fai

            # messages.success(request, "Document submitted successfully, but no approver was found for the first step.")

            response = render(request, 'partials/submit_success.html', {'document':document})

            return retarget(response, '#content-div')

            # return redirect('document_approval:document_detail', pk=document.pk)
            # return HttpResponse(headers={'HX-Redirect': reverse('document_approval:document_detail', kwargs={'pk': document.pk})})

        else:
            print("Form errors:", form.errors)
            return HttpResponse(form.errors.as_json(), status=400, content_type='application/json')

    else:

        form = DocumentSubmissionForm()
        context = {
        'form': form,
        'workflow': workflow,
        'prepared_fields': prepared_fields,
        'potential_approvers': CustomUser.objects.all(),
        }

        if request.htmx:
            print('htmx request')
            return render(request, 'document/components/submit_document.html', context)


        return render(request, 'document/submit_document_full.html', context)


@login_required
def documents_to_approve_to_resubmit(request):
    # This Django ORM query is fetching a specific set of documents based on certain conditions. Let's break it down:

# Document.objects.filter(...): This starts a query on the Document model.
# Q(current_step__approval__approver=request.user):
# This looks for documents where the current step has an approval assigned to the current user.
# Q(current_step__approval__is_approved=None):
# This further filters to only include documents where that approval is pending (not yet approved or rejected).
# Q(status='in_review'):
# This ensures only documents with the status 'in_review' are included.
# .distinct():
# This removes any duplicate results that might occur due to the nature of the query joins.
# .order_by('-created_at'):
# This orders the results by the creation date in descending order (newest first).
# Putting it all together, this query is finding:
# "All documents that are currently in review, where the current step has a pending approval assigned to the current user, ordered from newest to oldest."
# This query would typically be used to show a user all the documents that are waiting for their approval. It ensures that:

# The document is in the review process.
# The current user is responsible for the next approval.
# That approval hasn't been made yet (it's still pending).

# The distinct() call is important because without it, you might get duplicate documents if a user has multiple approvals on different steps of the same document.
    documents_to_approve = Document.objects.filter(
        Q(current_step__approval__approver=request.user) &
        Q(current_step__approval__is_approved=None) &
        Q(status='in_review')
    )

    # Documents rejected that the user can resubmit
    documents_to_resubmit = Document.objects.filter(
        Q(submitted_by=request.user) &
        Q(status='rejected')
    )

    # Combine both querysets
    documents = (documents_to_approve | documents_to_resubmit).distinct().order_by('-updated_at')

    context = {
        'documents': documents,

    }
    return render(request, 'document/documents_to_action.html', context)