from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from .models import DynamicField, ApprovalWorkflow

@login_required
def field_list(request):
    """List all dynamic fields with filtering options"""
    fields = DynamicField.objects.all().order_by('name')
    
    # Filter by field type if requested
    field_type = request.GET.get('type')
    if field_type:
        fields = fields.filter(field_type=field_type)
    
    return render(request, 'document/dynamic_fields/field_list.html', {
        'fields': fields,
        'field_types': DynamicField.FIELD_TYPES
    })

@login_required
def create_field(request):
    """Create a new dynamic field using Alpine.js"""
    # Get workflow_id from query parameters if available
    workflow_id = request.GET.get('id')
    workflow = None
    
    if workflow_id:
        workflow = get_object_or_404(ApprovalWorkflow, id=workflow_id)
    
    if request.method == 'POST':
        try:
            # Get basic field data
            name = request.POST.get('name')
            field_type = request.POST.get('field_type')
            required = request.POST.get('required') == 'true'
            input_width = request.POST.get('width', 'full')  # Get width from form but use as input_width
            order = request.POST.get('order', 0)
            
            # Get workflow_id from form or query parameters
            post_workflow_id = request.POST.get('workflow_id') or workflow_id
            
            if not post_workflow_id:
                raise ValueError("Workflow ID is required to create a dynamic field")
            
            workflow = get_object_or_404(ApprovalWorkflow, id=post_workflow_id)
            
            # Create the field
            field = DynamicField(
                name=name,
                field_type=field_type,
                required=required,
                input_width=input_width,
                order=order,
                workflow=workflow
            )
            
            # Handle type-specific properties
            if field_type == 'choice' or field_type == 'multiple_choice':
                field.choices = request.POST.get('choices', '')
            elif field_type == 'number':
                field.min_value = request.POST.get('min_value', None)
                field.max_value = request.POST.get('max_value', None)
            elif field_type == 'attachment':
                field.allowed_extensions = request.POST.get('allowed_extensions', '')
            elif field_type == 'product_list':
                field.product_list_columns = request.POST.get('product_list_columns', '')
            elif field_type == 'table_list':
                field.table_columns = request.POST.get('table_columns', '')
            
            field.save()
            messages.success(request, f'Field "{name}" created successfully!')
            
            # Redirect based on where the request came from
            next_url = request.POST.get('next', 'document_approval:field_list')
            
            # Check if next_url contains a view name and possibly query parameters
            if '&id=' in next_url or '?id=' in next_url:
                # The URL contains both a view name and an ID parameter
                view_name, params = next_url.split('&id=') if '&id=' in next_url else next_url.split('?id=')
                workflow_id = params.split('&')[0]  # Get the ID value
                
                if view_name.startswith('document_approval:'):
                    # Use the correct parameter name based on the URL pattern
                    if 'edit_workflow' in view_name:
                        return redirect(view_name, workflow_id=workflow_id)
                    else:
                        return redirect(view_name, id=workflow_id)
            elif next_url.startswith('document_approval:'):
                # Just a view name without parameters
                return redirect(next_url)
                
            return redirect('document_approval:field_list')
            
        except Exception as e:
            messages.error(request, f'Error creating field: {str(e)}')
    
    return render(request, 'document/dynamic_fields/create_field.html', {
        'field_types': DynamicField.FIELD_TYPES,
        'width_choices': DynamicField.WIDTH_CHOICES
    })

@login_required
def edit_field(request, field_id):
    """Edit an existing dynamic field"""
    field = get_object_or_404(DynamicField, id=field_id)
    
    if request.method == 'POST':
        try:
            # Update basic field data
            field.name = request.POST.get('name')
            field.field_type = request.POST.get('field_type')
            field.required = request.POST.get('required') == 'true'
            field.input_width = request.POST.get('width', 'full')  # Get width from form but use as input_width
            field.order = request.POST.get('order', 0)
            
            # Handle type-specific properties
            if field.field_type == 'choice' or field.field_type == 'multiple_choice':
                field.choices = request.POST.get('choices', '')
            elif field.field_type == 'number':
                field.min_value = request.POST.get('min_value', None)
                field.max_value = request.POST.get('max_value', None)
            elif field.field_type == 'attachment':
                field.allowed_extensions = request.POST.get('allowed_extensions', '')
            elif field.field_type == 'product_list':
                field.product_list_columns = request.POST.get('product_list_columns', '')
            elif field.field_type == 'table_list':
                field.table_columns = request.POST.get('table_columns', '')
            
            field.save()
            messages.success(request, f'Field "{field.name}" updated successfully!')
            return redirect('document_approval:field_list')
            
        except Exception as e:
            messages.error(request, f'Error updating field: {str(e)}')
    
    return render(request, 'document/dynamic_fields/edit_field.html', {
        'field': field,
        'field_types': DynamicField.FIELD_TYPES,
        'width_choices': DynamicField.WIDTH_CHOICES
    })

