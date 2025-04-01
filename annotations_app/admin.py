# annotations_app/admin.py

from django.contrib import admin
# Import your models from the models.py file in the same directory
from .models import Protein, Annotation

# Register the Protein model with customization (optional but recommended)
@admin.register(Protein)
class ProteinAdmin(admin.ModelAdmin):
    list_display = ('protein_id', 'name', 'pdb_file_path') # Fields to show in the list view
    search_fields = ('protein_id', 'name') # Allow searching by these fields

# Register the Annotation model with customization (optional but recommended)
@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    # Use 'user__username' to display the username from the related User model
    list_display = ('protein', 'user', 'given_annotation', 'timestamp')
    list_filter = ('given_annotation', 'timestamp', 'user') # Filter options in the sidebar
    search_fields = ('protein__protein_id', 'user__username') # Allow searching
    # Make timestamp read-only as it's set automatically
    readonly_fields = ('timestamp',)

# --- OR, the simpler registration (if the above is missing) ---
# If the @admin.register blocks are not there, you MUST have at least these lines:
# admin.site.register(Protein)
# admin.site.register(Annotation)
