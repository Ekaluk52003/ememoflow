# myapp/validators.py
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class CustomPasswordValidator:
    def validate(self, password, user=None):
        # 1. Check for minimum length of 8
        if len(password) < 8:
            raise ValidationError(
                _("Your password must contain at least 8 characters."),
                code='password_too_short',
            )
            
        # 2. Check for at least one number
        if not re.search(r'\d', password):
            raise ValidationError(
                _("Your password must contain at least one number."),
                code='password_no_number',
            )
            
        # 3. Check for at least one lowercase letter
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("Your password must contain at least one lowercase letter."),
                code='password_no_lower',
            )
            
        # 4. Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("Your password must contain at least one uppercase letter."),
                code='password_no_upper',
            )
            
        # 5. Check for at least one specific special character
        if not re.search(r'[!@#$%&*]', password):
            raise ValidationError(
                _("Your password must contain at least one special character from the following: !@#$%&*"),
                code='password_no_special',
            )

    def get_help_text(self):
        return _(
            "Your password must be at least 8 characters long, and contain at least "
            "one uppercase letter, one lowercase letter, one number, and one special character (!@#$%&*)."
        )