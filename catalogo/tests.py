"""Pruebas mínimas del sitio. Corren en el CI (GitHub Actions, con PostgreSQL) en cada push.

Local:  DJANGO_SETTINGS_MODULE=core.settings_ci python manage.py test
Con SQLite se saltan las pruebas que dependen de la búsqueda de PostgreSQL.
"""
import json
import unittest
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.template import engines
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .filtros import url_filtros
from .models import FamiliaOlfativa, Marca, Nota, Pedido, Perfume, PerfumeNota, Presentacion

IMG = "perfumes/ci.jpg"
solo_postgres = unittest.skipUnless(connection.vendor == "postgresql", "requiere PostgreSQL (pg_trgm y unaccent)")


class Base(TestCase):
    """Catálogo pequeño: 3 perfumes, 4 presentaciones, 2 notas (una con 3 perfumes y otra con 1)."""

    @classmethod
    def setUpTestData(cls):
        cls.marca = Marca.objects.create(nombre="Casa Prueba")
        cls.familia = FamiliaOlfativa.objects.create(nombre="Amaderada")
        cls.vainilla = Nota.objects.create(nombre="Vainilla")
        cls.bergamota = Nota.objects.create(nombre="Bergamota")

        cls.p1 = cls._perfume("No. 101", genero="M", inspirado_en="Sauvage de Dior", concentracion="edp")
        cls.p1_decant = Presentacion.objects.create(perfume=cls.p1, formato="decant", ml=5, precio=6000, stock=10)
        cls.p1_frasco = Presentacion.objects.create(
            perfume=cls.p1, formato="frasco", ml=100, precio=25000, precio_oferta=19990, stock=3,
        )

        cls.p2 = cls._perfume("Brisa Cítrica", genero="F", concentracion="edt")
        Presentacion.objects.create(perfume=cls.p2, formato="frasco", ml=50, precio=15000, stock=5)

        cls.agotado = cls._perfume("Sin Stock", genero="U")
        cls.agotado_pres = Presentacion.objects.create(perfume=cls.agotado, formato="frasco", ml=50, precio=12000, stock=0)

        for p in (cls.p1, cls.p2, cls.agotado):
            PerfumeNota.objects.create(perfume=p, nota=cls.vainilla, nivel="fondo")
        PerfumeNota.objects.create(perfume=cls.p1, nota=cls.bergamota, nivel="salida")

        for p in (cls.p1, cls.p2, cls.agotado):
            p.refresh_from_db()

    @classmethod
    def _perfume(cls, nombre, **extra):
        return Perfume.objects.create(
            nombre=nombre, marca=cls.marca, familia=cls.familia,
            descripcion="Descripción de prueba.", precio=0, imagen=IMG, **extra,
        )

    def setUp(self):
        cache.clear()  # el límite de pedidos por IP usa la caché

    def ids(self, respuesta):
        return [p.pk for p in respuesta.context["perfumes"]]


