# annotations_app/views.py

import os
import json
import zipfile
import tempfile
import logging
import io # Required for reading CSV from storage
from io import BytesIO
from datetime import datetime

from django.db import IntegrityError, transaction # Import transaction
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import JsonResponse, Http404 # Import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone # <<<< ADD THIS LINE
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie # Import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.contrib import messages

from .forms import CustomUserCreationForm, PDBZipUploadForm
# Import DomainCorrection model
from .models import ProteinFolder, Protein, Annotation, DomainCorrection, ManualDomainAnnotation
from django.db.models import Exists, OuterRef
from django.urls import reverse

import csv
from django.http import HttpResponse
from collections import defaultdict
from django.utils.encoding import smart_str  # To ensure UTF-8 strings
from django.contrib.auth import get_user_model
from django.db.models import Prefetch                   # NEW

from .utils import extract_pdb_sequence

logger = logging.getLogger(__name__)




@login_required
def download_pdb_folder_zip(request, folder_id):
    folder = get_object_or_404(ProteinFolder, id=folder_id)
    proteins = Protein.objects.filter(folder=folder).exclude(pdb_file_path__isnull=True)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for protein in proteins:
            try:
                # Add PDB file
                pdb_path = default_storage.path(protein.pdb_file_path)
                with open(pdb_path, 'rb') as pdb_file:
                    pdb_filename = f"{protein.protein_id}.pdb"
                    zip_file.writestr(pdb_filename, pdb_file.read())

                # Optionally add CSV if exists
                if protein.domain_csv_path:
                    csv_path = default_storage.path(protein.domain_csv_path)
                    with open(csv_path, 'rb') as csv_file:
                        csv_filename = f"{protein.protein_id}.csv"
                        zip_file.writestr(csv_filename, csv_file.read())
            except Exception as e:
                logger.warning(f"Failed to add files for {protein.protein_id}: {e}")

    zip_buffer.seek(0)
    filename = slugify(folder.name) + "_pdbs_and_csvs.zip"
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# --- Helper Function for CSV Parsing ---
def parse_domain_csv(protein):
    """Reads and parses the domain CSV file associated with a protein."""
    if not protein.domain_csv_path:
        return None, "No CSV path defined for this protein."

    try:
        if not default_storage.exists(protein.domain_csv_path):
             return None, f"CSV file not found at path: {protein.domain_csv_path}"

        with default_storage.open(protein.domain_csv_path, mode='rb') as binary_file:
            csv_text_stream = io.TextIOWrapper(binary_file, encoding='utf-8')
            reader = csv.DictReader(csv_text_stream)
            domains = []

            # --- Define required columns based on ACTUAL headers ---
            # Using the names shown in the error message and your 'cat' output
            required_columns = ['Predicted Domain', 'Start Residue', 'End Residue']

            if not reader.fieldnames or not all(col in reader.fieldnames for col in required_columns):
                missing = [col for col in required_columns if not reader.fieldnames or col not in reader.fieldnames]
                found_cols = ', '.join(reader.fieldnames) if reader.fieldnames else 'None'
                csv_text_stream.close() # Close stream before returning
                return None, f"CSV missing required columns: {', '.join(missing)}. Found headers: {found_cols}"

            for i, row in enumerate(reader):
                try:
                    # --- Use ACTUAL header names to access data ---
                    start_pos_str = row.get('Start Residue')
                    end_pos_str = row.get('End Residue')
                    domain_name = row.get('Predicted Domain', '').strip() # Use .get for safety

                    # Check if essential values are missing/empty in the row
                    if start_pos_str is None or end_pos_str is None or not domain_name:
                        logger.warning(f"Skipping row {i+1} in {protein.domain_csv_path} due to missing values. Row: {row}")
                        continue

                    start_pos = int(start_pos_str)
                    end_pos = int(end_pos_str)
                    # --- End of using ACTUAL header names ---

                    if not domain_name: # Double check after strip
                        logger.warning(f"Skipping row {i+1} in {protein.domain_csv_path} due to empty domain name after strip. Row: {row}")
                        continue

                    domains.append({
                        'id': f"domain_{i}",
                        'name': domain_name,
                        'start': start_pos,
                        'end': end_pos
                    })
                except (ValueError, KeyError, TypeError) as e: # Catch potential int conversion errors too
                    logger.warning(f"Skipping row {i+1} in {protein.domain_csv_path} due to parsing error: {e}. Row: {row}")
                    continue

            return domains, None

    except UnicodeDecodeError:
         logger.error(f"Encoding error reading CSV {protein.domain_csv_path}. Ensure it is UTF-8.", exc_info=True)
         return None, f"CSV file encoding issue. Ensure it's UTF-8 encoded."
    except Exception as e:
        logger.error(f"Error reading or parsing CSV {protein.domain_csv_path} for protein {protein.protein_id}: {e}", exc_info=True)
        error_msg = f"Server error reading CSV file: {e}"
        return None, error_msg


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
            # Get the value of the new checkbox
            is_architecture_upload = form.cleaned_data['is_architecture_annotation']
            user = request.user

            # Create the folder instance first
            folder = ProteinFolder.objects.create(
                name=folder_name,
                user=user,
                title=annotation_title,
                description=annotation_description
            )
            safe_folder = slugify(folder_name)
            # Define base storage path for this upload
            base_storage_path = f"pdbs/{user.username}/{safe_folder}"

            try:
                with tempfile.TemporaryDirectory() as tmpdirname:
                    zip_path = os.path.join(tmpdirname, zip_file.name)
                    # Save uploaded zip to temp dir
                    with open(zip_path, 'wb+') as temp_file:
                        for chunk in zip_file.chunks():
                            temp_file.write(chunk)

                    # --- Extract and Process Files ---
                    pdb_files_map = {} # Store {pdb_basename: full_temp_path}
                    csv_files_map = {} # Store {csv_basename: full_temp_path}
                    all_files_in_zip = [] # Keep track of all files extracted

                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            all_files_in_zip = zip_ref.namelist()
                            zip_ref.extractall(tmpdirname)
                    except zipfile.BadZipFile:
                        messages.error(request, "Invalid ZIP file.")
                        folder.delete() # Clean up the created folder object
                        return render(request, 'annotations_app/upload_zip.html', {'form': form})
                    except Exception as e:
                        logger.error(f"Error extracting ZIP file: {e}", exc_info=True)
                        messages.error(request, f"Error extracting ZIP file: {e}")
                        folder.delete() # Clean up
                        return render(request, 'annotations_app/upload_zip.html', {'form': form})


                    # --- Find all PDB and CSV files within the extracted structure ---
                    for root, _, files in os.walk(tmpdirname):
                        for filename in files:
                            full_temp_path = os.path.join(root, filename)
                            base, ext = os.path.splitext(filename)
                            ext_lower = ext.lower()

                            if ext_lower == '.pdb':
                                # Use uppercase basename consistent with Protein model protein_id?
                                # Let's keep original case for map key, normalize later if needed
                                pdb_files_map[base] = full_temp_path
                            elif ext_lower == '.csv':
                                csv_files_map[base] = full_temp_path

                    if not pdb_files_map:
                        messages.warning(request, "No PDB files (.pdb) found in the uploaded ZIP.")
                        folder.delete() # Clean up
                        return render(request, 'annotations_app/upload_zip.html', {'form': form})


                    proteins_to_create = [] # List to store protein data before bulk creation

                    # --- Validation and Preparation based on annotation type ---
                    if is_architecture_upload:
                        # Validate that every PDB has a corresponding CSV
                        missing_csvs = []
                        for pdb_base in pdb_files_map.keys():
                            if pdb_base not in csv_files_map:
                                missing_csvs.append(f"{pdb_base}.pdb")

                        if missing_csvs:
                            error_msg = "Architecture annotation requires a matching .csv file for every .pdb file. Missing CSVs for: " + ", ".join(missing_csvs)
                            messages.error(request, error_msg)
                            folder.delete() # Clean up
                            return render(request, 'annotations_app/upload_zip.html', {'form': form})

                        # Prepare protein data including CSV paths
                        for pdb_base, pdb_temp_path in pdb_files_map.items():
                            protein_id = pdb_base.strip().upper() # Consistent ID
                            pdb_filename = os.path.basename(pdb_temp_path)
                            csv_temp_path = csv_files_map[pdb_base]
                            csv_filename = os.path.basename(csv_temp_path)

                            relative_pdb_path = f"{base_storage_path}/{pdb_filename}"
                            relative_csv_path = f"{base_storage_path}/{csv_filename}" # Store in the same dir

                            proteins_to_create.append({
                                'protein_id': protein_id,
                                'name': protein_id, # Default name to protein_id
                                'folder': folder,
                                'pdb_temp_path': pdb_temp_path,
                                'csv_temp_path': csv_temp_path,
                                'pdb_file_path': relative_pdb_path,
                                'domain_csv_path': relative_csv_path,
                            })

                    else: # Standard PDB annotation
                        for pdb_base, pdb_temp_path in pdb_files_map.items():
                            protein_id = pdb_base.strip().upper()
                            pdb_filename = os.path.basename(pdb_temp_path)
                            relative_pdb_path = f"{base_storage_path}/{pdb_filename}"

                            proteins_to_create.append({
                                'protein_id': protein_id,
                                'name': protein_id,
                                'folder': folder,
                                'pdb_temp_path': pdb_temp_path,
                                'csv_temp_path': None, # No CSV
                                'pdb_file_path': relative_pdb_path,
                                'domain_csv_path': None, # No CSV path
                            })

                    # --- Save files to storage and create Protein objects ---
                    created_proteins = 0
                    skipped_duplicates = 0
                    for protein_data in proteins_to_create:
                        # Save PDB file
                        with open(protein_data['pdb_temp_path'], 'rb') as f_pdb:
                            try:
                                default_storage.save(protein_data['pdb_file_path'], f_pdb)
                            except Exception as e:
                                logger.error(f"Error saving PDB file {protein_data['pdb_file_path']}: {e}", exc_info=True)
                                messages.error(request, f"Failed to save PDB file for {protein_data['protein_id']}. Aborting upload.")
                                folder.delete() # Clean up folder if critical error
                                # Optionally: Delete already saved files/proteins if possible
                                return render(request, 'annotations_app/upload_zip.html', {'form': form})


                        # Save CSV file if it exists
                        if protein_data['csv_temp_path']:
                            with open(protein_data['csv_temp_path'], 'rb') as f_csv: # Read CSV as binary for storage
                                try:
                                    default_storage.save(protein_data['domain_csv_path'], f_csv)
                                except Exception as e:
                                    logger.error(f"Error saving CSV file {protein_data['domain_csv_path']}: {e}", exc_info=True)
                                    messages.error(request, f"Failed to save CSV file for {protein_data['protein_id']}. Associated PDB was saved, but CSV failed.")
                                    # Decide how to proceed: continue? abort? For now, log and continue but without CSV path in DB
                                    protein_data['domain_csv_path'] = None # Don't save CSV path if file saving failed


                        # Create Protein DB entry
                        try:
                            Protein.objects.create(
                                protein_id=protein_data['protein_id'],
                                name=protein_data['name'],
                                folder=protein_data['folder'],
                                pdb_file_path=protein_data['pdb_file_path'],
                                domain_csv_path=protein_data['domain_csv_path']
                            )
                            created_proteins += 1
                        except IntegrityError:
                            # Handle case where protein_id + folder combination already exists (e.g., re-upload)
                            logger.warning(f"Protein '{protein_data['protein_id']}' already exists in folder '{folder.name}'. Skipping.")
                            skipped_duplicates += 1
                            # Optional: Delete the just-uploaded files for the duplicate if you want strict behavior
                            # default_storage.delete(protein_data['pdb_file_path'])
                            # if protein_data['domain_csv_path']: default_storage.delete(protein_data['domain_csv_path'])
                        except Exception as e:
                             logger.error(f"Error creating Protein record for {protein_data['protein_id']}: {e}", exc_info=True)
                             messages.error(request, f"Database error creating record for {protein_data['protein_id']}. Files might be saved, but DB entry failed.")
                             # More robust cleanup might be needed here depending on requirements


                    # --- Post-processing messages ---
                    if created_proteins > 0:
                         messages.success(request, f"Successfully uploaded and processed {created_proteins} protein(s) for folder '{folder.name}'.")
                    if skipped_duplicates > 0:
                         messages.warning(request, f"Skipped {skipped_duplicates} duplicate protein(s) already present in the folder.")
                    if created_proteins == 0 and skipped_duplicates == 0:
                         # This case might happen if validation failed earlier but wasn't caught, or other edge cases
                         messages.warning(request, "No new proteins were added. Check the ZIP contents or previous uploads.")


                    return redirect('annotations_app:view_folders')

            except Exception as e:
                # Catch broader exceptions during file handling/processing
                logger.error(f"An unexpected error occurred during upload for folder '{folder_name}': {e}", exc_info=True)
                messages.error(request, f"An unexpected error occurred: {e}. Please try again.")
                if 'folder' in locals() and folder.pk:
                     folder.delete() # Attempt cleanup if folder object exists
                return render(request, 'annotations_app/upload_zip.html', {'form': form})

    else: # GET request
        form = PDBZipUploadForm()
    return render(request, 'annotations_app/upload_zip.html', {'form': form})


