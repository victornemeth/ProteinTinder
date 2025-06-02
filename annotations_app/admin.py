# annotations_app/admin.py
from django.contrib import admin
from .models import (
    ProteinFolder,
    Protein,
    Annotation,
    DomainCorrection,
    ManualDomainAnnotation,
)

# ───────────────────────────
# Existing registrations
# ───────────────────────────
@admin.register(ProteinFolder)
class ProteinFolderAdmin(admin.ModelAdmin):
    list_display  = ("name", "user", "title", "created_at")
    search_fields = ("name", "title", "description", "user__username")
    list_filter   = ("created_at", "user")
    readonly_fields = ("created_at",)


@admin.register(Protein)
class ProteinAdmin(admin.ModelAdmin):
    list_display  = ("protein_id", "name", "pdb_file_path", "folder")
    search_fields = ("protein_id", "name")
    list_filter   = ("folder",)


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display  = (
        "protein",
        "user",
        "given_annotation",
        "folder",
        "annotation_title",
        "timestamp",
    )
    search_fields = ("protein__protein_id", "user__username", "annotation_title")
    list_filter   = ("given_annotation", "folder", "timestamp", "user")
    readonly_fields = ("timestamp",)

# ───────────────────────────
# NEW: architecture-specific models
# ───────────────────────────
@admin.register(DomainCorrection)
class DomainCorrectionAdmin(admin.ModelAdmin):
    list_display  = (
        "protein",
        "user",
        "domain_name",
        "start_pos",
        "end_pos",
        "is_marked_wrong",
        "timestamp",
    )
    list_filter   = ("is_marked_wrong", "user", "protein__folder")
    search_fields = (
        "protein__protein_id",
        "domain_name",
        "user__username",
    )
    readonly_fields = ("timestamp",)
    ordering = ("-timestamp",)


@admin.register(ManualDomainAnnotation)
class ManualDomainAnnotationAdmin(admin.ModelAdmin):
    list_display  = (
        "protein",
        "user",
        "domain_name",
        "start_pos",
        "end_pos",
        "timestamp",
    )
    list_filter   = ("user", "protein__folder")
    search_fields = (
        "protein__protein_id",
        "domain_name",
        "user__username",
    )
    readonly_fields = ("timestamp",)
    ordering = ("-timestamp",)
