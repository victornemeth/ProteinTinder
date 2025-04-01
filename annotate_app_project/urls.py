# ~/annotate/annotate_app_project/urls.py

from django.contrib import admin
from django.urls import path, include
from annotations_app import views as annotation_views

# === ADD these imports ===
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('annotate/', include('annotations_app.urls', namespace='annotations_app')),
    path('accounts/signup/', annotation_views.signup_view, name='signup'),
    path('accounts/', include('django.contrib.auth.urls')),
]

# === ADD this line at the end for development media serving ===
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
