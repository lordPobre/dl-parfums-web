from django import forms


class ContactoForm(forms.Form):
    nombre = forms.CharField(max_length=80)
    email = forms.EmailField(max_length=120)
    mensaje = forms.CharField(max_length=3000, widget=forms.Textarea)
    sitio_web = forms.CharField(required=False)  # campo trampa: solo lo llenan los bots

    def clean_nombre(self):
        # Sin saltos de línea: el nombre va en el asunto del correo
        return " ".join(self.cleaned_data["nombre"].split())


# --- Datos del cliente antes de WhatsApp (datos-pedido) ---
import re

REGIONES = [
    "Arica y Parinacota", "Tarapacá", "Antofagasta", "Atacama", "Coquimbo", "Valparaíso",
    "Metropolitana", "O'Higgins", "Maule", "Ñuble", "Biobío", "La Araucanía",
    "Los Ríos", "Los Lagos", "Aysén", "Magallanes",
]


def formatear_rut(valor):
    """'12345678k' -> '12.345.678-K'. None si el dígito verificador no coincide."""
    limpio = re.sub(r"[^0-9kK]", "", valor or "").upper()
    if not 8 <= len(limpio) <= 9 or not limpio[:-1].isdigit():
        return None
    cuerpo, dv = limpio[:-1], limpio[-1]
    suma, factor = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    if dv != {11: "0", 10: "K"}.get(resto, str(resto)):
        return None
    return f"{int(cuerpo):,}".replace(",", ".") + "-" + dv


def formatear_telefono(valor):
    """'912345678' o '+56 9 1234 5678' -> '+56 9 1234 5678'. None si no tiene 9 dígitos."""
    d = re.sub(r"\D", "", valor or "")
    if len(d) == 11 and d.startswith("56"):
        d = d[2:]
    if len(d) != 9:
        return None
    return f"+56 {d[0]} {d[1:5]} {d[5:]}"


class DatosPedidoForm(forms.Form):
    nombre = forms.CharField(max_length=60)
    apellido = forms.CharField(max_length=60)
    rut = forms.CharField(max_length=14)
    telefono = forms.CharField(max_length=20)
    email = forms.EmailField(max_length=120)
    region = forms.ChoiceField(choices=[(r, r) for r in REGIONES])
    comuna = forms.CharField(max_length=60)
    direccion = forms.CharField(max_length=160)
    notas = forms.CharField(max_length=500, required=False)

    def clean_rut(self):
        rut = formatear_rut(self.cleaned_data["rut"])
        if not rut:
            raise forms.ValidationError("RUT no válido. Revisa el dígito verificador.")
        return rut

    def clean_telefono(self):
        tel = formatear_telefono(self.cleaned_data["telefono"])
        if not tel:
            raise forms.ValidationError("Escribe un celular de 9 dígitos, ej. 9 1234 5678.")
        return tel

    def clean(self):
        datos = super().clean()
        # Una sola línea: el nombre va en el asunto del correo
        for campo in ("nombre", "apellido", "comuna", "direccion"):
            if datos.get(campo):
                datos[campo] = " ".join(datos[campo].split())
        return datos

    def campos_pedido(self):
        d = self.cleaned_data
        return {
            "cliente": d["nombre"], "apellido": d["apellido"], "rut": d["rut"], "telefono": d["telefono"],
            "email": d["email"], "region": d["region"], "comuna": d["comuna"],
            "direccion": d["direccion"], "notas": d.get("notas", ""),
        }
