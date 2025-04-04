# annotations_app/views.py

import os
import json
import zipfile
import tempfile
import logging
from django.db import IntegrityError
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import CustomUserCreationForm, PDBZipUploadForm
from .models import ProteinFolder, Protein, Annotation

import csv
from django.http import HttpResponse
from collections import defaultdict

def redirect_to_annotate(request):
    folder = ProteinFolder.objects.first()
    if folder:
        return redirect('annotations_app:annotate_protein', folder_id=folder.id)
    return redirect('annotations_app:upload_zip')

@login_required
def upload_zip_view(request):
    if request.method == 'POST':
        form = PDBZipUploadForm(request.POST, request.FILES)
        if form.is_valid():
            folder_name = form.cleaned_data['folder_name']
            annotation_title = form.cleaned_data['annotation_title']
            annotation_description = form.cleaned_data['annotation_description']
            zip_file = request.FILES['zip_file']
            user = request.user

            folder = ProteinFolder.objects.create(
                name=folder_name,
                user=user,
                title=annotation_title,
                description=annotation_description
            )
            safe_folder = slugify(folder_name)

            with tempfile.TemporaryDirectory() as tmpdirname:
                zip_path = os.path.join(tmpdirname, zip_file.name)
                with open(zip_path, 'wb+') as temp_file:
                    for chunk in zip_file.chunks():
                        temp_file.write(chunk)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdirname)
                for root, _, files in os.walk(tmpdirname):
                    for filename in files:
                        if filename.lower().endswith('.pdb'):
                            protein_id, _ = os.path.splitext(filename)
                            protein_id = protein_id.strip().upper()
                            full_path = os.path.join(root, filename)
                            relative_path = f"pdbs/{user.username}/{safe_folder}/{filename}"
                            with open(full_path, 'rb') as f:
                                default_storage.save(relative_path, f)
                            _, created = Protein.objects.get_or_create(
                                protein_id=protein_id,
                                folder=folder,
                                defaults={
                                    'name': protein_id,
                                    'pdb_file_path': relative_path
                                }
                            )
            return redirect('annotations_app:view_folders')
    else:
        form = PDBZipUploadForm()
    return render(request, 'annotations_app/upload_zip.html', {'form': form})

@login_required
def view_folders(request):
    folders = ProteinFolder.objects.all()
    folder_data = []

    for folder in folders:
        total_proteins = folder.proteins.count()
        annotated_count = Annotation.objects.filter(folder=folder, user=request.user).count()
        is_complete = total_proteins > 0 and total_proteins == annotated_count

        folder_data.append({
            'folder': folder,
            'is_complete': is_complete,
        })

    return render(request, 'annotations_app/folder_list.html', {'folder_data': folder_data})


def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def annotate_protein_view(request, folder_id=None):
    user = request.user
    if ProteinFolder.objects.count() == 0:
        return redirect('annotations_app:upload_zip')
    if folder_id:
        proteins_qs = Protein.objects.filter(folder_id=folder_id)
    else:
        return redirect('annotations_app:view_folders')
    annotated_ids = Annotation.objects.filter(user=user).values_list('protein__id', flat=True)
    protein_to_annotate = proteins_qs.exclude(id__in=annotated_ids).first()

    if not protein_to_annotate:
        return redirect('annotations_app:view_folders')
    folder = getattr(protein_to_annotate, 'folder', None)
    context = {
        'protein': protein_to_annotate,
        'media_url': settings.MEDIA_URL,
        'annotation_title': folder.title if folder else "",
        'annotation_description': folder.description if folder else "",
    }
    if protein_to_annotate.pdb_file_path:
        for prefix in ['app/media/', '/app/media/']:
            if protein_to_annotate.pdb_file_path.startswith(prefix):
                protein_to_annotate.pdb_file_path = protein_to_annotate.pdb_file_path.replace(prefix, '', 1)
    return render(request, 'annotations_app/annotate.html', context)

@csrf_exempt
@login_required
def submit_annotation(request):
    try:
        if request.method == "POST":
            data = json.loads(request.body)
            protein_id = data.get("protein_id")
            folder_id = data.get("folder_id")
            direction = data.get("annotation")
            user = request.user

            if not protein_id or not direction or not folder_id:
                return JsonResponse({"error": "Missing data"}, status=400)

            direction_map = {
                "right": "correct",
                "left": "wrong",
                "down": "unsure"
            }

            if direction not in direction_map:
                return JsonResponse({"error": "Invalid annotation direction"}, status=400)

            # Get protein scoped by folder
            protein = Protein.objects.get(protein_id=protein_id, folder_id=folder_id)
            folder = protein.folder
            title = folder.title if folder else ""

            # Create or update annotation
            Annotation.objects.update_or_create(
                protein=protein,
                user=user,
                defaults={
                    "folder": folder,
                    "annotation_title": title,
                    "given_annotation": direction_map[direction]
                }
            )

            return JsonResponse({"success": True})

        return JsonResponse({"error": "Invalid request method"}, status=405)

    except Protein.DoesNotExist:
        return JsonResponse({"error": "Protein not found"}, status=404)
    except Protein.MultipleObjectsReturned:
        return JsonResponse({"error": "Multiple proteins found with same ID — specify folder"}, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Annotation failed:\n%s", e, exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)



@login_required
def download_annotations_csv(request, folder_id):
    folder = get_object_or_404(ProteinFolder, id=folder_id)
    annotations = Annotation.objects.filter(folder=folder).select_related('user', 'protein')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="annotations_{folder.name}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Username', 'Protein ID', 'Annotation', 'Timestamp'])

    for annotation in annotations:
        writer.writerow([
            annotation.user.username,
            annotation.protein.protein_id,
            annotation.get_given_annotation_display(),
            annotation.timestamp
        ])

    return response


@require_POST
@login_required
def undo_annotation(request):
    user = request.user
    try:
        last_annotation = Annotation.objects.filter(user=user).latest("timestamp")
        protein = last_annotation.protein
        last_annotation.delete()
        return JsonResponse({
            "success": True,
            "protein_id": protein.protein_id,
            "pdb_file_path": protein.pdb_file_path,
            "name": protein.name,
        })
    except Annotation.DoesNotExist:
        return JsonResponse({"success": False, "error": "No previous annotation found."}, status=404)

@login_required
def annotation_overview(request, folder_id):
    folder = get_object_or_404(ProteinFolder, id=folder_id)
    annotations = Annotation.objects.filter(folder=folder, user=request.user).select_related('protein')

    grouped = defaultdict(list)
    for ann in annotations:
        protein = ann.protein
        # Strip off any '/app/media/' prefix if present (like in annotate_protein_view)
        for prefix in ['app/media/', '/app/media/']:
            if protein.pdb_file_path and protein.pdb_file_path.startswith(prefix):
                protein.pdb_file_path = protein.pdb_file_path.replace(prefix, '', 1)
        grouped[ann.given_annotation].append(protein)

    return render(request, 'annotations_app/annotation_overview.html', {
        'folder': folder,
        'grouped_annotations': dict(grouped),
        'media_url': settings.MEDIA_URL
    })