from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef
from django.shortcuts import render

@login_required
def view_folders(request):
    """
    Show folders, ordered so that “my” folders come first, architecture before
    structure-only, and alphabetically.  By default only your folders are shown;
    if ?show_all=1 is passed, show everyone's.
    """
    # ←—— NEW: decide whether to show all or only the user's
    show_all = request.GET.get("show_all") == "1"

    base_qs = ProteinFolder.objects.all().annotate(
        has_architecture_data=Exists(
            Protein.objects.filter(
                folder=OuterRef("pk"),
                domain_csv_path__isnull=False,
            )
        )
    )
    if not show_all:
        base_qs = base_qs.filter(user=request.user)

    folder_data = []
    for folder in base_qs:
        total_proteins = folder.proteins.count()
        annotated_count = Annotation.objects.filter(
            folder=folder, user=request.user
        ).count()
        is_complete = total_proteins > 0 and total_proteins == annotated_count
        folder_data.append({
            "folder": folder,
            "is_architecture": folder.has_architecture_data,
            "is_complete": is_complete,
            "total_proteins": total_proteins,
            "annotated_count": annotated_count,
        })

    # sort as before
    folder_data.sort(
        key=lambda d: (
            d["folder"].user != request.user,
            not d["is_architecture"],
            d["folder"].name.lower(),
        )
    )

    return render(request, "annotations_app/folder_list.html", {
        "folder_data": folder_data,
        "users": get_user_model().objects.all(),
        "show_all": show_all,         # ←—— pass flag into template
    })


