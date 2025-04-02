# annotations_app/views.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings # <--- ADD THIS LINE
from django.contrib.auth import login # Import the login function
from .models import Protein, Annotation
from .forms import CustomUserCreationForm # Import the form we just created

from django.shortcuts import redirect

def redirect_to_annotate(request):
    return redirect('annotations_app:annotate_protein')


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
def annotate_protein_view(request):
    user = request.user

    # Get proteins the user has already annotated
    annotated_protein_ids = Annotation.objects.filter(user=user).values_list('protein_id', flat=True)

    # Get the next protein that hasn't been annotated
    protein_to_annotate = Protein.objects.exclude(
        protein_id__in=annotated_protein_ids
    ).first()

    context = {
        'protein': protein_to_annotate,
        'media_url': settings.MEDIA_URL,
    }

    if protein_to_annotate:
        # Clean the file path (remove any leading 'app/media/' or '/app/media/')
        cleaned_path = protein_to_annotate.pdb_file_path
        for prefix in ['app/media/', '/app/media/']:
            if cleaned_path.startswith(prefix):
                cleaned_path = cleaned_path.replace(prefix, '', 1)
        protein_to_annotate.pdb_file_path = cleaned_path
    else:
        context['message'] = 'All proteins annotated!'

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

            # Save annotation
            Annotation.objects.create(
                protein=protein,
                user=user,
                given_annotation=direction_map[direction]
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

