
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('llms.txt', TemplateView.as_view(template_name='llms.txt', content_type='text/plain')),
    path('',include('accounts.urls')),
    path('',include('base.urls')),
    path('', include('customer.urls')),
    path('staff/', include('base.staff_urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
