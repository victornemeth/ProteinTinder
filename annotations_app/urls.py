# annotations_app/urls.py
from . import views
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static


app_name = 'annotations_app'

urlpatterns = [
    # --- Core Views ---
    path('', views.home, name='home'),
    path('folder_list', views.view_folders, name='view_folders'),
    
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
    path('annotate/undo/', views.undo_last, name='undo'),
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

    path('manual/annotate/', views.manual_annotate_protein_view, name='manual_annotate_protein'),
    path('annotate/submit_manual_domains/', views.submit_manual_domains, name='submit_manual_domains'),

    path(
        'folder/<int:folder_id>/manual_annotate/',
        views.manual_annotate_folder_view,
        name='manual_annotate_folder'
    ),
    path(
        'folder/<int:folder_id>/manual_annotate/<int:protein_pk>/',
        views.manual_annotate_folder_view,
        name='manual_annotate_specific'
    ),
    path(
        "folder/<int:folder_id>/domain-overview/",
        views.domain_annotation_overview,
        name="domain_annotation_overview",
    ),
    path(
        "folder/<int:folder_id>/domain-annotations.zip",
        views.domain_annotation_download,
        name="domain_annotation_download",
    ),
    path("undo/manual/", views.undo_last_manual_domain, name="undo_manual_domain"),
    path("manual/skip/", views.skip_manual_domain, name="skip_manual_domain"),
    path('about/', views.about_view, name='about'),

]

# Keep media URL config for development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)