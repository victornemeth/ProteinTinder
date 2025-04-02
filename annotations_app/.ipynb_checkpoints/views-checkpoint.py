# annotations_app/views.py
import os
import json
import zipfile
import tempfile

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt

from .forms import CustomUserCreationForm, PDBZipUploadForm
from .models import ProteinFolder, Protein, Annotation


def redirect_to_annotate(request):
    # Try getting the first folder (can change to newest or user's if needed)
    folder = ProteinFolder.objects.first()

    if folder:
        return redirect('annotations_app:annotate_protein', folder_id=folder.id)
    else:
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

            # Save folder with title/desc
            folder = ProteinFolder.objects.create(
                name=folder_name,
                user=user,
                title=annotation_title,
                description=annotation_description
            )
            safe_folder = slugify(folder_name)

            # Create a temporary directory to extract
            with tempfile.TemporaryDirectory() as tmpdirname:
                zip_path = os.path.join(tmpdirname, zip_file.name)

                # Save uploaded zip temporarily
                with open(zip_path, 'wb+') as temp_file:
                    for chunk in zip_file.chunks():
                        temp_file.write(chunk)

                # Extract the zip
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdirname)

                # Iterate over extracted files
                for root, _, files in os.walk(tmpdirname):
                    for filename in files:
                        if filename.lower().endswith('.pdb'):
                            protein_id, _ = os.path.splitext(filename)
                            protein_id = protein_id.strip().upper()

                            full_path = os.path.join(root, filename)
                            relative_path = f"pdbs/{user.username}/{safe_folder}/{filename}"

                            # Save to media storage
                            with open(full_path, 'rb') as f:
                                default_storage.save(relative_path, f)

                            Protein.objects.create(
                                protein_id=protein_id,
                                pdb_file_path=relative_path,
                                folder=folder
                            )

            return redirect('annotations_app:view_folders')
    else:
        form = PDBZipUploadForm()

    return render(request, 'annotations_app/upload_zip.html', {'form': form})


@login_required
def view_folders(request):
    folders = ProteinFolder.objects.all()  # 🔁 instead of filtering by user
    return render(request, 'annotations_app/folder_list.html', {'folders': folders})


def signup_view(request):
    """Handles user registration."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save() # Creates the user in the database
            # Optional: Log the user in directly after signup
            # login(request, user)
            # Redirect to a success page or login page
            return redirect('login') # Redirect to the login page URL name
            # Or redirect to annotation page: return redirect('annotations_app:annotate_protein')
    else: # GET request
        form = CustomUserCreationForm()

    context = {'form': form}
    return render(request, 'registration/signup.html', context)



@login_required
def annotate_protein_view(request, folder_id=None):
    user = request.user

    # If no folders at all, redirect to upload page
    if ProteinFolder.objects.count() == 0:
        return redirect('annotations_app:upload_zip')

    # If a folder is selected, filter proteins from that folder
    if folder_id:
        proteins_qs = Protein.objects.filter(folder_id=folder_id)
    else:
        return redirect('annotations_app:view_folders')  # Redirect to folder chooser

    # Get already annotated proteins
    annotated_ids = Annotation.objects.filter(user=user).values_list('protein_id', flat=True)
    protein_to_annotate = proteins_qs.exclude(protein_id__in=annotated_ids).first()

    if not protein_to_annotate:
        return redirect('annotations_app:view_folders')

    # Safe folder access
    folder = getattr(protein_to_annotate, 'folder', None)
    context = {
        'protein': protein_to_annotate,
        'media_url': settings.MEDIA_URL,
        'annotation_title': folder.title if folder else "",
        'annotation_description': folder.description if folder else "",
    }

    # Clean up path
    if protein_to_annotate.pdb_file_path:
        for prefix in ['app/media/', '/app/media/']:
            if protein_to_annotate.pdb_file_path.startswith(prefix):
                protein_to_annotate.pdb_file_path = protein_to_annotate.pdb_file_path.replace(prefix, '', 1)

    return render(request, 'annotations_app/annotate.html', context)

@csrf_exempt  # Remove this if you're strictly using CSRF tokens
@login_required
def submit_annotation(request):
    try:
        if request.method == "POST":
            data = json.loads(request.body)
            protein_id = data.get("protein_id")
            direction = data.get("annotation")  # expected: 'right', 'left', or 'down'
            user = request.user

            if not protein_id or not direction:
                return JsonResponse({"error": "Missing data"}, status=400)

            # Map swipe directions to annotation values
            direction_map = {
                "right": "correct",
                "left": "wrong",
                "down": "unsure"
            }

            if direction not in direction_map:
                return JsonResponse({"error": "Invalid annotation direction"}, status=400)

            # Ensure protein exists
            protein = Protein.objects.get(protein_id=protein_id)
            folder = protein.folder
            title = folder.title if folder else ""


            # Save annotation
            Annotation.objects.create(
                protein=protein,
                user=user,
                given_annotation=direction_map[direction],
                folder=folder,
                annotation_title=title
            )


            return JsonResponse({"success": True})

        return JsonResponse({"error": "Invalid request method"}, status=405)

    except Exception as e:
        import traceback, logging
        logger = logging.getLogger(__name__)
        logger.error("Annotation failed:\n%s", traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required
def undo_last_annotation(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        protein_id = data.get('protein_id')
        user = request.user
        try:
            ann = Annotation.objects.filter(protein__protein_id=protein_id, user=user).latest('timestamp')
            ann.delete()
            return JsonResponse({'success': True})
        except Annotation.DoesNotExist:
            return JsonResponse({'error': 'No annotation found to undo'}, status=404)
    return JsonResponse({'error': 'Invalid method'}, status=405)

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Annotation

@require_POST
@login_required
def undo_annotation(request):
    user = request.user
    try:
        last_annotation = Annotation.objects.filter(user=user).latest("timestamp")
        protein = last_annotation.protein
        last_annotation.delete()

        # Return enough data to re-show the protein
        return JsonResponse({
            "success": True,
            "protein_id": protein.protein_id,
            "pdb_file_path": protein.pdb_file_path,
            "name": protein.name,
        })
    except Annotation.DoesNotExist:
        return JsonResponse({"success": False, "error": "No previous annotation found."}, status=404)

