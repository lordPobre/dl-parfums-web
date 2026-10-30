"""Archivos estáticos con hash en el nombre (base.3f2a1c….js), comprimidos por WhiteNoise (E5).

Con nombres fijos, después de un deploy el navegador o Cloudflare podían servir el JS anterior
hasta una hora. Con hash, cada versión tiene su propia URL y se guarda 1 año.

Diferencia con el de WhiteNoise: si un CSS o JS apunta a un archivo que no existe (por ejemplo
el .map de Chart.js, que no viene en el repo), deja la referencia tal cual en vez de abortar
collectstatic; y una plantilla que pide un archivo fuera del manifiesto recibe la URL sin hash
en vez de un error 500.
"""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class EstaticosConHash(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            return name
