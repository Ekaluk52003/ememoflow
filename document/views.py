from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Q
from .models import Document, Approval, ApprovalWorkflow, ApprovalStep, DynamicField, DynamicFieldValue, PDFTemplate, ReportConfiguration
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

from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@login_required
@require_http_methods(["DELETE"])
def delete_attachment(request, field_id, document_id):
    field_value = get_object_or_404(DynamicFieldValue, field_id=field_id, document__submitted_by=request.user,  document_id=document_id)

    print('file found',  field_value )


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
    return render(request, 'document/workflow_list.html', {'workflows': workflows})

@login_required
def document_list(request):
    documents = Document.objects.all().order_by('-created_at')
    return render(request, 'document/document_list.html', {'documents': documents})

@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
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
        except ValidationError as e:
            messages.error(request, str(e))
        return redirect('document_approval:document_detail', pk=document.pk)

    context = {
        'document': document,
        'prepared_values': prepared_values,
        'user_approval': user_approval,
        'can_approve': user_approval and document.status == 'in_review',
        'can_resubmit': document.status in ['rejected','pending'] and request.user == document.submitted_by,
        'can_draw' : document.can_withdraw(request.user)
    }

    # for field in dynamic_field_values :
    #     print(field.field.field_type )
    #     # print(field.value )

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
#done upadte
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
        if form.is_valid():
            document = form.save(commit=False)
            document.submitted_by = request.user
            document.workflow = workflow
            document.status = 'in_review'
            document.current_step = workflow.steps.first()
            document.save()

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
                                total_quantity += qty  # Add to total quantity
                            except ValueError:
                                messages.error(request, f"Invalid quantity for product {name}")
                                document.delete()
                                return render(request, 'document_approval:submit_document.html', {'workflow': workflow, 'prepared_fields': prepared_fields})

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
                            DynamicFieldValue.objects.create(
                            document=document,
                            field=field,
                            file=file
                    )

                else:
                    value = request.POST.get(f'dynamic_{field.id}')
                    if field.required and not value:
                        document.delete()
                        messages.error(request, f"{field.name} is required.")
                        return render(request, 'submit_document.html', {'workflow': workflow, 'prepared_fields': prepared_fields})

                    DynamicFieldValue.objects.create(
                        document=document,
                        field=field,
                        value=value
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

    else:
        form = DocumentSubmissionForm()
        context = {
        'form': form,
        'workflow': workflow,
        'prepared_fields': prepared_fields,
        'potential_approvers': CustomUser.objects.all(),
        }

        print('prepare field', prepared_fields)
        return render(request, 'document/submit_document.html', context)


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