# annotations_app/urls.py

from django.urls import path
from . import views

app_name = 'annotations_app' # Namespace for URLs

urlpatterns = [
    path('', views.annotate_protein_view, name='annotate_protein'),
    path('annotate/', views.submit_annotation, name='annotate'),  # <-- this is the one you need
    # Add URL for submitting annotations later
]
