from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
import time
from django.shortcuts import render

class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = "pages/home.html"
    login_url = "account_login"


class AboutPageView(LoginRequiredMixin, TemplateView):
    template_name = "pages/about.html"
    login_url = "account_login"


@login_required(login_url="account_login")
def about(request):
    # Some processing
  
    # Processing End
    if request.htmx:
        return render(request, 'pages/components/about.html')
    else:
        return render(request, 'pages/about_full.html')