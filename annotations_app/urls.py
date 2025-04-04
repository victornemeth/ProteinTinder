# annotations_app/urls.py
from . import views
from django.urls import path

app_name = 'annotations_app'

urlpatterns = [
    # Existing URLs
    path('', views.view_folders, name='view_folders'),
    path('upload/', views.upload_zip_view, name='upload_zip'),

    # URL for annotating the *next* available protein in a folder
    path('folder/<int:folder_id>/annotate/', views.annotate_protein_view, name='annotate_protein'),

    # NEW URL: Annotate a *specific* protein within a folder
    path('folder/<int:folder_id>/annotate/<int:protein_pk>/', views.annotate_protein_view, name='annotate_specific_protein'),

    path('folder/<int:folder_id>/redo/', views.redo_folder_view, name='redo_folder'), # Keep this for full reset if desired
    path('folder/<int:folder_id>/download/', views.download_annotations_csv, name='download_annotations_csv'),
    path('annotate/submit/', views.submit_annotation, name='annotate'), # Renamed slightly for clarity if desired, or keep 'annotate'
    path('annotate/undo/', views.undo_annotation, name='undo'), # Renamed slightly for clarity if desired, or keep 'undo'
    path('folder/<int:folder_id>/overview/', views.annotation_overview, name='annotation_overview'),
]