def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

# --- Annotation Routing View ---
@login_required
@ensure_csrf_cookie # Ensure CSRF cookie is set for AJAX POSTs
def annotate_protein_view(request, folder_id, protein_pk=None):
    user = request.user
    folder = get_object_or_404(ProteinFolder, id=folder_id)
    proteins_qs = Protein.objects.filter(folder=folder).order_by('protein_id')

    protein_to_annotate = None
    is_specific_redo = False

    if protein_pk:
        protein_to_annotate = get_object_or_404(Protein, pk=protein_pk, folder=folder)
        is_specific_redo = True
        messages.info(request, f"Re-annotating specific protein: {protein_to_annotate.protein_id}")
    else:
        # Find the next protein that does NOT have a standard Annotation record by this user
        if not proteins_qs.exists():
            messages.warning(request, f"Folder '{folder.name}' contains no proteins.")
            return redirect('annotations_app:view_folders')

        # Get IDs of proteins already annotated by this user in this folder
        annotated_protein_pks = Annotation.objects.filter(
            user=user,
            folder=folder
        ).values_list('protein_id', flat=True) # Use protein_id (PK)

        protein_to_annotate = proteins_qs.exclude(pk__in=annotated_protein_pks).first()

        if not protein_to_annotate:
            messages.info(request, f"You have completed annotating all proteins in folder '{folder.name}'.")
            return redirect('annotations_app:annotation_overview', folder_id=folder.id)

    if not protein_to_annotate:
         messages.error(request, "Could not find a protein to annotate.")
         return redirect('annotations_app:view_folders')

    # --- Check if it has architecture data ---
    is_architecture = bool(protein_to_annotate.domain_csv_path)
    domain_data = None
    csv_error = None

    # --- Prepare base context ---
    context = {
        'protein': protein_to_annotate,
        'media_url': settings.MEDIA_URL,
        'annotation_title': folder.title,
        'annotation_description': folder.description,
        'folder': folder,
        'folder_id': folder.id,
        'is_specific_redo': is_specific_redo,
         # Add pdb_url and cleaned_pdb_path (relative)
        'pdb_url': None,
        'cleaned_pdb_path': None,
    }

    # --- Add PDB path/URL to context ---
    if protein_to_annotate.pdb_file_path:
        try:
            context['pdb_url'] = default_storage.url(protein_to_annotate.pdb_file_path)
            base_media_path = os.path.join(settings.MEDIA_ROOT, '')
            pdb_full_path = default_storage.path(protein_to_annotate.pdb_file_path)
            relative_path = os.path.relpath(pdb_full_path, base_media_path)
            context['cleaned_pdb_path'] = relative_path.replace(os.path.sep, '/')
        except Exception as e:
             logger.error(f"Error processing PDB path '{protein_to_annotate.pdb_file_path}': {e}")
             messages.error(request, "Error finding the PDB file path.")
             # Keep paths as None in context

    # --- Process based on type ---
    if is_architecture:
        domain_data, csv_error = parse_domain_csv(protein_to_annotate)
    
        # 🔽 Add this to include user's marked corrections
        marked_wrong_domains = DomainCorrection.objects.filter(
            user=user,
            protein=protein_to_annotate,
            is_marked_wrong=True
        ).values('domain_name', 'start_pos', 'end_pos')
    
        context['domain_data'] = domain_data
        context['marked_wrong_data'] = list({
            "name": d["domain_name"],
            "start": d["start_pos"],
            "end": d["end_pos"]
        } for d in marked_wrong_domains)



        context['csv_error'] = csv_error
        template_name = 'annotations_app/architecture.html'

    else:
        # No specific context needed for standard annotation beyond base context
        template_name = 'annotations_app/annotate.html'

    return render(request, template_name, context)



