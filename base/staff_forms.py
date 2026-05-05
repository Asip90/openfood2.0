# base/staff_forms.py
from django import forms


class StaffLoginForm(forms.Form):
    username = forms.CharField(
        max_length=50,
        label='Identifiant',
        widget=forms.TextInput(attrs={
            'placeholder': "Nom d'utilisateur",
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Mot de passe',
            'autocomplete': 'current-password',
        }),
    )


class StaffMemberForm(forms.Form):
    ROLE_CHOICES = [
        ('coadmin', 'Co-administrateur'),
        ('cuisinier', 'Cuisinier'),
        ('serveur', 'Serveur'),
    ]

    first_name = forms.CharField(max_length=100, label='Prénom')
    last_name = forms.CharField(max_length=100, label='Nom')
    username = forms.CharField(
        max_length=50,
        label='Identifiant',
        help_text='Unique au sein du restaurant',
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, label='Rôle')
    password = forms.CharField(
        widget=forms.PasswordInput(),
        label='Mot de passe',
        required=False,
        help_text='Laisser vide pour ne pas modifier (édition uniquement)',
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(),
        label='Confirmer le mot de passe',
        required=False,
    )
    is_active = forms.BooleanField(required=False, initial=True, label='Compte actif')

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('confirm_password')
        if p1 or p2:
            if p1 != p2:
                self.add_error('confirm_password', 'Les mots de passe ne correspondent pas.')
        return cleaned
