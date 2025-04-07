# annotations_app/models.py

from django.db import models
from django.conf import settings  # To link to the User model

class ProteinFolder(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="")
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class Protein(models.Model):
    protein_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255, blank=True, null=True)
    pdb_file_path = models.CharField(max_length=500, blank=True, null=True)
    folder = models.ForeignKey(ProteinFolder, on_delete=models.CASCADE, related_name='proteins')

    class Meta:
        unique_together = ('protein_id', 'folder')

    def __str__(self):
        return f"{self.protein_id} in {self.folder.name}"


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