@login_required
@require_POST
# No CSRF exempt needed if token is sent correctly via JS
def submit_annotation(request):
    """ Handles standard Correct/Wrong/Unsure submissions from annotate.html """
    try:
        data = json.loads(request.body)
        protein_id = data.get("protein_id") # Use protein_id from JS
        protein_pk = data.get("protein_pk") # Or PK if available
        folder_id = data.get("folder_id")
        direction = data.get("annotation") # 'left', 'right', 'down'
        user = request.user

        required_fields = {'folder_id': folder_id, 'annotation': direction}
        if not (protein_id or protein_pk):
             required_fields['protein_id_or_pk'] = None # Indicate missing protein identifier

        missing = [k for k, v in required_fields.items() if v is None]
        if missing:
             return JsonResponse({"error": f"Missing data: {', '.join(missing)}"}, status=400)


        direction_map = { "right": "correct", "left": "wrong", "down": "unsure" }
        if direction not in direction_map:
            return JsonResponse({"error": "Invalid annotation direction"}, status=400)

        # --- Find Protein ---
        try:
             # Prioritize PK if provided
             if protein_pk:
                 protein = Protein.objects.get(pk=protein_pk, folder_id=folder_id)
             elif protein_id:
                 protein = Protein.objects.get(protein_id=protein_id, folder_id=folder_id)
             else:
                 # This case should be caught by the missing check above, but as fallback:
                 return JsonResponse({"error": "Missing protein identifier (ID or PK)"}, status=400)
        except Protein.DoesNotExist:
            error_msg = f"Protein PK={protein_pk}" if protein_pk else f"Protein ID='{protein_id}'"
            return JsonResponse({"error": f"{error_msg} not found in folder ID={folder_id}"}, status=404)
        except Protein.MultipleObjectsReturned:
            # This really should only happen if using protein_id and it's not unique within the folder
             logger.error(f"Multiple proteins found for id={protein_id} in folder={folder_id}")
             return JsonResponse({"error": "Internal Server Error: Duplicate protein ID found"}, status=500)


        folder = protein.folder
        title = folder.title if folder else ""

        # --- Create or update standard Annotation ---
        annotation, created = Annotation.objects.update_or_create(
            protein=protein,
            user=user,
            defaults={
                "folder": folder,
                "annotation_title": title,
                "given_annotation": direction_map[direction],
                # Ensure timestamp is updated on modification
                "timestamp": timezone.now()
            }
        )

        return JsonResponse({"success": True})

    except json.JSONDecodeError:
         return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"Standard Annotation submission failed: {e}", exc_info=True)
        return JsonResponse({"error": f"An unexpected server error occurred: {str(e)}"}, status=500)




@login_required
def download_annotations_csv(request, folder_id):
    folder = get_object_or_404(ProteinFolder, id=folder_id)
    annotations = Annotation.objects.filter(folder=folder).select_related('user', 'protein')

    response = HttpResponse(content_type='text/tab-separated-values; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="annotations_{folder.name}.tsv"'

    writer = csv.writer(response, delimiter='\t')
    writer.writerow(['Username', 'Protein ID', 'Annotation', 'Timestamp'])

    for annotation in annotations:
        writer.writerow([
            annotation.user.username,
            annotation.protein.protein_id,
            annotation.get_given_annotation_display(),
            annotation.timestamp
        ])

    return response


@login_required
def annotation_overview(request, folder_id):
    folder = get_object_or_404(ProteinFolder, id=folder_id)

    user_id = request.GET.get("user")
    if user_id and user_id != str(request.user.id):
        try:
            target_user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("annotations_app:view_folders")
    else:
        target_user = request.user

    annotations = Annotation.objects.filter(
        folder=folder,
        user=target_user
    ).select_related("protein").order_by("given_annotation", "protein__protein_id")

    for ann in annotations:
        protein = ann.protein
        if protein.pdb_file_path:
            try:
                base_media_path = os.path.join(settings.MEDIA_ROOT, '')
                if os.path.isabs(protein.pdb_file_path):
                    pdb_full_path = default_storage.path(protein.pdb_file_path)
                    relative_path = os.path.relpath(pdb_full_path, base_media_path)
                    protein.pdb_file_path = relative_path.replace(os.path.sep, '/')
                else:
                    protein.pdb_file_path = protein.pdb_file_path.replace(os.path.sep, '/')
            except Exception as e:
                logger.warning(f"Path issue for protein {protein.pk}: {e}")
                protein.pdb_file_path = None

    users = get_user_model().objects.all()

    return render(request, "annotations_app/annotation_overview.html", {
        "folder": folder,
        "annotations": annotations,
        "media_url": settings.MEDIA_URL,
        "target_user": target_user,
        "users": users,  # ✅ Added users list here
    })


@require_POST # Ensure this view only accepts POST requests
@login_required
def redo_folder_view(request, folder_id):
    """
    Deletes all annotations made by the current user for the specified folder
    and redirects to the annotation view for that folder to start over.
    """
    folder = get_object_or_404(ProteinFolder, id=folder_id)
    user = request.user

    # Delete annotations for this user and this folder
    annotations_to_delete = Annotation.objects.filter(user=user, folder=folder)
    count = annotations_to_delete.count()
    annotations_to_delete.delete()

    messages.success(request, f"Successfully reset {count} annotations for folder '{folder.name}'. You can now start annotating it again.")

    # Redirect to the first protein annotation page for this folder
    return redirect('annotations_app:annotate_protein', folder_id=folder.id)

    # Renamed original submission view
@login_required
@require_POST # Should be POST
@csrf_exempt # Keep if using simple JS fetch without explicit CSRF header setup
def submit_standard_annotation(request):
    # This view now ONLY handles the simple Correct/Wrong/Unsure annotations
    try:
        if request.method == "POST":
            data = json.loads(request.body)
            protein_pk = data.get("protein_pk") # Prefer PK if available and unique
            protein_id = data.get("protein_id")
            folder_id = data.get("folder_id")
            direction = data.get("annotation") # left, right, down
            user = request.user

            if not (protein_pk or protein_id) or not direction or not folder_id:
                return JsonResponse({"error": "Missing data (protein_pk/id, folder_id, annotation)"}, status=400)

            direction_map = { "right": "correct", "left": "wrong", "down": "unsure" }
            if direction not in direction_map:
                return JsonResponse({"error": "Invalid annotation direction"}, status=400)

            # --- Find Protein ---
            try:
                if protein_pk:
                     protein = Protein.objects.get(pk=protein_pk, folder_id=folder_id)
                else:
                     # Fallback to protein_id, ensure it's unique within folder
                     protein = Protein.objects.get(protein_id=protein_id, folder_id=folder_id)
            except Protein.DoesNotExist:
                return JsonResponse({"error": "Protein not found in specified folder"}, status=404)
            except Protein.MultipleObjectsReturned:
                 # This shouldn't happen if using PK, but handle for protein_id case
                 logger.error(f"Multiple proteins found for id={protein_id} in folder={folder_id}")
                 return JsonResponse({"error": "Internal Server Error: Duplicate protein ID found"}, status=500)


            folder = protein.folder
            title = folder.title if folder else ""

            # --- Create or update standard Annotation ---
            # NOTE: For architecture annotations, this record marks the protein as "reviewed"
            annotation, created = Annotation.objects.update_or_create(
                protein=protein,
                user=user,
                defaults={
                    "folder": folder,
                    "annotation_title": title,
                    "given_annotation": direction_map[direction]
                }
            )
            # Update timestamp manually if updating
            if not created:
                annotation.timestamp = timezone.now() # Requires: from django.utils import timezone
                annotation.save(update_fields=['timestamp', 'given_annotation'])

            return JsonResponse({"success": True})

        return JsonResponse({"error": "Invalid request method"}, status=405)

    except json.JSONDecodeError:
         return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"Standard Annotation failed: {e}", exc_info=True)
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)


