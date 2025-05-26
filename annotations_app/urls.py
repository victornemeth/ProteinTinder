# annotations_app/urls.py
from . import views
from django.urls import path

app_name = 'annotations_app'

urlpatterns = [
    # --- Core Views ---
    path('', views.view_folders, name='view_folders'),
    path('upload/', views.upload_zip_view, name='upload_zip'),
    path('folder/<int:folder_id>/overview/', views.annotation_overview, name='annotation_overview'),

    # --- Annotation Entry Points ---
    # Determines which template (annotate.html or architecture.html) to show
    path('folder/<int:folder_id>/annotate/', views.annotate_protein_view, name='annotate_protein'),
    path('folder/<int:folder_id>/annotate/<int:protein_pk>/', views.annotate_protein_view, name='annotate_specific_protein'),

    # --- Submission Endpoints ---
    # For standard swipe annotation (from annotate.html)
    path('annotate/submit/', views.submit_annotation, name='annotate'),
    # NEW: For domain corrections (from architecture.html)
    path('annotate/submit_domain_correction/', views.submit_domain_correction, name='submit_domain_correction'),

    # --- Action Endpoints ---
    # For undoing standard swipe annotation (from annotate.html)
    path('annotate/undo/', views.undo_annotation, name='undo'),
    # path('annotate/undo_domain_correction/', views.undo_domain_correction, name='undo_domain_correction'), # Add later if needed

    # --- Folder Actions ---
    path('folder/<int:folder_id>/redo/', views.redo_folder_view, name='redo_folder'),
    path('folder/<int:folder_id>/download/', views.download_annotations_csv, name='download_annotations_csv'),

    # --- Redirects/Helpers ---
    path("annotate/", views.redirect_to_annotate, name="redirect_to_annotate"), # Redirects to first available folder/protein

    path('folder/<int:folder_id>/architecture-overview/', views.architecture_annotation_overview, name='architecture_annotation_overview'),

    path('folder/<int:folder_id>/download_domain_corrections/', views.download_domain_corrections_csv, name='download_domain_corrections_csv'),

    path('delete-folder/<int:folder_id>/', views.delete_folder, name='delete_folder'),
    path('download_folder_zip/<int:folder_id>/', views.download_pdb_folder_zip, name='download_folder_zip'),


]