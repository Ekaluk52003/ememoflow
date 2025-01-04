from django.views.generic import TemplateView
import time
from django.shortcuts import render

class HomePageView(TemplateView):
    template_name = "pages/home.html"


class AboutPageView(TemplateView):
    template_name = "pages/about.html"


def about(request):
    # Some processing
  
    # Processing End
    if request.htmx:
        return render(request, 'pages/components/about.html')
    else:
        return render(request, 'pages/about_full.html')