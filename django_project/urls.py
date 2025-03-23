from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("document/", include("document.urls")),
    path("accounts/", include("allauth.urls")),
    path("", include("pages.urls")),
    path('hijack/', include('hijack.urls')),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
         path("__reload__/", include("django_browser_reload.urls")),
    ] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