# --- NEW VIEW: Domain Correction Submission ---
@login_required
@require_POST
def submit_domain_correction(request):
    """
    Save (or overwrite) the list of domains the user has marked as wrong
    for *this protein*.  Any domains that were previously marked but are
    no longer in `corrections` are deleted.
    """
    try:
        data        = json.loads(request.body)
        protein_pk  = data.get("protein_pk")
        folder_id   = data.get("folder_id")
        corrections = data.get("corrections")        # list[{name,start,end}]
        user        = request.user

        if not protein_pk or folder_id is None or not isinstance(corrections, list):
            return JsonResponse(
                {"error": "Missing or invalid data (protein_pk, folder_id, corrections)"},
                status=400
            )

        # ------------------------------------------------------------------
        # Look-up objects
        # ------------------------------------------------------------------
        try:
            protein = Protein.objects.get(pk=protein_pk, folder_id=folder_id)
        except Protein.DoesNotExist:
            return JsonResponse({"error": "Protein not found in folder"}, status=404)

        # ------------------------------------------------------------------
        # Replace the old set atomically
        # ------------------------------------------------------------------
        with transaction.atomic():
            # 1) drop everything that exists for this user+protein
            DomainCorrection.objects.filter(user=user, protein=protein).delete()

            # 2) create fresh rows (if any)
            new_objs = []
            for corr in corrections:
                try:
                    new_objs.append(DomainCorrection(
                        protein=protein,
                        user=user,
                        domain_name=corr["name"],
                        start_pos=int(corr["start"]),
                        end_pos=int(corr["end"]),
                        is_marked_wrong=True
                    ))
                except (KeyError, ValueError, TypeError):
                    # skip malformed rows silently
                    continue
            DomainCorrection.objects.bulk_create(new_objs)

            # 3) mark the protein as “reviewed” in the standard Annotation
            Annotation.objects.update_or_create(
                protein=protein,
                user=user,
                defaults={
                    "folder": protein.folder,
                    "annotation_title": protein.folder.title,
                    "given_annotation": "correct",
                    "timestamp": timezone.now()
                }
            )

        return JsonResponse({
            "success": True,
            "saved": len(new_objs),
            "message": (
                "Corrections updated."
                if new_objs else
                "No domains are marked wrong any more."
            )
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error("Domain-correction save failed: %s", e, exc_info=True)
        return JsonResponse({"error": f"Server error: {e}"}, status=500)

@require_POST
@login_required
def undo_last(request):
    user = request.user                              # ←  back in place!

    # ------------------------------------------------------------------
    # read the optional folder_id that the JS sends
    # ------------------------------------------------------------------
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        payload = {}

    folder_id = payload.get("folder_id")

    # ------------------------------------------------------------------
    # find the most-recent annotation *for this user (and folder)*
    # ------------------------------------------------------------------
    qs = Annotation.objects.filter(user=user)
    if folder_id:
        qs = qs.filter(folder_id=folder_id)

    try:
        last = qs.latest("timestamp")
    except Annotation.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "You haven’t saved anything yet."},
            status=404,
        )

    protein = last.protein

    # ------------------------------------------------------------------
    # delete the annotation and all its auxiliary rows
    # ------------------------------------------------------------------
    last.delete()
    DomainCorrection.objects.filter(user=user, protein=protein).delete()
    # ManualDomainAnnotation.objects.filter(user=user, protein=protein).delete()

    # ------------------------------------------------------------------
    # tell the browser to open that protein again
    # ------------------------------------------------------------------
    return JsonResponse(
        {
            "success": True,
            "redirect_url": reverse(
                "annotations_app:annotate_specific_protein",
                args=[protein.folder_id, protein.pk],
            ),
        }
    )

# views.py
@require_POST
@login_required
def undo_last_manual_domain(request):
    """
    Roll back the **last set of manual-domain splits** you saved,
    without touching any structure/architecture annotations.

    • It looks only at `ManualDomainAnnotation` rows.  
    • It removes every split for that protein and user.  
    • It leaves the `Annotation` table completely untouched.
    """
    user = request.user

    # optional folder filter coming from JS ---------------------------------
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        payload = {}
    folder_id = payload.get("folder_id")

    # locate the most-recent manual-domain entry ----------------------------
    qs = ManualDomainAnnotation.objects.filter(user=user)
    if folder_id:
        qs = qs.filter(protein__folder_id=folder_id)

    last_split = qs.order_by("-id").first()          # id ≈ insertion order
    if not last_split:
        return JsonResponse(
            {"success": False,
             "error": "You haven’t saved any manual domains yet."},
            status=404,
        )

    protein = last_split.protein

    # wipe all manual splits for that protein/user --------------------------
    ManualDomainAnnotation.objects.filter(user=user, protein=protein).delete()

    # redirect back to the same protein in the manual flow ------------------
    redirect_url = reverse(
        "annotations_app:manual_annotate_folder",
        args=[protein.folder_id],                    # one-arg URL variant
        # args=[protein.folder_id, protein.pk],      # if your URL expects both
    )

    return JsonResponse({"success": True, "redirect_url": redirect_url})

