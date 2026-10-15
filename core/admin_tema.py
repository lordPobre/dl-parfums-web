"""Configuración del admin con Unfold (reemplaza JAZZMIN_SETTINGS).
Íconos: https://fonts.google.com/icons — se escriben con su nombre en inglés."""
from django.urls import reverse_lazy

_GRIS = {
    "50": "oklch(98.5% .002 247.839)", "100": "oklch(96.7% .003 264.542)", "200": "oklch(92.8% .006 264.531)",
    "300": "oklch(87.2% .01 258.338)", "400": "oklch(70.7% .022 261.325)", "500": "oklch(55.1% .027 264.364)",
    "600": "oklch(44.6% .03 256.802)", "700": "oklch(37.3% .034 259.733)", "800": "oklch(27.8% .033 256.848)",
    "900": "oklch(21% .034 264.665)", "950": "oklch(13% .028 261.692)",
}

# Color principal casi negro (#111827), como el sitio: botones, enlace activo, interruptores.
_NEGRO = {
    "50": "oklch(96.7% .003 264.542)", "100": "oklch(92.8% .006 264.531)", "200": "oklch(87.2% .01 258.338)",
    "300": "oklch(70.7% .022 261.325)", "400": "oklch(44.6% .03 256.802)", "500": "oklch(27.8% .033 256.848)",
    "600": "oklch(21% .034 264.665)", "700": "oklch(21% .034 264.665)", "800": "oklch(13% .028 261.692)",
    "900": "oklch(13% .028 261.692)", "950": "oklch(13% .028 261.692)",
}


def _item(titulo, icono, url, **extra):
    return {"title": titulo, "icon": icono, "link": reverse_lazy(url), **extra}


UNFOLD = {
    "SITE_TITLE": "Instinto Olfativo Admin",
    "SITE_HEADER": "Instinto Olfativo",
    "SITE_SUBHEADER": "Administración",
    "SITE_SYMBOL": "spa",
    "SITE_URL": "/",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": True,
    "THEME": "light",
    "BORDER_RADIUS": "6px",
    "DASHBOARD_CALLBACK": "catalogo.dashboard.dashboard_callback",
    "COLORS": {"base": _GRIS, "primary": _NEGRO},
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "General",
                "items": [
                    _item("Inicio", "space_dashboard", "admin:index"),
                    _item("Panel de ventas", "monitoring", "admin:panel_ventas"),
                ],
            },
            {
                "title": "Catálogo",
                "separator": True,
                "items": [
                    _item("Perfumes", "water_drop", "admin:catalogo_perfume_changelist"),
                    _item("Marcas", "sell", "admin:catalogo_marca_changelist"),
                    _item("Familias olfativas", "eco", "admin:catalogo_familiaolfativa_changelist"),
                    _item("Notas", "local_florist", "admin:catalogo_nota_changelist"),
                    _item("Reseñas", "star", "admin:catalogo_resena_changelist",
                          badge="catalogo.dashboard.badge_resenas", badge_variant="warning"),
                ],
            },
            {
                "title": "Tienda",
                "separator": True,
                "items": [
                    _item("Pedidos", "shopping_bag", "admin:catalogo_pedido_changelist",
                          badge="catalogo.dashboard.badge_pedidos", badge_variant="warning"),
                    _item("Promociones", "percent", "admin:catalogo_promocion_changelist"),
                    _item("Portadas del home", "photo_library", "admin:catalogo_imagenportada_changelist"),
                    _item("Página Nosotros", "article", "admin:catalogo_paginanosotros_changelist"),
                ],
            },
            {
                "title": "Usuarios",
                "separator": True,
                "collapsible": True,
                "items": [
                    _item("Usuarios", "person", "admin:auth_user_changelist"),
                    _item("Grupos", "group", "admin:auth_group_changelist"),
                ],
            },
        ],
    },
}
