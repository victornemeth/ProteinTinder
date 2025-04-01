# annotations_app/urls.py

from django.urls import path
from . import views

app_name = 'annotations_app' # Namespace for URLs

urlpatterns = [
    path('', views.annotate_protein_view, name='annotate_protein'),
    # Add URL for submitting annotations later
]
