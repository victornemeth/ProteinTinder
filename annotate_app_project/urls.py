# ~/annotate/annotate_app_project/urls.py

from django.contrib import admin
from django.urls import path, include
from annotations_app import views as annotation_views

# === ADD these imports ===
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # REMOVE or COMMENT OUT this redirect line:
    # path('', annotation_views.redirect_to_annotate, name='home_redirect'),

    # CHANGE the prefix for your app's URLs from 'annotate/' to '':
    path('', include('annotations_app.urls', namespace='annotations_app')), # <<< CHANGE IS HERE

    path('admin/', admin.site.urls),
    # REMOVE the old path that included 'annotate/' prefix:
    # path('annotate/', include('annotations_app.urls', namespace='annotations_app')), # <<< REMOVE THIS LINE

    # Keep accounts URLs
    path('accounts/signup/', annotation_views.signup_view, name='signup'),
    path('accounts/', include('django.contrib.auth.urls')),
]

# Keep media URL config for development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
