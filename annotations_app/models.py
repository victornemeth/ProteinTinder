# annotations_app/models.py

from django.db import models
from django.conf import settings  # To link to the User model
import os

class ProteinFolder(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="")
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Protein(models.Model):
    """ Represents a single protein structure within a folder. """
    protein_id = models.CharField(max_length=100, db_index=True, help_text="Unique identifier for the protein (e.g., filename base).")
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Optional display name.")
    # Stores path relative to MEDIA_ROOT or storage root
    pdb_file_path = models.CharField(max_length=500, blank=True, null=True, help_text="Path to the PDB file within storage.")
    # Stores path relative to MEDIA_ROOT or storage root
    domain_csv_path = models.CharField(max_length=500, blank=True, null=True, help_text="Path to the domain CSV file within storage, if available.")
    folder = models.ForeignKey(ProteinFolder, on_delete=models.CASCADE, related_name='proteins')

    class Meta:
        # Ensures a protein ID is unique within a specific folder
        unique_together = ('protein_id', 'folder')
        ordering = ['protein_id'] # Consistent ordering within a folder

    def __str__(self):
        return f"{self.protein_id} (Folder: {self.folder.name})"

    @property
    def pdb_filename(self):
        """ Helper property to get just the PDB filename. """
        return os.path.basename(self.pdb_file_path) if self.pdb_file_path else None

    @property
    def has_domain_data(self):
        """ Checks if domain data path exists and the file is accessible in storage. """
        # Avoid import at top level if default_storage might not be configured during model loading phase
        from django.core.files.storage import default_storage
        try:
            # Check both that the path exists in DB and the file exists in storage
            return bool(self.domain_csv_path and default_storage.exists(self.domain_csv_path))
        except Exception:
            # Handle potential storage backend errors during exists() check
            logger = logging.getLogger(__name__) # Get logger locally
            logger.warning(f"Storage backend error checking existence for {self.domain_csv_path}", exc_info=True)
            return False



class Annotation(models.Model):
    ANNOTATION_CHOICES = [
        ('correct', 'Correct'),
        ('wrong', 'Wrong'),
        ('unsure', 'Unsure'),
    ]

    protein = models.ForeignKey(Protein, on_delete=models.CASCADE, related_name='annotations')
    folder = models.ForeignKey(ProteinFolder, on_delete=models.CASCADE, null=True, blank=True)
    annotation_title = models.CharField(max_length=255, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='annotations')
    given_annotation = models.CharField(max_length=10, choices=ANNOTATION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('protein', 'user')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.protein.protein_id}: {self.get_given_annotation_display()}"

class DomainCorrection(models.Model):
    """ Records when a user marks a specific domain annotation as incorrect. """
    protein = models.ForeignKey(Protein, on_delete=models.CASCADE, related_name='domain_corrections')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='domain_corrections')
    # Store enough info from the CSV to identify the domain
    domain_name = models.CharField(max_length=100)
    start_pos = models.IntegerField()
    end_pos = models.IntegerField()
    is_marked_wrong = models.BooleanField(default=True) # Field indicating the action
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        # Prevent multiple identical corrections by the same user for the same domain
        unique_together = ('protein', 'user', 'domain_name', 'start_pos', 'end_pos')
        ordering = ['timestamp'] # Default order: oldest first

    def __str__(self):
        return f"Domain Correction by {self.user.username} on {self.protein.protein_id}: Domain '{self.domain_name}' ({self.start_pos}-{self.end_pos})"

class ManualDomainAnnotation(models.Model):
    protein = models.ForeignKey(Protein, on_delete=models.CASCADE, related_name='manual_domain_annotations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='manual_domain_annotations')
    domain_name = models.CharField(max_length=100)
    start_pos = models.IntegerField()
    end_pos = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('protein', 'user', 'domain_name', 'start_pos', 'end_pos')
        ordering = ['start_pos']

    def __str__(self):
        return f"{self.user.username} - {self.protein.protein_id}: {self.domain_name} ({self.start_pos}-{self.end_pos})"
