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
from django.contrib import messages # Make sure messages is imported

from .forms import CustomUserCreationForm, PDBZipUploadForm
from .models import ProteinFolder, Protein, Annotation

import csv
from django.http import HttpResponse
from collections import defaultdict


logger = logging.getLogger(__name__) # Setup logger for the view

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

@login_required
def view_folders(request):
    # Fetch folders associated with the user or all folders if you want admins to see everything
    # For now, let's assume users only see their own folders or all folders. Adjust if needed.
    # folders = ProteinFolder.objects.filter(user=request.user) # Option: Only user's folders
    folders = ProteinFolder.objects.all().order_by('name') # Show all folders
    folder_data = []

    for folder in folders:
        total_proteins = folder.proteins.count()
        # Count annotations specifically for the current user and this folder
        annotated_count = Annotation.objects.filter(folder=folder, user=request.user).count()
        is_complete = total_proteins > 0 and total_proteins == annotated_count

        folder_data.append({
            'folder': folder,
            'is_complete': is_complete,
            'total_proteins': total_proteins,
            'annotated_count': annotated_count,
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
def annotate_protein_view(request, folder_id, protein_pk=None): # Add protein_pk=None
    user = request.user
    folder = get_object_or_404(ProteinFolder, id=folder_id)
    proteins_qs = Protein.objects.filter(folder=folder).order_by('protein_id') # Ensure consistent order

    protein_to_annotate = None
    is_specific_redo = False # Flag to know if we loaded a specific protein

    if protein_pk:
        # If a specific protein PK is provided, load that protein
        protein_to_annotate = get_object_or_404(Protein, pk=protein_pk, folder=folder)
        # Optional: Add checks here if you need to verify user permissions for this specific protein/folder
        is_specific_redo = True
        messages.info(request, f"Re-annotating specific protein: {protein_to_annotate.protein_id}") # Optional feedback
    else:
        # Original logic: Find the next unannotated protein
        if not proteins_qs.exists():
            messages.warning(request, f"Folder '{folder.name}' contains no proteins.")
            return redirect('annotations_app:view_folders')

        annotated_ids = Annotation.objects.filter(user=user, folder=folder).values_list('protein__id', flat=True)
        protein_to_annotate = proteins_qs.exclude(id__in=annotated_ids).first()

        if not protein_to_annotate:
            messages.info(request, f"You have completed annotating all proteins in folder '{folder.name}'.")
            return redirect('annotations_app:annotation_overview', folder_id=folder.id)

    # --- Common logic for both cases ---
    if not protein_to_annotate:
         # This case should ideally not be reached if logic above is correct, but as a fallback:
         messages.error(request, "Could not find a protein to annotate.")
         return redirect('annotations_app:view_folders')


    # Prepare context
    context = {
        'protein': protein_to_annotate,
        'media_url': settings.MEDIA_URL,
        'annotation_title': folder.title,
        'annotation_description': folder.description,
        'folder': folder, # Pass the whole folder object
        'folder_id': folder.id,
        'is_specific_redo': is_specific_redo, # Pass the flag to the template
    }

    # Clean up pdb_file_path (same robust cleaning as before)
    if protein_to_annotate.pdb_file_path:
        try:
            # Using default_storage.url might be simpler if configured correctly
            # context['pdb_url'] = default_storage.url(protein_to_annotate.pdb_file_path)
            # Manual relative path construction:
            base_media_path = os.path.join(settings.MEDIA_ROOT, '')
            pdb_full_path = default_storage.path(protein_to_annotate.pdb_file_path)
            relative_path = os.path.relpath(pdb_full_path, base_media_path)
            # Ensure forward slashes for URL compatibility
            protein_to_annotate.cleaned_pdb_path = relative_path.replace(os.path.sep, '/')
        except Exception as e:
             logging.error(f"Error processing PDB path '{protein_to_annotate.pdb_file_path}': {e}")
             messages.error(request, "Error finding the PDB file path.")
             # Decide how to handle - maybe show error on page or redirect
             protein_to_annotate.cleaned_pdb_path = None # Indicate path issue

    # Pass the cleaned path to the template if using manual construction
    context['cleaned_pdb_path'] = getattr(protein_to_annotate, 'cleaned_pdb_path', None)

    return render(request, 'annotations_app/annotate.html', context)


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

    # Get the flat list of annotations, SORTED BY THE GROUPING KEY FIRST
    annotations = Annotation.objects.filter(
        folder=folder,
        user=request.user
    ).select_related('protein').order_by('given_annotation', 'protein__protein_id') # CORRECTED ORDERING

    # The template will handle the grouping now

    # Clean paths directly on the protein objects within annotations
    for ann in annotations:
        protein = ann.protein
        if protein.pdb_file_path:
            try:
                # Manual relative path construction:
                base_media_path = os.path.join(settings.MEDIA_ROOT, '')
                # Check if the path is already relative, avoid calling default_storage.path on relative paths
                if not os.path.isabs(protein.pdb_file_path):
                     # Assume it might be relative to MEDIA_ROOT already (e.g., 'pdbs/user/folder/file.pdb')
                     # Or if it includes MEDIA_URL prefix, strip it if needed
                     # This part might need adjustment based on exactly how paths are stored
                     # For now, let's assume if it's not absolute, it's okay as is for URL construction
                     pass # Keep the path as is
                else:
                    # If it's absolute, try to make it relative to MEDIA_ROOT
                    pdb_full_path = default_storage.path(protein.pdb_file_path) # This might fail if path isn't in storage
                    relative_path = os.path.relpath(pdb_full_path, base_media_path)
                    # Ensure forward slashes for URL compatibility
                    protein.pdb_file_path = relative_path.replace(os.path.sep, '/') # Overwrite original or use new attr

            except ValueError as ve:
                 # Handle cases where default_storage.path() fails (e.g., path not managed by storage)
                 logging.warning(f"Could not resolve absolute path for protein {protein.id} ('{protein.pdb_file_path}'): {ve}. Assuming relative path.")
                 # Ensure forward slashes even if we couldn't resolve it fully
                 if protein.pdb_file_path:
                     protein.pdb_file_path = protein.pdb_file_path.replace(os.path.sep, '/')
            except Exception as e:
                logging.error(f"Error processing PDB path for protein {protein.id} ('{protein.pdb_file_path}'): {e}")
                protein.pdb_file_path = None # Indicate path issue

        # Ensure forward slashes just in case
        if protein.pdb_file_path:
             protein.pdb_file_path = protein.pdb_file_path.replace(os.path.sep, '/')


    return render(request, 'annotations_app/annotation_overview.html', {
        'folder': folder,
        'annotations': annotations, # Pass the correctly sorted flat queryset/list
        'media_url': settings.MEDIA_URL
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