class PaginasPublicasTests(Base):
    def test_responden_200(self):
        urls = [
            reverse("home"),
            reverse("catalogo"),
            reverse("catalogo_genero", args=["mujer"]),
            self.familia.get_absolute_url(),
            self.marca.get_absolute_url(),
            self.vainilla.get_absolute_url(),
            self.p1.get_absolute_url(),
            self.agotado.get_absolute_url(),
            reverse("contacto"),
            reverse("politicas"),
            reverse("nosotros"),
            "/robots.txt",
            "/sitemap.xml",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_genero_inexistente_404(self):
        self.assertEqual(self.client.get("/perfumes/otro/").status_code, 404)

    def test_perfume_inactivo_404(self):
        Perfume.objects.filter(pk=self.p2.pk).update(activo=False)
        self.assertEqual(self.client.get(self.p2.get_absolute_url()).status_code, 404)

    def test_url_antigua_por_id_redirige(self):
        r = self.client.get(f"/perfume/{self.p1.pk}/")
        self.assertRedirects(r, self.p1.get_absolute_url(), status_code=301, fetch_redirect_response=False)

    def test_slug_cambiado_redirige(self):
        anterior = self.p2.slug
        self.p2.slug = "brisa-nueva"
        self.p2.save()
        r = self.client.get(f"/perfume/{anterior}/")
        self.assertRedirects(r, "/perfume/brisa-nueva/", status_code=301, fetch_redirect_response=False)

    def test_catalogo_antiguo_redirige_con_filtros(self):
        r = self.client.get("/catalogo/?genero=F")
        self.assertRedirects(r, "/perfumes/?genero=F", status_code=301, fetch_redirect_response=False)

    def test_robots_bloquea_api(self):
        self.assertContains(self.client.get("/robots.txt"), "Disallow: /api/")

    def test_cache_cdn(self):
        self.assertIn("s-maxage=3600", self.client.get(reverse("catalogo"))["Cache-Control"])
        self.assertIn("private", self.client.get(reverse("catalogo"), {"q": "dior"})["Cache-Control"])


class CatalogoTests(Base):
    def test_combinaciones_de_filtros(self):
        consultas = [
            {"genero": "M", "precio": "hasta-10000", "tamano": 5, "formato": "decant"},
            {"intensidad": "intensa", "nota": self.vainilla.pk, "stock": "1", "orden": "precio-asc"},
            {"orden": "precio-desc"},
            {"orden": "nombre"},
            {"precio": "desde-20000"},
            {"familia_txt": "amader"},
            {"q": "xqzw"},
            # Valores inválidos: se ignoran, no rompen la página
            {"marca": "abc", "familia": "x", "tamano": "?", "precio": "gratis", "orden": "raro", "page": 999},
        ]
        for consulta in consultas:
            with self.subTest(consulta=consulta):
                self.assertEqual(self.client.get(reverse("catalogo"), consulta).status_code, 200)

    def test_precio_y_formato_en_la_misma_presentacion(self):
        r = self.client.get(reverse("catalogo"), {"formato": "decant", "precio": "hasta-10000"})
        self.assertEqual(self.ids(r), [self.p1.pk])
        r = self.client.get(reverse("catalogo"), {"formato": "frasco", "precio": "hasta-10000"})
        self.assertEqual(self.ids(r), [])

    def test_agotados_al_final_y_filtro_disponibles(self):
        ids = self.ids(self.client.get(reverse("catalogo")))
        self.assertEqual(ids[-1], self.agotado.pk)
        ids = self.ids(self.client.get(reverse("catalogo"), {"stock": "1"}))
        self.assertNotIn(self.agotado.pk, ids)

    def test_landing_de_nota(self):
        ids = self.ids(self.client.get(self.bergamota.get_absolute_url()))
        self.assertEqual(ids, [self.p1.pk])

    def test_nota_con_pocos_perfumes_noindex_y_fuera_del_sitemap(self):
        noindex = 'content="noindex,follow"'
        self.assertContains(self.client.get(self.bergamota.get_absolute_url()), noindex)
        self.assertNotContains(self.client.get(self.vainilla.get_absolute_url()), noindex)
        sitemap = self.client.get("/sitemap.xml")
        self.assertContains(sitemap, self.vainilla.get_absolute_url())
        self.assertNotContains(sitemap, self.bergamota.get_absolute_url())

    @solo_postgres
    def test_busqueda_tolera_errores(self):
        self.assertIn(self.p1.pk, self.ids(self.client.get(reverse("catalogo"), {"q": "sauvaje"})))

    @solo_postgres
    def test_busqueda_sin_tildes(self):
        ids = self.ids(self.client.get(reverse("catalogo"), {"q": "citrica"}))
        self.assertIn(self.p2.pk, ids)
        self.assertNotIn(self.p1.pk, ids)

    @solo_postgres
    def test_api_buscar(self):
        datos = self.client.get(reverse("api_buscar"), {"q": "sauvaje"}).json()
        self.assertIn("No. 101", [r["nombre"] for r in datos["resultados"]])
        self.assertTrue(datos["ver_todos"].startswith(reverse("catalogo")))


class PedidoTests(Base):
    def pedir(self, items, **extra):
        cuerpo = json.dumps({"items": items, "cliente": "CI", **extra})
        return self.client.post(reverse("crear_pedido"), data=cuerpo, content_type="application/json")

    def test_usa_el_precio_del_servidor(self):
        r = self.pedir([{"id": f"v-{self.p1_frasco.pk}", "qty": 2, "precio": 1}])
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertEqual(datos["total"], 19990 * 2)
        pedido = Pedido.objects.get(pk=datos["pedido_id"])
        self.assertEqual(pedido.estado, "pendiente")
        self.assertEqual(pedido.codigo, datos["codigo"])

    def test_id_de_perfume_usa_la_presentacion_mas_barata(self):
        self.assertEqual(self.pedir([{"id": str(self.p1.pk)}]).json()["total"], 6000)

    def test_cantidad_maxima_por_linea(self):
        self.assertEqual(self.pedir([{"id": f"v-{self.p1_decant.pk}", "qty": 999}]).json()["total"], 6000 * 10)

    def test_no_descuenta_stock_al_crear(self):
        self.pedir([{"id": f"v-{self.p1_decant.pk}", "qty": 3}])
        self.p1_decant.refresh_from_db()
        self.assertEqual(self.p1_decant.stock, 10)

    def test_rechaza_agotados_y_datos_basura(self):
        r = self.pedir([{"id": f"v-{self.agotado_pres.pk}"}, {"id": "hack"}, "x", {"id": "v-999999"}])
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Pedido.objects.exists())

    def test_json_invalido(self):
        r = self.client.post(reverse("crear_pedido"), data="no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_solo_post(self):
        self.assertEqual(self.client.get(reverse("crear_pedido")).status_code, 405)

    def test_limite_por_ip(self):
        item = [{"id": f"v-{self.p1_decant.pk}"}]
        for _ in range(5):
            self.assertEqual(self.pedir(item).status_code, 200)
        self.assertEqual(self.pedir(item).status_code, 429)


class ModelosTests(Base):
    def test_resumen_desde_presentaciones(self):
        self.assertEqual(self.p1.precio, 6000)
        self.assertEqual(self.p1.n_presentaciones, 2)
        self.assertEqual(self.p1.stock, 13)
        self.assertTrue(self.p1.es_oferta)
        self.assertEqual(self.agotado.stock, 0)

    def test_resumen_se_actualiza_al_cambiar_stock(self):
        self.agotado_pres.stock = 4
        self.agotado_pres.save()
        self.agotado.refresh_from_db()
        self.assertEqual(self.agotado.stock, 4)

    def test_piramide_sincroniza_campos_de_texto(self):
        self.assertEqual(self.p1.notas_salida, "Bergamota")
        self.assertEqual(self.p1.notas_fondo, "Vainilla")
        self.assertEqual(self.p1.notas_corazon, "")

    def test_slugs_unicos(self):
        otro = self._perfume("No. 101")
        self.assertNotEqual(otro.slug, self.p1.slug)


class UrlFiltrosTests(SimpleTestCase):
    def test_un_solo_genero_va_a_su_landing(self):
        self.assertEqual(url_filtros({}, {}, genero="F"), "/perfumes/mujer/")

    def test_mismo_valor_quita_el_filtro(self):
        self.assertEqual(url_filtros({"genero": "F"}, {}, genero="F"), "/perfumes/")

    def test_varios_filtros_en_orden_estable(self):
        self.assertEqual(
            url_filtros({"precio": "hasta-10000"}, {}, genero="M"),
            "/perfumes/?genero=M&precio=hasta-10000",
        )

    def test_una_nota_va_a_su_landing(self):
        self.assertEqual(url_filtros({}, {"nota": {"3": "vainilla"}}, nota=3), "/nota/vainilla/")

    def test_cambiar_filtro_quita_la_pagina(self):
        self.assertEqual(url_filtros({"page": 4, "orden": "nombre"}, {}), "/perfumes/?orden=nombre")


class PlantillasTests(SimpleTestCase):
    def test_todas_las_plantillas_compilan(self):
        motor = engines["django"]
        raiz = Path(settings.BASE_DIR) / "templates"
        for ruta in sorted(raiz.rglob("*.html")):
            nombre = ruta.relative_to(raiz).as_posix()
            with self.subTest(plantilla=nombre):
                motor.get_template(nombre)


class PromocionesTests(Base):
    def crear(self, **datos):
        from .models import Promocion
        datos.setdefault("precio", 1000)
        return Promocion.objects.create(**datos)

    def test_vigencia_y_tema_en_el_home(self):
        from datetime import timedelta
        from django.utils import timezone
        hoy = timezone.localdate()
        self.crear(titulo="Vencida", tema="navidad", fecha_fin=hoy - timedelta(days=1))
        self.crear(titulo="Futura", tema="navidad", fecha_inicio=hoy + timedelta(days=1))
        self.crear(titulo="Dúo Navidad", tema="navidad", precio=12900, precio_normal=16000, fecha_fin=hoy)
        r = self.client.get(reverse("home"))
        self.assertEqual([p.titulo for p in r.context["promociones"]], ["Dúo Navidad"])
        self.assertEqual(r.context["tema_promos"], "navidad")
        self.assertContains(r, "Especial de Navidad")
        self.assertContains(r, "-19%")

    def test_temas_mezclados_usan_encabezado_neutro(self):
        self.crear(titulo="A", tema="navidad")
        self.crear(titulo="B", tema="black")
        r = self.client.get(reverse("home"))
        self.assertEqual(r.context["tema_promos"], "especial")
        self.assertContains(r, "Ofertas especiales")

    def test_etiqueta_generica_muestra_el_tema(self):
        self.assertEqual(self.crear(titulo="A", tema="madre").texto_etiqueta, "Día de la Madre")
        self.assertEqual(self.crear(titulo="B", tema="madre", etiqueta="2x1").texto_etiqueta, "2x1")

    def test_validaciones(self):
        from datetime import date
        from django.core.exceptions import ValidationError
        from .models import Promocion
        with self.assertRaises(ValidationError):
            Promocion(titulo="x", precio=5000, precio_normal=4000).full_clean()
        with self.assertRaises(ValidationError):
            Promocion(titulo="x", precio=5000, fecha_inicio=date(2026, 12, 24), fecha_fin=date(2026, 12, 1)).full_clean()

    def test_promocion_vencida_no_se_puede_pedir(self):
        from datetime import timedelta
        from django.utils import timezone
        vencida = self.crear(titulo="Vencida", fecha_fin=timezone.localdate() - timedelta(days=1))
        cuerpo = json.dumps({"items": [{"id": f"promo-{vencida.pk}"}], "cliente": "CI"})
        r = self.client.post(reverse("crear_pedido"), data=cuerpo, content_type="application/json")
        self.assertEqual(r.status_code, 400)


class AdminUnfoldTests(TestCase):
    """Las pantallas principales del admin cargan con Unfold."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_superuser("admin-ci", "ci@example.com", "x"))

    def test_pantallas_cargan(self):
        for nombre in ("admin:index", "admin:panel_ventas", "admin:catalogo_perfume_changelist",
                       "admin:catalogo_perfume_add", "admin:catalogo_promocion_add",
                       "admin:catalogo_pedido_changelist", "admin:auth_user_changelist"):
            with self.subTest(nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_inicio_muestra_resumen(self):
        r = self.client.get(reverse("admin:index"))
        self.assertContains(r, "Pedidos por confirmar")
        self.assertContains(r, "Nueva promoción")


class SeguridadSemana1Tests(TestCase):
    """Límites compartidos por IP, formulario de contacto protegido y JSON escapado."""

    def setUp(self):
        from django.core import mail
        mail.outbox = []

    def _contacto(self, **extra):
        datos = {"nombre": "Ana Pérez", "email": "ana@example.com", "mensaje": "Hola, ¿tienen Eclaire?"}
        datos.update(extra)
        return self.client.post(reverse("contacto"), datos, REMOTE_ADDR="203.0.113.7")

    def test_limite_se_guarda_sin_la_ip(self):
        from django.test import RequestFactory
        from .limites import excede_limite
        from .models import LimiteSolicitud
        req = RequestFactory().post("/", REMOTE_ADDR="198.51.100.4")
        self.assertEqual([excede_limite(req, "prueba", 2, 600) for _ in range(3)], [False, False, True])
        self.assertFalse(LimiteSolicitud.objects.filter(clave__contains="198.51.100.4").exists())

    def test_contacto_envia_con_responder_al_cliente(self):
        from django.core import mail
        r = self._contacto()
        self.assertRedirects(r, reverse("contacto"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ["ana@example.com"])

    def test_contacto_campo_trampa_no_envia(self):
        from django.core import mail
        self._contacto(sitio_web="http://spam.example")
        self.assertEqual(len(mail.outbox), 0)

    def test_contacto_email_invalido_no_envia(self):
        from django.core import mail
        r = self._contacto(email="no-es-un-correo")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_contacto_limite_por_ip(self):
        from django.core import mail
        for _ in range(5):
            self._contacto()
        self.assertEqual(len(mail.outbox), 3)

    def test_contacto_nombre_sin_saltos_de_linea(self):
        from django.core import mail
        self._contacto(nombre="Ana\nBcc: otro@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("\n", mail.outbox[0].subject)

    def test_home_usa_json_script(self):
        # El bloque del test olfativo solo se dibuja si hay familias con perfumes activos;
        # basta con comprobar que la vista entrega datos (no texto JSON) para json_script.
        r = self.client.get(reverse("home"))
        self.assertIsInstance(r.context["familias_data"], list)
        self.assertNotIn("familias_data|safe", Path(settings.BASE_DIR, "templates", "home.html").read_text(encoding="utf-8"))


class TextosLegalesTests(TestCase):
    """Páginas legales publicadas y enlazadas, con los datos del vendedor visibles."""

    def test_paginas_cargan(self):
        for nombre, texto in (("terminos", "Derecho de retracto"), ("privacidad", "Tus derechos")):
            with self.subTest(nombre):
                self.assertContains(self.client.get(reverse(nombre)), texto)

    def test_pie_con_vendedor_y_enlaces(self):
        r = self.client.get(reverse("politicas"))
        self.assertContains(r, reverse("terminos"))
        self.assertContains(r, reverse("privacidad"))
        self.assertContains(r, "pertenecen a sus respectivos titulares")

    def test_aviso_en_contacto(self):
        self.assertContains(self.client.get(reverse("contacto")), reverse("privacidad"))

    def test_sitemap_incluye_paginas_legales(self):
        r = self.client.get("/sitemap.xml")
        self.assertContains(r, "/terminos/")
        self.assertContains(r, "/privacidad/")


class ConsentimientoYPromocionesTests(TestCase):
    def test_sin_ids_no_hay_aviso_ni_pixeles(self):
        r = self.client.get(reverse("politicas"))
        self.assertNotContains(r, 'id="io-cookies"')
        self.assertNotContains(r, "fbevents.js")

    def test_con_id_el_pixel_espera_consentimiento(self):
        from django.test import override_settings
        with override_settings(META_PIXEL_ID="123456789"):
            r = self.client.get(reverse("politicas"))
        self.assertContains(r, 'id="io-cookies"')
        self.assertContains(r, "Rechazar")
        self.assertNotContains(r, "<script async src=\"https://connect.facebook.net")

    def test_promocion_exige_fecha_o_unidades(self):
        from datetime import date
        from django.core.exceptions import ValidationError
        from .models import Promocion
        with self.assertRaises(ValidationError):
            Promocion(titulo="x", precio=5000).full_clean()
        Promocion(titulo="x", precio=5000, unidades=20).full_clean()
        Promocion(titulo="x", precio=5000, fecha_fin=date(2026, 12, 24)).full_clean()

    def test_tarjeta_muestra_unidades(self):
        from .models import Promocion
        Promocion.objects.create(titulo="Dúo", precio=5000, unidades=20)
        self.assertContains(self.client.get(reverse("home")), "Hasta agotar 20 unidades")

    def test_mapa_carga_al_clic(self):
        self.assertNotContains(self.client.get(reverse("contacto")), '<iframe')


class CSPEstrictaTests(TestCase):
    def directiva(self, csp, nombre):
        for d in csp.split(";"):
            partes = d.split()
            if partes and partes[0] == nombre:
                return d
        return ""

    def test_csp_del_sitio_sin_unsafe_inline(self):
        csp = self.client.get(reverse("home"))["Content-Security-Policy"]
        self.assertIn("default-src 'none'", csp)
        self.assertNotIn("'unsafe-inline'", self.directiva(csp, "script-src"))
        self.assertNotIn("'unsafe-inline'", self.directiva(csp, "style-src"))
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertIn("object-src 'none'", csp)

    def test_nonce_de_la_cabecera_coincide_con_el_html(self):
        import re
        r = self.client.get(reverse("home"))
        nonce = re.search(r"'nonce-([^']+)'", r["Content-Security-Policy"]).group(1)
        self.assertIn(f'nonce="{nonce}"', r.content.decode())

    def test_nonce_cambia_en_cada_respuesta(self):
        a = self.client.get(reverse("home"))["Content-Security-Policy"]
        b = self.client.get(reverse("home"))["Content-Security-Policy"]
        self.assertNotEqual(a, b)

    def test_sin_handlers_inline(self):
        import re
        for nombre in ("home", "contacto"):
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertIsNone(re.search(r"\son[a-z]+\s*=\s*[\"']", html), nombre)

    def test_cabeceras_cross_origin(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r["Cross-Origin-Resource-Policy"], "same-site")
        self.assertEqual(r["Cross-Origin-Opener-Policy"], "same-origin")


class SEOTests(TestCase):
    def test_home_metadatos(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('lang="es-CL"', html)
        for etiqueta in ('property="og:image"', 'property="og:site_name"', 'name="twitter:card"', '"@type":"WebSite"'):
            self.assertIn(etiqueta, html)

    def test_descripciones_distintas(self):
        import re
        def desc(nombre):
            html = self.client.get(reverse(nombre)).content.decode()
            return re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        valores = [desc(n) for n in ("home", "catalogo", "contacto", "nosotros")]
        self.assertEqual(len(set(valores)), len(valores))

    def test_404_propio_y_noindex(self):
        r = self.client.get("/esta-pagina-no-existe/")
        self.assertEqual(r.status_code, 404)
        self.assertIn("Página no encontrada", r.content.decode())
        self.assertIn('name="robots" content="noindex"', r.content.decode())

    def test_sitemap_con_imagenes(self):
        r = self.client.get("/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.decode().startswith("<?xml"))
        self.assertIn("sitemap-image", r.content.decode())

    def test_titulo_seo(self):
        from types import SimpleNamespace as N
        from catalogo.templatetags.seo import titulo_seo
        corto = N(meta_titulo="", nombre="Oud 21", inspirado_en="Oud Wood")
        largo = N(meta_titulo="", nombre="Smart Collection No. 387", inspirado_en="Bleu de Chanel Eau de Parfum")
        self.assertEqual(titulo_seo(corto), "Oud 21 – Inspirado en Oud Wood | Instinto Olfativo")
        self.assertNotIn("Instinto Olfativo", titulo_seo(largo))
        self.assertEqual(titulo_seo(N(meta_titulo="Manual", nombre="X", inspirado_en="")), "Manual")


class SEOSegundaRondaTests(TestCase):
    def test_home_sin_problemas_del_reporte(self):
        import re
        html = self.client.get(reverse("home")).content.decode()
        titulo = re.search(r"<title>([^<]*)</title>", html).group(1)
        self.assertLessEqual(len(titulo), 60)
        self.assertNotIn("<h3 data-test", html)
        self.assertIsNone(re.search(r"<h[1-6][^>]*>\s*</h[1-6]>", html))
        self.assertIn("js/base.js", html)
        self.assertNotIn("const btnMenu", html)

    def test_imagenes_con_src_y_alt(self):
        import re
        html = self.client.get(reverse("home")).content.decode()
        for img in re.findall(r"<img\b[^>]*>", html):
            self.assertRegex(img, r'\bsrc="[^"]+"', img)
            self.assertRegex(img, r'\balt="[^"]+"', img)

    def test_google_site_verification(self):
        from django.test import override_settings
        with override_settings(GOOGLE_SITE_VERIFICATION="abc123"):
            html = self.client.get(reverse("contacto")).content.decode()
        self.assertIn('name="google-site-verification" content="abc123"', html)


# ---------- seo3: meta descripciones y JavaScript minificado ----------
import html as _html
import re as _re

from django.test import SimpleTestCase


class SEO3Tests(TestCase):
    def descripcion(self, url):
        html = self.client.get(url).content.decode()
        m = _re.search(r'<meta name="description" content="([^"]*)"', html)
        self.assertIsNotNone(m, f"{url} sin meta description")
        return _html.unescape(m.group(1))

    def test_descripciones_hasta_160_caracteres(self):
        for nombre in ("home", "catalogo", "nosotros"):
            with self.subTest(nombre):
                d = self.descripcion(reverse(nombre))
                self.assertLessEqual(len(d), 160, f"{nombre}: {len(d)} caracteres")
                self.assertGreaterEqual(len(d), 70, f"{nombre}: {len(d)} caracteres")


class JSMinificadoTests(SimpleTestCase):
    def test_js_publicado_es_el_minificado_de_src(self):
        from minificar_js import DEST, SRC, minificar
        fuentes = sorted(SRC.glob("*.js"))
        self.assertTrue(fuentes, "static/js/src/ está vacío")
        for f in fuentes:
            with self.subTest(f.name):
                self.assertEqual(
                    (DEST / f.name).read_text(encoding="utf-8"),
                    minificar(f.read_text(encoding="utf-8")),
                    f"static/js/{f.name} no coincide con src/: corre python minificar_js.py",
                )
