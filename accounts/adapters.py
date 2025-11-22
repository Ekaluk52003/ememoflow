from allauth.account.adapter import DefaultAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect


class NoSignupRedirectAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Disable public signup and redirect to home (or another view).
        """
        raise ImmediateHttpResponse(redirect("home"))
