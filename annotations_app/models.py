# annotations_app/models.py

from django.db import models
from django.conf import settings # To link to the User model

class Protein(models.Model):
    """Represents a 3D protein structure."""
    protein_id = models.CharField(max_length=50, unique=True, primary_key=True) # e.g., PDB ID like '6VXX'
    name = models.CharField(max_length=255, blank=True, null=True)
    # Add other relevant fields if needed, e.g., source, description
    # You might store the PDB file path/URL here or just the ID
    pdb_file_path = models.CharField(max_length=500, blank=True, null=True) # Or models.FileField if storing locally

    def __str__(self):
        return self.protein_id

class Annotation(models.Model):
    """Stores a user's annotation for a specific protein."""
    ANNOTATION_CHOICES = [
        ('correct', 'Correct'),
        ('wrong', 'Wrong'),
        ('unsure', 'Unsure'),
    ]

    protein = models.ForeignKey(Protein, on_delete=models.CASCADE, related_name='annotations')
    # Use settings.AUTH_USER_MODEL to refer to the user model (best practice)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='annotations')
    # Storing user_name is redundant if you have the user foreign key,
    # but if required by specs:
    # user_name = models.CharField(max_length=150) # Match User model's username length
    given_annotation = models.CharField(max_length=10, choices=ANNOTATION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True) # Record when annotation was made

    class Meta:
        # Ensure a user can only annotate a specific protein once (optional, depends on requirements)
        unique_together = ('protein', 'user')
        ordering = ['-timestamp'] # Show newest annotations first by default

    def __str__(self):
        # Use user.username if using the ForeignKey directly
        return f"{self.user.username} - {self.protein.protein_id}: {self.get_given_annotation_display()}"
        # If storing user_name separately:
        # return f"{self.user_name} - {self.protein.protein_id}: {self.get_given_annotation_display()}"
