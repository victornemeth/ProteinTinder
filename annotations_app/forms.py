# ~/annotate/annotations_app/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User # Or your custom user model if you have one
import zipfile # Import zipfile for validation

class CustomUserCreationForm(UserCreationForm):
    # You can add extra fields here if needed, like email
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')

    class Meta(UserCreationForm.Meta):
        model = User # Make sure this points to the correct User model
        # Include 'email' along with default fields
        fields = UserCreationForm.Meta.fields + ('email',)

    # You can add custom validation here if necessary
    # For example, check if email is unique (though User model often enforces this)
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if email exists and belongs to a *different* user during signup
        if User.objects.filter(email=email).exists():
             # Optional: If you allow users to change email later, you might need
             # to exclude the current user's record during updates.
             # For signup, this check is usually sufficient.
             raise forms.ValidationError("An account with this email address already exists.")
        return email


class PDBZipUploadForm(forms.Form):
    folder_name = forms.CharField(max_length=100, label="Folder Name")
    annotation_title = forms.CharField(max_length=255, label="Annotation Title")
    annotation_description = forms.CharField(widget=forms.Textarea, required=False, label="Description")
    zip_file = forms.FileField(label="Upload ZIP File (.zip)")
    # Add the new checkbox field
    is_architecture_annotation = forms.BooleanField(
        required=False, # Make it optional (default is False/unchecked)
        label="Include architecture data (CSV files)?",
        help_text="Check this if your ZIP file contains a matching .csv file for every .pdb file."
    )

    def clean_zip_file(self):
        """ Add basic validation for the zip file itself. """
        zip_file = self.cleaned_data.get('zip_file')
        if zip_file:
            try:
                # Check if it's a valid zip file by trying to read its structure
                with zipfile.ZipFile(zip_file, 'r') as zf:
                    # You could add more checks here, like file count limits if needed
                    if not zf.namelist():
                        raise forms.ValidationError("The uploaded ZIP file is empty.")
            except zipfile.BadZipFile:
                raise forms.ValidationError("The uploaded file is not a valid ZIP file.")
            # Reset file pointer after reading for subsequent processing in the view
            zip_file.seek(0)
        return zip_file

    # Optional: Add clean method to validate CSV presence if checkbox is checked
    # This validation is complex here because we need the extracted file list.
    # It's generally easier and more efficient to do this validation in the view
    # after extracting the zip.