@login_required
@login_required
def architecture_annotation_overview(request, folder_id):
    """
    Show every protein that *has a standard annotation* together with
    • all domains parsed from its CSV (the “annotated domains”)
    • the subset the user marked as wrong
    """
    folder = get_object_or_404(ProteinFolder, id=folder_id)

    # -------- resolve user to display ----------------------------------
    user_id = request.GET.get("user")
    User = get_user_model()
    if user_id:
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("annotations_app:view_folders")
    else:
        target_user = request.user

    # -------- fetch data ------------------------------------------------
    ann_qs = Annotation.objects.filter(folder=folder, user=target_user) \
                               .select_related("protein")

    corr_qs = DomainCorrection.objects.filter(
        user=target_user,
        protein__folder=folder,
        is_marked_wrong=True
    ).select_related("protein")

    # group corrections by protein for quick lookup
    wrong_by_protein = defaultdict(list)
    for c in corr_qs:
        wrong_by_protein[c.protein].append(c)

    # -------- build per-protein payload --------------------------------
    protein_info = []
    for ann in ann_qs:
        protein = ann.protein

        # 1. parse CSV → predicted / annotated domains
        domains, _err = parse_domain_csv(protein)
        domains = domains or []                     # empty list on error

        # 2. tag those that are marked wrong
        wrong_set = {
            (w.domain_name, w.start_pos, w.end_pos)
            for w in wrong_by_protein.get(protein, [])
        }

        tagged = []
        for d in domains:
            tagged.append({
                "name":  d["name"],
                "start": d["start"],
                "end":   d["end"],
                "wrong": (d["name"], d["start"], d["end"]) in wrong_set
            })

        protein_info.append((protein, tagged))

    protein_info.sort(key=lambda pair: pair[0].protein_id)

    users = User.objects.all()

    return render(request, "annotations_app/architecture_overview.html", {
        "folder": folder,
        "protein_info": protein_info,   # ← NEW payload
        "media_url": settings.MEDIA_URL,
        "target_user": target_user,
        "users": users,
    })


# annotations_app/views.py
@login_required
def download_domain_corrections_csv(request, folder_id):
    """
    Export one TSV line per (user, protein) in the folder.
    • Status    – “No domains marked” or “n domain(s) marked”
    • Marked…   – list of domain names
    • Domain…   – list of residue ranges
    """
    folder = get_object_or_404(ProteinFolder, id=folder_id)

    # ------------------------------------------------------------
    # 1)  fetch once, group in memory
    # ------------------------------------------------------------
    from collections import defaultdict
    corr_map = defaultdict(list)          # (user_id, protein_id) ➜ [DomainCorrection]

    for c in DomainCorrection.objects.filter(
            protein__folder=folder,
            is_marked_wrong=True
        ).select_related("protein", "user"):
        corr_map[(c.user_id, c.protein_id)].append(c)

    # ------------------------------------------------------------
    # 2)  we need at least the set of (user, protein) pairs.
    #     The Annotation table is the easiest way to get that.
    # ------------------------------------------------------------
    annotations = (
        Annotation.objects
        .filter(folder=folder)
        .select_related("protein", "user")
        .order_by("user__username", "protein__protein_id")
    )

    # ------------------------------------------------------------
    # 3)  build the TSV
    # ------------------------------------------------------------
    response = HttpResponse(
        content_type="text/tab-separated-values; charset=utf-8"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="architecture_overview_{folder.name}.tsv"'
    )

    writer = csv.writer(response, delimiter="\t")
    writer.writerow(
        ["Username", "Protein ID", "Status", "Marked Domains", "Domain Ranges"]
    )

    for ann in annotations:
        key         = (ann.user_id, ann.protein_id)
        domain_list = corr_map.get(key, [])

        if domain_list:
            status        = f"{len(domain_list)} domain(s) marked"
            domain_names  = [smart_str(d.domain_name) for d in domain_list]
            domain_ranges = [f"{d.start_pos}-{d.end_pos}" for d in domain_list]
        else:
            status, domain_names, domain_ranges = (
                "No domains marked", [], []
            )

        writer.writerow(
            [
                ann.user.username,
                ann.protein.protein_id,
                status,
                str(domain_names),
                str(domain_ranges),
            ]
        )

    return response



@require_POST
@login_required
def delete_folder(request, folder_id):
    folder = get_object_or_404(ProteinFolder, id=folder_id)

    if request.user != folder.user:
        messages.error(request, "You are not authorized to delete this folder.")
        return redirect('annotations_app:view_folders')

    try:
        # Optionally delete associated proteins and annotations
        Protein.objects.filter(folder=folder).delete()
        Annotation.objects.filter(folder=folder).delete()
        DomainCorrection.objects.filter(protein__folder=folder).delete()
        folder.delete()
        messages.success(request, f"Folder '{folder.name}' has been deleted.")
    except Exception as e:
        logger.error(f"Error deleting folder {folder_id}: {e}", exc_info=True)
        messages.error(request, "An error occurred while deleting the folder.")

    return redirect('annotations_app:view_folders')

# --- Additional View for Saving Manual Domain Annotations ---


@login_required
@require_POST
def submit_manual_domains(request):
    try:
        data = json.loads(request.body)
        protein_pk = data.get("protein_pk")
        folder_id = data.get("folder_id")
        domains = data.get("manual_domains")  # [{name, start, end}, ...]
        user = request.user

        if not (protein_pk and folder_id and isinstance(domains, list)):
            return JsonResponse({"error": "Missing required data."}, status=400)

        protein = get_object_or_404(Protein, pk=protein_pk, folder_id=folder_id)

        # Delete existing manual annotations by this user
        ManualDomainAnnotation.objects.filter(protein=protein, user=user).delete()

        # Save new domain data
        new_objs = [
            ManualDomainAnnotation(
                protein=protein,
                user=user,
                domain_name=d["name"],
                start_pos=int(d["start"]),
                end_pos=int(d["end"])
            )
            for d in domains if all(k in d for k in ("name", "start", "end"))
        ]
        ManualDomainAnnotation.objects.bulk_create(new_objs)

        return JsonResponse({"success": True, "message": f"Saved {len(new_objs)} domain annotations."})

    except Exception as e:
        logger.error(f"Manual domain annotation failed: {e}", exc_info=True)
        return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)



