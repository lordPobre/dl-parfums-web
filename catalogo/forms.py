from django import forms


class ContactoForm(forms.Form):
    nombre = forms.CharField(max_length=80)
    email = forms.EmailField(max_length=120)
    mensaje = forms.CharField(max_length=3000, widget=forms.Textarea)
    sitio_web = forms.CharField(required=False)  # campo trampa: solo lo llenan los bots

    def clean_nombre(self):
        # Sin saltos de línea: el nombre va en el asunto del correo
        return " ".join(self.cleaned_data["nombre"].split())
