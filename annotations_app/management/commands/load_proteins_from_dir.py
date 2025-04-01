# ~/annotate/annotations_app/management/commands/load_proteins_from_dir.py

import os
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from annotations_app.models import Protein # Import your Protein model

class Command(BaseCommand):
    help = 'Scans a directory for PDB files (.pdb, .cif, .ent) and adds them to the Protein model using filenames as IDs.'

    def add_arguments(self, parser):
        # Positional argument for the directory path *inside the container*
        parser.add_argument('directory_path', type=str, help='Path to the directory containing PDB files (within the Docker container)')
        parser.add_argument(
            '--extensions',
            nargs='+', # Allows multiple extensions
            default=['.pdb', '.cif', '.ent'], # Default extensions to look for
            help='List of file extensions to consider (e.g., .pdb .cif)'
        )

    def handle(self, *args, **options):
        directory_path = options['directory_path']
        allowed_extensions = [ext.lower() for ext in options['extensions']] # Ensure lowercase

        if not os.path.isdir(directory_path):
            raise CommandError(f"Directory not found at path (inside container): {directory_path}")

        self.stdout.write(self.style.NOTICE(f"Starting scan of directory: {directory_path}"))
        self.stdout.write(f"Looking for files with extensions: {', '.join(allowed_extensions)}")

        added_count = 0
        skipped_count = 0
        error_count = 0

        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)

            # Check if it's a file and has an allowed extension
            is_allowed_file = False
            if os.path.isfile(file_path):
                _, file_ext = os.path.splitext(filename)
                if file_ext.lower() in allowed_extensions:
                    is_allowed_file = True

            if not is_allowed_file:
                continue # Skip directories or files with wrong extensions

            # Extract protein ID from filename (without extension)
            protein_id_base, _ = os.path.splitext(filename)
            protein_id = protein_id_base.strip().upper() # Clean and enforce uppercase

            if not protein_id:
                self.stdout.write(self.style.WARNING(f"Skipping file with empty base name: {filename}"))
                skipped_count += 1
                continue

            try:
                # Use get_or_create to add if not present
                # Store the path *within the container* where the file was found
                protein, created = Protein.objects.get_or_create(
                    protein_id=protein_id,
                    defaults={'pdb_file_path': filename} # Store the container path
                    # You could add other defaults, e.g., 'name': protein_id
                )

                if created:
                    added_count += 1
                    self.stdout.write(f"Added protein: {protein_id} (from {filename})")
                else:
                    # Optionally update the file path if it changed?
                    # if protein.pdb_file_path != file_path:
                    #     protein.pdb_file_path = file_path
                    #     protein.save()
                    #     self.stdout.write(f"Updated path for existing protein: {protein_id}")
                    # else:
                    skipped_count += 1
                    self.stdout.write(f"Skipped (already exists): {protein_id}")

            except IntegrityError as e:
                self.stdout.write(self.style.ERROR(f"Integrity Error for {protein_id} (from {filename}): {e}"))
                error_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing file {filename} for ID {protein_id}: {e}"))
                error_count += 1

        self.stdout.write(self.style.SUCCESS(f"Finished scan. Added: {added_count}, Skipped/Existing: {skipped_count}, Errors: {error_count}"))