@login_required
@ensure_csrf_cookie
def manual_annotate_protein_view(request):
    user = request.user
    proteins = Protein.objects.filter(domain_csv_path__isnull=True)

    if not proteins.exists():
        messages.warning(request,
                         "No proteins without domain CSVs available for manual annotation.")
        return redirect('annotations_app:view_folders')

    annotated_ids = Annotation.objects.filter(user=user)\
                                      .values_list("protein_id", flat=True)
    protein = proteins.exclude(pk__in=annotated_ids).order_by('?').first()

    if not protein:
        messages.info(request,
                      "You have manually annotated all available proteins.")
        return redirect('annotations_app:view_folders')

 # ── NEW: primary-sequence extraction ────────────────────────────────
    sequence = ""
    try:
        if protein.pdb_file_path:
            sequence = extract_pdb_sequence(
                default_storage.path(protein.pdb_file_path)
            )
    except Exception as e:
        logger.warning("Cannot extract sequence for %s: %s",
                       protein.protein_id, e)
    # ── page payload ────────────────────────────────────────────────────
    context = {
        "protein"           : protein,
        "folder"            : folder,
        "folder_id"         : folder.id,
        "annotation_title"  : folder.title or "Manual Annotation",
        "annotation_description": folder.description,
        "media_url"         : settings.MEDIA_URL,
        "pdb_url"           : (default_storage.url(protein.pdb_file_path)
                               if protein.pdb_file_path else None),
        "domain_data"       : domain_data,
        "marked_wrong_data" : [],
        "csv_error"         : None,
        "next_protein_url"  : reverse('annotations_app:manual_annotate_folder',
                                      args=[folder.id]),
        "sequence"          : sequence,          # 🔹  pass it to template
    }

    return render(request,
                  "annotations_app/manual_domain_annotator.html",
                  context)

@login_required
@ensure_csrf_cookie
def manual_annotate_folder_view(request, folder_id, protein_pk=None):
    """
    Serve manual_domain_annotator.html for one protein at a time,
    restricted to the selected folder and to structures that do NOT
    already have a domain CSV.
    """
    user   = request.user
    folder = get_object_or_404(ProteinFolder, id=folder_id)

    # only the PDB-only proteins for this folder
    proteins_qs = Protein.objects.filter(folder=folder,
                                         domain_csv_path__isnull=True)

    if not proteins_qs.exists():
        messages.warning(request,
                         "Every structure in this folder already has "
                         "predicted domains – use the architecture flow instead.")
        return redirect('annotations_app:view_folders')


    skip_key    = f"manual_skipped_{folder.id}"
    skipped     = request.session.get(skip_key, [])

    if protein_pk:                                     # explicit redo
        protein = get_object_or_404(Protein, pk=protein_pk, folder=folder)

    else:                                              # next un-done
        done_ids = ManualDomainAnnotation.objects.filter(
            user=user, protein__folder=folder
        ).values_list("protein_id", flat=True)

        protein = (
            proteins_qs
            .exclude(pk__in=done_ids)
            .exclude(pk__in=skipped)        # ← NEW
            .first()
        )

        # if everything fresh is finished, recycle skipped ones (FIFO)
        if not protein and skipped:
            protein = proteins_qs.filter(pk=skipped.pop(0)).first()
            request.session[skip_key] = skipped
            request.session.modified  = True

        if not protein:
            messages.info(request,
                        f"You finished domain-annotating “{folder.name}”.")
            return redirect('annotations_app:domain_annotation_overview',
                            folder_id=folder.id)

    # ── pre-fill any manual domains the user already saved ───────────
    existing = ManualDomainAnnotation.objects.filter(
        protein=protein, user=user
    ).order_by('start_pos')
    domain_data = [
        {'name': d.domain_name, 'start': d.start_pos, 'end': d.end_pos}
        for d in existing
    ]

# ── NEW: primary-sequence extraction ────────────────────────────────
    sequence = ""
    try:
        if protein.pdb_file_path:
            sequence = extract_pdb_sequence(
                default_storage.path(protein.pdb_file_path)
            )
    except Exception as e:
        logger.warning("Cannot extract sequence for %s: %s",
                       protein.protein_id, e)

    # ── page payload ────────────────────────────────────────────────────
    context = {
        "protein"           : protein,
        "folder"            : folder,
        "folder_id"         : folder.id,
        "annotation_title"  : folder.title or "Manual Annotation",
        "annotation_description": folder.description,
        "media_url"         : settings.MEDIA_URL,
        "pdb_url"           : (default_storage.url(protein.pdb_file_path)
                               if protein.pdb_file_path else None),
        "domain_data"       : domain_data,
        "marked_wrong_data" : [],
        "csv_error"         : None,
        "next_protein_url"  : reverse('annotations_app:manual_annotate_folder',
                                      args=[folder.id]),
        "sequence"          : sequence,          # 🔹  pass it to template
        "domain_data": domain_data,              # keep: still useful in Jinja
        "domain_data_json": json.dumps(domain_data),   # <-- NEW
    }

    return render(request,
                  "annotations_app/manual_domain_annotator.html",
                  context)


# annotations_app/views.py  (append near the other overview views)
@login_required
def domain_annotation_overview(request, folder_id):
    """
    List every protein that CURRENT (or selected) user has
    manually split into domains, together with the domains.
    """
    from collections import defaultdict
    folder = get_object_or_404(ProteinFolder, id=folder_id)

    # -- whose annotations do we show? (same logic as annotation_overview)
    user_id   = request.GET.get("user")
    User      = get_user_model()
    target_user = request.user if not user_id or user_id == str(request.user.id) \
                  else get_object_or_404(User, id=user_id)

    qs = ManualDomainAnnotation.objects.filter(
            protein__folder=folder,
            user=target_user
         ).select_related("protein")

    protein_to_domains = defaultdict(list)
    for d in qs:
        protein_to_domains[d.protein].append(d)

    users = User.objects.all()

    # ⬇ NEW – convert to a sortable list of (protein, [domains]) tuples
    protein_domain_list = [
        (protein, doms) for protein, doms in protein_to_domains.items()
    ]
    protein_domain_list.sort(key=lambda t: t[0].protein_id)   # nice ordering

    return render(
        request,
        "annotations_app/domain_annotation_overview.html",
        {
            "folder"            : folder,
            "protein_to_domains": protein_domain_list,   # 👈 pass the list
            "media_url"         : settings.MEDIA_URL,
            "target_user"       : target_user,
            "users"             : users,
        },
    )

