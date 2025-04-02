# ~/annotate/annotations_app/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User # Or your custom user model if you have one

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
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email



# forms.py
class PDBZipUploadForm(forms.Form):
    folder_name = forms.CharField(max_length=100)
    annotation_title = forms.CharField(max_length=255)
    annotation_description = forms.CharField(widget=forms.Textarea, required=False)
    zip_file = forms.FileField(label="Upload a ZIP file of PDBs")

