# annotations_app/urls.py
from . import views
from django.urls import path

app_name = 'annotations_app'

urlpatterns = [
    path('', views.view_folders, name='view_folders'),
    path('upload/', views.upload_zip_view, name='upload_zip'),
    path('folder/<int:folder_id>/annotate/', views.annotate_protein_view, name='annotate_protein'),
    path('annotate/folder/<int:folder_id>/download/', views.download_annotations_csv, name='download_annotations_csv'),
    path('annotate/', views.submit_annotation, name='annotate'),
    path('undo/', views.undo_annotation, name='undo'),
    path('folder/<int:folder_id>/overview/', views.annotation_overview, name='annotation_overview'),
]