# views.py
# views.py
@login_required
def domain_annotation_download(request, folder_id):
    """
    ZIP export with:
      • {protein}.csv               manual-domain table
      • fastas/{protein}.fasta      1 FASTA record / domain
      • pdbs/{protein}/domain_*.pdb individual PDBs per domain
    """
    from textwrap import wrap
    from django.utils.text import slugify
    from Bio import PDB
    from Bio.PDB import PDBIO, Select
    from .utils import extract_pdb_sequence

    folder = get_object_or_404(ProteinFolder, pk=folder_id)

    # --- which user's data are we exporting? ---------------------------
    user_id = request.GET.get("user")                # from “…?user=42”
    if user_id:
        try:
            target_user = get_user_model().objects.get(pk=user_id)
        except get_user_model().DoesNotExist:
            raise Http404("User not found.")
    else:
        target_user = request.user                   # fallback



    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

        # proteins = (
        #     Protein.objects.filter(folder=folder)
        #     .prefetch_related("manual_domain_annotations")
        #     .order_by("protein_id")
        # )
        domains_qs = ManualDomainAnnotation.objects.filter(   # only wanted user
                            user=target_user
                        ).order_by("start_pos")

        proteins = (
            Protein.objects.filter(
                folder=folder,
                manual_domain_annotations__user=target_user   # at least one split
            )
            .prefetch_related(                                # attach just those
                Prefetch("manual_domain_annotations",
                        queryset=domains_qs,
                        to_attr="user_domains")
            )
            .order_by("protein_id")
            .distinct()
        )
        wrote_any = False

        for protein in proteins:
            domains = protein.user_domains        # already filtered & ordered

            if not domains:
                continue

            wrote_any = True

            # ---------- CSV ----------
            csv_io = io.StringIO()
            writer = csv.writer(csv_io)
            writer.writerow(
                ["Domain Number", "Start Residue", "End Residue", "Predicted Domain"]
            )
            for idx, d in enumerate(domains, 1):
                writer.writerow([idx, d.start_pos, d.end_pos, d.domain_name])
            zf.writestr(f"{protein.protein_id}.csv", csv_io.getvalue())

            # ---------- full sequence ----------
            seq_full = ""
            pdb_abs  = None
            try:
                if protein.pdb_file_path:
                    pdb_abs = default_storage.path(protein.pdb_file_path)
                    seq_full = extract_pdb_sequence(pdb_abs)
            except Exception as e:
                logger.warning("Sequence/PDB parse failed for %s: %s",
                               protein.protein_id, e)

            # ---------- FASTA ----------
            if seq_full:
                fasta_lines = []
                for d in domains:
                    if not (1 <= d.start_pos <= d.end_pos <= len(seq_full)):
                        continue
                    frag = seq_full[d.start_pos-1 : d.end_pos]
                    header = (
                        f">{protein.protein_id}|{d.domain_name}"
                        f"|{d.start_pos}-{d.end_pos}"
                    )
                    fasta_lines.append(header + "\n" +
                                       "\n".join(wrap(frag, 60)))
                if fasta_lines:
                    zf.writestr(
                        f"fastas/{protein.protein_id}.fasta",
                        "\n".join(fasta_lines) + "\n"
                    )

            # ---------- per-domain PDBs ----------
            if pdb_abs and os.path.exists(pdb_abs):
                try:
                    parser    = PDB.PDBParser(QUIET=True)
                    structure = parser.get_structure("model", pdb_abs)

                    # we know how many domains upfront → choose a width that keeps
                    # alphabetical = numerical order (e.g. 01, 02 … 10)
                    num_digits = max(2, len(str(len(domains))))

                    for idx, d in enumerate(domains, 1):
                        start, end = d.start_pos, d.end_pos
                        if start > end:
                            continue

                        class RangeSelect(Select):
                            def accept_residue(self, residue, s=start, e=end):
                                return s <= residue.id[1] <= e

                        pdb_io  = PDBIO()
                        pdb_io.set_structure(structure)
                        buf = io.StringIO()
                        pdb_io.save(buf, RangeSelect())

                        domain_slug = slugify(d.domain_name) or f"domain{idx}"
                        idx_str     = str(idx).zfill(num_digits)          # e.g. 01
                        fname = (
                            f"pdbs/{protein.protein_id}/"
                            f"{protein.protein_id}_{idx_str}_{domain_slug}.pdb"
                        )
                        zf.writestr(fname, buf.getvalue())

                except Exception as e:
                    logger.warning("Domain-PDB split failed for %s: %s",
                                protein.protein_id, e)


        if not wrote_any:
            raise Http404("No domain annotations found in this folder.")

    zip_buffer.seek(0)
    # response = HttpResponse(zip_buffer.read(), content_type="application/zip")
    # response["Content-Disposition"] = (
    #     f'attachment; filename=\"domain_annotations_{folder.id}.zip\"'
    # )
    response = HttpResponse(zip_buffer.getvalue(),
                            content_type="application/zip")
    
    # Cache-busting headers
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"]        = "no-cache"
    response["Expires"]       = "0"
    
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = (
        f'attachment; filename="domain_annotations_{folder.id}_{stamp}.zip"'
    )
    return response

# annotations_app/views.py  (place near the other POST helpers)
@require_POST
@login_required
def skip_manual_domain(request):
    """
    Put the current protein on a “come-back-later” list that lives
    in the user’s session (per-folder) and jump straight to the next
    manual-domain job.
    """
    try:
        data       = json.loads(request.body or "{}")
        protein_pk = data.get("protein_pk")
        folder_id  = data.get("folder_id")
        if not (protein_pk and folder_id):
            return JsonResponse({"error": "Missing data"}, status=400)

        # ── sanity check ────────────────────────────────────────────────
        Protein.objects.get(
            pk=protein_pk,
            folder_id=folder_id,
            domain_csv_path__isnull=True        # manual-domain candidates only
        )

        key      = f"manual_skipped_{folder_id}"
        skipped  = request.session.get(key, [])
        if protein_pk not in skipped:
            skipped.append(protein_pk)
            request.session[key] = skipped      # persists until logout
            request.session.modified = True

        return JsonResponse({
            "success"     : True,
            "redirect_url": reverse(
                "annotations_app:manual_annotate_folder",
                args=[folder_id]                # → “next” protein
            )
        })
    except Protein.DoesNotExist:
        return JsonResponse({"error": "Protein not found"}, status=404)
    except Exception as e:
        logger.error("Skip-manual failed: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


def about_view(request):
    return render(request, 'annotations_app/about.html')

def home(request):
    return render(request, 'annotations_app/home.html')
