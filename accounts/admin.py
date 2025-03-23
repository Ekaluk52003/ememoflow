from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.fields import Field
from import_export.widgets import ManyToManyWidget, BooleanWidget, ForeignKeyWidget
from import_export.results import RowResult
from allauth.account.models import EmailAddress
from django.db.models import Q
from django.db import transaction

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser

class GroupsWidget(ManyToManyWidget):
    """Widget for displaying groups in preview"""
    def render(self, value, obj=None):
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return super().render(value, obj)
        
    def clean(self, value, row=None, *args, **kwargs):
        """Override clean to prevent trying to convert group names to IDs"""
        if value:
            return value
        return None

class CustomBooleanWidget(BooleanWidget):
    """Custom widget to display boolean values as TRUE or FALSE"""
    TRUE_VALUES = ['True', 'true', 'TRUE', '1', 'Yes', 'yes', 'YES', True]
    FALSE_VALUES = ['False', 'false', 'FALSE', '0', 'No', 'no', 'NO', False]
    
    def render(self, value, obj=None):
        if value in self.TRUE_VALUES:
            return "TRUE"
        if value in self.FALSE_VALUES:
            return "FALSE"
        return str(value)

class CustomUserResource(resources.ModelResource):
    # Define fields including groups as a dehydrated field
    password = Field(column_name='password')
    verify_email = Field(column_name='verify_email', widget=CustomBooleanWidget())
    groups = fields.Field(column_name='groups')
    is_staff = Field(attribute='is_staff', column_name='is_staff', widget=CustomBooleanWidget())
    is_superuser = Field(attribute='is_superuser', column_name='is_superuser', widget=CustomBooleanWidget())
    is_active = Field(attribute='is_active', column_name='is_active', widget=CustomBooleanWidget())
    
    # Store raw values for preview
    _raw_data = {}
    _groups_data = {}
    
    class Meta:
        model = CustomUser
        import_id_fields = ['username', 'email']
        fields = ('username', 'email', 'first_name', 'last_name', 'job_title', 
                 'is_staff', 'is_superuser', 'is_active')
        export_order = ('username', 'email', 'first_name', 'last_name', 'job_title', 
                       'is_staff', 'is_superuser', 'is_active', 'groups', 'verify_email')
        skip_unchanged = False  # Don't skip unchanged rows to ensure they appear in preview
        report_skipped = True   # Report skipped rows

    def before_import_row(self, row, **kwargs):
        # Store raw values for preview in class variable
        key = f"{row.get('username')}:{row.get('email')}"
        self._raw_data[key] = {
            'verify_email': row.get('verify_email', True)
        }
        
        # Store groups separately
        if 'groups' in row:
            self._groups_data[key] = row.get('groups', '')
            
        # Convert string boolean values to actual booleans
        for field in ['is_staff', 'is_superuser', 'is_active', 'verify_email']:
            if field in row:
                if isinstance(row[field], str):
                    row[field] = row[field].lower() in ['true', 'yes', '1']
            elif field == 'verify_email':
                # Default to True if not specified
                row['verify_email'] = True

    def before_import(self, dataset, using_transactions, dry_run, **kwargs):
        """
        Check for email uniqueness before import to prevent duplicate email errors.
        """
        # Call the parent method first
        result = super().before_import(dataset, using_transactions, dry_run, **kwargs)
        
        if not dry_run:
            # Check for duplicate emails in the dataset
            emails = {}
            for i, row in enumerate(dataset.dict):
                email = row.get('email')
                if not email:
                    continue
                    
                if email in emails:
                    # Mark this row as having a duplicate email
                    row['_duplicate_email'] = True
                    dataset.append_col(lambda row: 'ERROR: Duplicate email in import data', header='import_errors')
                else:
                    emails[email] = i
                    
                # Check if email already exists in the database
                # Skip if the username matches (update case)
                username = row.get('username')
                existing_user = CustomUser.objects.filter(email=email).exclude(username=username).first()
                if existing_user:
                    row['_duplicate_email'] = True
                    dataset.append_col(lambda row: f'ERROR: Email already exists for user {existing_user.username}', header='import_errors')
        
        return result

    def import_field(self, field, obj, data, is_m2m=False, **kwargs):
        """
        Override import_field to skip the groups field during initial import
        """
        if field.column_name == 'groups':
            # Skip processing groups field here, we'll handle it in after_import_row
            return
        super().import_field(field, obj, data, is_m2m, **kwargs)

    def for_delete(self, row, instance):
        """
        Returns True if row import should delete instance.
        """
        return False  # Never delete users during import

    def get_instance(self, instance_loader, row):
        """
        Get instance based on import_id_fields.
        """
        # Get the instance using the standard method
        instance = super().get_instance(instance_loader, row)
        
        # If we found an existing instance, store its data for preview
        if instance:
            key = f"{instance.username}:{instance.email}"
            
            # Store existing group data for preview
            if hasattr(instance, 'groups') and instance.groups is not None:
                try:
                    groups_str = ",".join([g.name for g in instance.groups.all()])
                    self._groups_data[key] = groups_str
                except (AttributeError, TypeError):
                    pass
                    
            # Store email verification status
            try:
                email_verified = EmailAddress.objects.filter(
                    user=instance, 
                    email=instance.email, 
                    verified=True
                ).exists()
                self._raw_data[key] = {
                    'verify_email': email_verified
                }
            except:
                pass
                
        return instance

    @transaction.atomic
    def after_import_row(self, row, row_result, **kwargs):
        """Process groups and email verification after row import"""
        # Skip processing if this row has a duplicate email
        if row.get('_duplicate_email'):
            row_result.import_type = RowResult.IMPORT_TYPE_ERROR
            row_result.errors.append('Duplicate email address')
            return
            
        if row_result.import_type == 'new' or row_result.import_type == 'update':
            instance = row_result.object_id
            if not instance:
                return
                
            # Get the user object
            try:
                user = CustomUser.objects.get(pk=instance)
            except CustomUser.DoesNotExist:
                return
                
            # Handle password
            if 'password' in row and row['password']:
                user.set_password(row['password'])
                user.save()
                
            # Handle groups - get from stored data
            key = f"{user.username}:{user.email}"
            if key in self._groups_data and self._groups_data[key]:
                try:
                    groups_str = self._groups_data[key]
                    groups_to_add = []
                    group_names = [name.strip() for name in groups_str.split(',') if name.strip()]
                    
                    for group_name in group_names:
                        try:
                            group = Group.objects.get(name=group_name)
                            groups_to_add.append(group)
                        except Group.DoesNotExist:
                            pass
                    
                    # Clear and add groups
                    user.groups.clear()
                    for group in groups_to_add:
                        user.groups.add(group)
                except Exception as e:
                    row_result.errors.append(f"Error setting groups: {str(e)}")
                    
            # Handle email verification
            verify_email = row.get('verify_email', True)
            if verify_email and user.email:
                try:
                    # First check if this email is already verified for another user
                    existing_email = EmailAddress.objects.filter(
                        email=user.email
                    ).exclude(user=user).first()
                    
                    if existing_email:
                        # Don't create a duplicate verified email
                        row_result.import_type = RowResult.IMPORT_TYPE_ERROR
                        row_result.errors.append(f'Email {user.email} is already verified for another user')
                        return
                        
                    # Now create or update the email address for this user
                    email_address, created = EmailAddress.objects.get_or_create(
                        user=user,
                        email=user.email,
                        defaults={
                            'verified': True,
                            'primary': True
                        }
                    )
                    
                    # If it already existed, update it to be verified
                    if not created:
                        email_address.verified = True
                        email_address.primary = True
                        email_address.save()
                except Exception as e:
                    row_result.errors.append(f"Error setting email verification: {str(e)}")

    def get_export_headers(self):
        """Include groups and verify_email in export headers"""
        headers = super().get_export_headers()
        if 'groups' not in headers:
            headers.append('groups')
        if 'verify_email' not in headers:
            headers.append('verify_email')
        return headers
        
    def dehydrate_groups(self, obj):
        """Custom method to display groups in preview"""
        # Try to get the raw groups value from the class variable
        key = f"{obj.username}:{obj.email}"
        if key in self._groups_data:
            return self._groups_data[key]
        
        # Fallback to getting groups from the object if available
        if obj.pk and hasattr(obj, 'groups') and obj.groups is not None:
            try:
                return ",".join([g.name for g in obj.groups.all()])
            except (AttributeError, TypeError):
                pass
        return ""
        
    def dehydrate_verify_email(self, obj):
        """Custom method to display verify_email in preview"""
        # Try to get the raw verify_email value from the class variable
        key = f"{obj.username}:{obj.email}"
        if key in self._raw_data and 'verify_email' in self._raw_data[key]:
            value = self._raw_data[key]['verify_email']
            if isinstance(value, bool):
                return "TRUE" if value else "FALSE"
            return str(value)
            
        # If we have a saved object, check if it has a verified email
        if obj.pk:
            try:
                email_verified = EmailAddress.objects.filter(
                    user=obj, 
                    email=obj.email, 
                    verified=True
                ).exists()
                return "TRUE" if email_verified else "FALSE"
            except:
                pass
                
        return "TRUE"  # Default value
        
    def dehydrate_is_staff(self, obj):
        return "TRUE" if obj.is_staff else "FALSE"
        
    def dehydrate_is_superuser(self, obj):
        return "TRUE" if obj.is_superuser else "FALSE"
        
    def dehydrate_is_active(self, obj):
        return "TRUE" if obj.is_active else "FALSE"


class CustomUserAdmin(ImportExportModelAdmin, UserAdmin):
    resource_class = CustomUserResource
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('job_title',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('job_title',)}),
    )
    list_display = ['id','email', 'username','job_title', 'is_staff', 'get_groups']
    
    def get_groups(self, obj):
        if obj and obj.pk and hasattr(obj, 'groups') and obj.groups is not None:
            return ", ".join([g.name for g in obj.groups.all()])
        return ""
    get_groups.short_description = 'Group'

admin.site.register(CustomUser, CustomUserAdmin)