@login_required
def delete_field(request, field_id):
    """Delete a dynamic field"""
    field = get_object_or_404(DynamicField, id=field_id)
    
    if request.method == 'POST':
        try:
            name = field.name
            field.delete()
            messages.success(request, f'Field "{name}" deleted successfully!')
            return redirect('document_approval:field_list')
        except Exception as e:
            messages.error(request, f'Error deleting field: {str(e)}')
        
        return render(request, 'document/dynamic_fields/delete_field.html', {
            'field': field
        })
    
    return render(request, 'document/dynamic_fields/delete_field.html', {
        'field': field
    })

@login_required
@require_POST
def delete_field_ajax(request, field_id):
    """Delete a dynamic field via AJAX"""
    field = get_object_or_404(DynamicField, id=field_id)
    
    try:
        name = field.name
        field.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Field "{name}" deleted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@require_POST
def edit_field_ajax(request, field_id):
    """Edit a dynamic field via AJAX"""
    field = get_object_or_404(DynamicField, id=field_id)
    
    try:
        data = json.loads(request.body)
        
        # Update basic field data
        field.name = data.get('name', field.name)
        field.field_type = data.get('field_type', field.field_type)
        field.required = data.get('required', field.required)
        field.input_width = data.get('input_width', field.input_width)
        
        # Handle type-specific properties
        if field.field_type == 'choice' or field.field_type == 'multiple_choice':
            field.choices = data.get('choices', field.choices)
        elif field.field_type == 'number':
            field.min_value = data.get('min_value', field.min_value)
            field.max_value = data.get('max_value', field.max_value)
        elif field.field_type == 'attachment':
            field.allowed_extensions = data.get('allowed_extensions', field.allowed_extensions)
        elif field.field_type == 'product_list':
            field.product_list_columns = data.get('product_list_columns', field.product_list_columns)
        elif field.field_type == 'table_list':
            field.table_columns = data.get('table_columns', field.table_columns)
        
        field.save()
        
        # Return detailed field information for DOM updates
        field_data = {
            'id': field.id,
            'name': field.name,
            'field_type': field.field_type,
            'field_type_display': dict(DynamicField.FIELD_TYPES).get(field.field_type, ''),
            'required': field.required,
            'input_width': field.input_width,
            'width_display': dict(DynamicField.WIDTH_CHOICES).get(field.input_width, ''),
            'choices': field.choices,
            'table_columns': field.table_columns,
            'allowed_extensions': field.allowed_extensions,
            'textarea_rows': field.textarea_rows,
            'multiple_files': field.multiple_files
        }
        
        # Add min_value and max_value if they exist
        if hasattr(field, 'min_value'):
            field_data['min_value'] = field.min_value
        if hasattr(field, 'max_value'):
            field_data['max_value'] = field.max_value
        
        return JsonResponse({
            'success': True,
            'message': f'Field "{field.name}" updated successfully!',
            'field': field_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def field_preview(request, field_id=None):
    """Preview a dynamic field"""
    if field_id:
        field = get_object_or_404(DynamicField, id=field_id)
        # Check if this is an embed request
        is_embed = request.GET.get('embed', 'false').lower() == 'true'
        template = 'document/dynamic_fields/field_preview_embed.html' if is_embed else 'document/dynamic_fields/field_preview.html'
        
        response = render(request, template, {
            'field': field
        })
        # Allow this page to be embedded in an iframe from the same origin
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response
    
    # Handle AJAX preview for unsaved field
    if request.method == 'POST':
        field_data = {
            'name': request.POST.get('name', 'Field Preview'),
            'field_type': request.POST.get('field_type', 'text'),
            'required': request.POST.get('required') == 'true',
            'input_width': request.POST.get('width', 'full'),  # Get width from form but use as input_width
            'choices': request.POST.get('choices', ''),
            'min_value': request.POST.get('min_value', None),
            'max_value': request.POST.get('max_value', None),
            'allowed_extensions': request.POST.get('allowed_extensions', ''),
            'product_list_columns': request.POST.get('product_list_columns', ''),
            'table_columns': request.POST.get('table_columns', '')
        }
        
        # Create a temporary field object with the provided data
        temp_field = DynamicField()
        for key, value in field_data.items():
            setattr(temp_field, key, value)
        
        # Add helper methods that the template expects
        temp_field.get_field_type_display = lambda: dict(DynamicField.FIELD_TYPES).get(temp_field.field_type, '')
        temp_field.get_width_display = lambda: dict(DynamicField.WIDTH_CHOICES).get(temp_field.input_width, '')
        
        # Add helper properties for lists
        temp_field.choices_list = temp_field.choices.splitlines() if temp_field.choices else []
        temp_field.table_columns_list = temp_field.table_columns.split('|') if temp_field.table_columns else []
        temp_field.product_list_columns_list = temp_field.product_list_columns.split('|') if temp_field.product_list_columns else []
        
        response = render(request, 'document/dynamic_fields/field_preview_partial.html', {
            'field': temp_field
        })
        # Allow this page to be embedded in an iframe from the same origin
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response
    
    return JsonResponse({'error': 'Invalid request'}, status=400)
