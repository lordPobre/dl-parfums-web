from django.test import TestCase
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
from django.test import SimpleTestCase, TestCase, override_settings
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


@override_settings(PEDIDO_EXIGE_DATOS=False)
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


@override_settings(PEDIDO_EXIGE_DATOS=False)
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
        entrar_admin_verificado(self.client, User.objects.create_superuser("admin-ci", "ci@example.com", "x"))

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
        self.assertRegex(html, r"js/base(\.[0-9a-f]{12})?\.js")  # con o sin hash del manifiesto
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



# ---------- movil-rendimiento: fuentes locales e imágenes a su tamaño ----------
import re as _re_mr

from django.contrib.staticfiles import finders as _finders_mr


class RendimientoMovilTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse("home")).content.decode()

    def test_sin_google_fonts(self):
        self.assertNotIn("fonts.googleapis.com", self.html)
        self.assertNotIn("fonts.gstatic.com", self.html)

    def test_fuentes_precargadas_existen(self):
        fuentes = _re_mr.findall(r'href="[^"]*/fonts/([^"/]+\.woff2)"[^>]*as="font"', self.html)
        self.assertTrue(fuentes, 'falta <link rel="preload" as="font">')
        for f in fuentes:
            f = _re_mr.sub(r"\.[0-9a-f]{12}(?=\.woff2$)", "", f)  # nombre con hash del manifest
            with self.subTest(f):
                self.assertIsNotNone(_finders_mr.find(f"fonts/{f}"), f"falta static/fonts/{f}")

    def test_logo_e_icono_webp_con_tamano(self):
        imgs = _re_mr.findall(r"<img\b[^>]*(?:logo-instinto|icono-gota)[^>]*>", self.html)
        self.assertTrue(imgs)
        for tag in imgs:
            with self.subTest(tag[:90]):
                self.assertNotIn(".png", tag)
                self.assertRegex(tag, r'\swidth="\d+"')
                self.assertRegex(tag, r'\sheight="\d+"')


def entrar_admin_verificado(client, usuario):
    """Inicia sesión con el segundo factor ya validado (para pruebas del admin)."""
    from django_otp import DEVICE_ID_SESSION_KEY
    from django_otp.plugins.otp_totp.models import TOTPDevice
    dispositivo = TOTPDevice.objects.create(user=usuario, name="pruebas", confirmed=True)
    client.force_login(usuario)
    sesion = client.session
    sesion[DEVICE_ID_SESSION_KEY] = dispositivo.persistent_id
    sesion.save()


class Admin2FATests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.usuario = User.objects.create_superuser("admin-2fa", "2fa@example.com", "x")
        self.inicio = reverse("admin:index")

    def test_sin_dispositivo_pide_configurar(self):
        self.client.force_login(self.usuario)
        r = self.client.get(self.inicio)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("admin2fa_configurar")))

    def test_configurar_con_qr_y_codigos_de_respaldo(self):
        from django_otp.oath import totp
        from django_otp.plugins.otp_totp.models import TOTPDevice
        import io
        from django.core.management import call_command
        call_command("autorizar_2fa", self.usuario.username, stdout=io.StringIO())
        self.client.force_login(self.usuario)
        r = self.client.get(reverse("admin2fa_configurar"))
        self.assertContains(r, "data:image/svg+xml;base64,")
        d = TOTPDevice.objects.get(user=self.usuario)
        r = self.client.post(reverse("admin2fa_configurar"), {"codigo": f"{totp(d.bin_key):06d}"})
        self.assertContains(r, "Códigos de respaldo")
        d.refresh_from_db()
        self.assertTrue(d.confirmed)
        self.assertEqual(self.client.get(self.inicio).status_code, 200)

    def test_con_dispositivo_pide_codigo(self):
        from django_otp.oath import totp
        from django_otp.plugins.otp_totp.models import TOTPDevice
        d = TOTPDevice.objects.create(user=self.usuario, name="app", confirmed=True)
        self.client.force_login(self.usuario)
        r = self.client.get(self.inicio)
        self.assertTrue(r["Location"].startswith(reverse("admin2fa_verificar")))
        malo = f"{(totp(d.bin_key) + 1) % 1000000:06d}"
        self.assertContains(self.client.post(reverse("admin2fa_verificar"), {"codigo": malo}), "Código incorrecto")
        d.throttle_reset()
        r = self.client.post(reverse("admin2fa_verificar"), {"codigo": f"{totp(d.bin_key):06d}"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(self.inicio).status_code, 200)

    def test_codigo_de_respaldo_sirve_una_vez(self):
        from django_otp.plugins.otp_static.models import StaticDevice
        d = StaticDevice.objects.create(user=self.usuario, name="respaldo", confirmed=True)
        d.token_set.create(token="abcd2345")
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(reverse("admin2fa_verificar"), {"codigo": "abcd2345"}).status_code, 302)
        self.client.logout()
        self.client.force_login(self.usuario)
        self.assertContains(self.client.post(reverse("admin2fa_verificar"), {"codigo": "abcd2345"}), "Código incorrecto")

    def test_sitio_publico_no_cambia(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get("/").status_code, 200)


@override_settings(PEDIDO_EXIGE_DATOS=False)
class CombosTests(Base):
    """Combo automático: 2 Smart Collection de 25 o 30 ml por $10.000 (cada uno vale $6.000)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from .models import Promocion
        cls.sc1 = cls._perfume("Smart Collection No.540", inspirado_en="Baccarat Rouge 540")
        cls.sc1_25 = Presentacion.objects.create(perfume=cls.sc1, formato="frasco", ml=25, precio=6000, stock=10)
        cls.sc1_30 = Presentacion.objects.create(perfume=cls.sc1, formato="frasco", ml=30, precio=6000, stock=10)
        cls.sc1_100 = Presentacion.objects.create(perfume=cls.sc1, formato="frasco", ml=100, precio=20000, stock=10)
        cls.sc2 = cls._perfume("Smart Collection No.475", inspirado_en="Good Girl de Carolina Herrera")
        cls.sc2_30 = Presentacion.objects.create(perfume=cls.sc2, formato="frasco", ml=30, precio=6000, stock=10)
        cls.promo = Promocion.objects.create(
            titulo="2 Smart Collection por $10.000", precio=10000, unidades=50,
            combo_cantidad=2, combo_ml="25,30", combo_nombre="Smart Collection",
        )

    def pedir(self, *pares):
        items = [{"id": f"v-{p.pk}", "qty": q} for p, q in pares]
        r = self.client.post(reverse("crear_pedido"), data=json.dumps({"items": items}), content_type="application/json")
        return r.json()

    def test_dos_smart_salen_a_10000(self):
        d = self.pedir((self.sc1_30, 1), (self.sc2_30, 1))
        self.assertEqual((d["total"], d["descuento"]), (10000, 2000))
        pedido = Pedido.objects.get(pk=d["pedido_id"])
        self.assertEqual(pedido.descuento, 2000)
        self.assertIn("2 Smart Collection", pedido.detalle_descuento)

    def test_mezcla_25_y_30_y_misma_linea(self):
        self.assertEqual(self.pedir((self.sc1_25, 1), (self.sc2_30, 1))["total"], 10000)
        self.assertEqual(self.pedir((self.sc2_30, 2))["total"], 10000)

    def test_impar_paga_el_ultimo_normal(self):
        self.assertEqual(self.pedir((self.sc1_30, 2), (self.sc2_30, 1))["total"], 16000)
        self.assertEqual(self.pedir((self.sc1_30, 2), (self.sc2_30, 2))["total"], 20000)

    def test_otros_tamanos_y_perfumes_no_califican(self):
        self.assertEqual(self.pedir((self.sc1_100, 1), (self.sc2_30, 1))["total"], 26000)
        self.assertEqual(self.pedir((self.sc2_30, 1), (self.p1_decant, 1))["total"], 12000)

    def test_combo_vencido_no_descuenta(self):
        from datetime import timedelta
        from django.utils import timezone
        type(self.promo).objects.filter(pk=self.promo.pk).update(fecha_fin=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.pedir((self.sc1_30, 1), (self.sc2_30, 1))["total"], 12000)

    def test_combo_no_se_pide_como_linea(self):
        cuerpo = json.dumps({"items": [{"id": f"promo-{self.promo.pk}"}]})
        r = self.client.post(reverse("crear_pedido"), data=cuerpo, content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_pedido_guarda_inspirado_en(self):
        d = self.pedir((self.sc1_30, 1))
        item = Pedido.objects.get(pk=d["pedido_id"]).items.get()
        self.assertIn("inspirado en Baccarat Rouge 540", item.nombre)

    def test_cotizar(self):
        r = self.client.get(reverse("api_cotizar"), {"i": f"v-{self.sc1_30.pk}:1,v-{self.sc2_30.pk}:1,hack"})
        d = r.json()
        self.assertEqual((d["subtotal"], d["descuento"], d["total"]), (12000, 2000, 10000))
        self.assertEqual(d["lineas"][0]["insp"], "Baccarat Rouge 540")
        self.assertEqual(d["detalle"][0]["combos"], 1)

    def test_validaciones_combo(self):
        from django.core.exceptions import ValidationError
        from .models import Promocion
        with self.assertRaises(ValidationError):
            Promocion(titulo="x", precio=10000, unidades=5, combo_cantidad=1).full_clean()
        with self.assertRaises(ValidationError):
            Promocion(titulo="x", precio=10000, unidades=5, combo_cantidad=2, combo_ml="25 ml").full_clean()


# ---------- seguridad-critica: respaldo cifrado, carrito, WhatsApp y admin ----------
@override_settings(PEDIDO_EXIGE_DATOS=False)
class SeguridadCriticaTests(Base):
    def test_respaldo_cifrado_y_sin_sesiones(self):
        yml = Path(settings.BASE_DIR, ".github", "workflows", "respaldo.yml").read_text(encoding="utf-8")
        self.assertIn("--exclude-table-data=django_session", yml)
        self.assertIn('age -r "$AGE_PUBLICA"', yml)
        self.assertIn("path: respaldo.dump.age", yml)
        self.assertNotIn("path: respaldo.dump\n", yml)

    def test_pedido_devuelve_lineas_con_precio_del_servidor(self):
        cuerpo = json.dumps({"items": [{"id": f"v-{self.p1_frasco.pk}", "qty": 2, "precio": 1, "nombre": "<b>x</b>"}]})
        d = self.client.post(reverse("crear_pedido"), data=cuerpo, content_type="application/json").json()
        self.assertEqual(len(d["lineas"]), 1)
        self.assertEqual((d["lineas"][0]["precio"], d["lineas"][0]["cantidad"]), (19990, 2))
        self.assertIn("No. 101", d["lineas"][0]["nombre"])
        self.assertNotIn("<b>", d["lineas"][0]["nombre"])

    def test_carrito_escapa_textos_y_usa_precios_del_servidor(self):
        js = Path(settings.BASE_DIR, "static", "js", "src", "base.js").read_text(encoding="utf-8")
        for fragmento in ("esc(i.nombre)", "esc(i.marca)", "esc(i.img)", "function limpiar(",
                          "mensaje(d) : local()", "precios[l.id] = l.precio"):
            with self.subTest(fragmento):
                self.assertIn(fragmento, js)
        self.assertNotIn("+ i.nombre + '</h4>'", js)
        self.assertNotIn("fmt(i.precio));", js)  # el mensaje ya no usa precios del navegador

    def test_admin_sin_cdn_externo(self):
        from django.contrib.staticfiles import finders
        from core.security_headers import CSP_ADMIN
        self.assertNotIn("jsdelivr", CSP_ADMIN)
        html = Path(settings.BASE_DIR, "templates", "admin", "panel_ventas.html").read_text(encoding="utf-8")
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertIsNotNone(finders.find("vendor/chart-4.4.1.umd.min.js"))

    def test_sesion_de_8_horas_y_contrasenas_de_12(self):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        self.assertEqual(settings.SESSION_COOKIE_AGE, 8 * 3600)
        with self.assertRaises(ValidationError):
            validate_password("Perfume2026")  # 11 caracteres

    def test_limite_cuenta_tambien_los_rechazados(self):
        from django.test import RequestFactory
        from .limites import excede_limite
        req = RequestFactory().post("/", REMOTE_ADDR="198.51.100.9")
        self.assertEqual([excede_limite(req, "prueba-s12", 2, 600) for _ in range(4)], [False, False, True, True])


class Alta2FAAutorizadaTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.usuario = User.objects.create_user("staff-nuevo", "s@example.com", "x", is_staff=True)
        self.client.force_login(self.usuario)

    def test_sin_autorizacion_no_muestra_qr(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        r = self.client.get(reverse("admin2fa_configurar"))
        self.assertContains(r, "autorizarlo un administrador")
        self.assertNotContains(r, "data:image/svg+xml;base64,")
        self.assertFalse(TOTPDevice.objects.filter(user=self.usuario).exists())

    def test_con_autorizacion_registra_y_sale_del_grupo(self):
        import io
        from django.core.management import call_command
        from django_otp.oath import totp
        from django_otp.plugins.otp_totp.models import TOTPDevice
        from core.admin_2fa import GRUPO_ALTA
        call_command("autorizar_2fa", "staff-nuevo", stdout=io.StringIO())
        r = self.client.get(reverse("admin2fa_configurar"))
        self.assertContains(r, "data:image/svg+xml;base64,")
        d = TOTPDevice.objects.get(user=self.usuario)
        self.assertContains(self.client.post(reverse("admin2fa_configurar"), {"codigo": f"{totp(d.bin_key):06d}"}),
                            "Códigos de respaldo")
        self.assertFalse(self.usuario.groups.filter(name=GRUPO_ALTA).exists())

    def test_reiniciar_borra_el_dispositivo_anterior(self):
        import io
        from django.core.management import call_command
        from django_otp.plugins.otp_totp.models import TOTPDevice
        TOTPDevice.objects.create(user=self.usuario, name="teléfono perdido", confirmed=True)
        call_command("autorizar_2fa", "staff-nuevo", "--reiniciar", stdout=io.StringIO())
        self.assertFalse(TOTPDevice.objects.filter(user=self.usuario).exists())


# ---------- datos-pedido: datos del cliente y aviso por correo ----------
from unittest import mock as _mock_dp

from django.test import override_settings as _override_dp


@_override_dp(PEDIDO_CORREO_SINCRONO=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DatosPedidoTests(Base):
    DATOS = {
        "nombre": "Ana", "apellido": "Pérez Soto", "rut": "11111111-1", "telefono": "+56 9 1234 5678",
        "email": "ana@example.com", "region": "Los Lagos", "comuna": "Castro",
        "direccion": "Calle Falsa 123, depto 4", "notas": "Dejar en conserjería",
    }

    def setUp(self):
        super().setUp()
        from django.core import mail
        mail.outbox = []
        limite = _mock_dp.patch("catalogo.views._excede_limite", return_value=False)
        limite.start()
        self.addCleanup(limite.stop)

    def pedir(self, **cambios):
        cuerpo = json.dumps({"items": [{"id": f"v-{self.p1_frasco.pk}", "qty": 1}], "cliente": {**self.DATOS, **cambios}})
        return self.client.post(reverse("crear_pedido"), data=cuerpo, content_type="application/json")

    def test_guarda_datos_y_avisa_solo_a_la_tienda(self):
        from django.core import mail
        d = self.pedir().json()
        p = Pedido.objects.get(pk=d["pedido_id"])
        self.assertEqual((p.cliente, p.apellido, p.rut, p.telefono, p.region, p.comuna),
                         ("Ana", "Pérez Soto", "11.111.111-1", "+56 9 1234 5678", "Los Lagos", "Castro"))
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn(p.codigo, correo.subject)
        self.assertNotIn("ana@example.com", correo.to)
        self.assertEqual(correo.reply_to, ["ana@example.com"])
        for texto in ("11.111.111-1", "Calle Falsa 123", "Castro", "Los Lagos", "conserjería", "No. 101", "19.990"):
            self.assertIn(texto, correo.body)

    def test_campos_obligatorios(self):
        from django.core import mail
        for campo in ("nombre", "apellido", "rut", "telefono", "email", "region", "comuna", "direccion"):
            with self.subTest(campo):
                r = self.pedir(**{campo: ""})
                self.assertEqual(r.status_code, 400)
                self.assertIn(campo, r.json()["errores"])
        self.assertEqual(self.pedir(notas="").status_code, 200)
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_sin_datos_no_crea_pedido(self):
        cuerpo = json.dumps({"items": [{"id": f"v-{self.p1_frasco.pk}"}]})
        r = self.client.post(reverse("crear_pedido"), data=cuerpo, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Pedido.objects.exists())

    def test_valores_invalidos(self):
        casos = {"rut": "11111111-2", "telefono": "1234", "region": "Narnia", "email": "no-es-correo"}
        for campo, valor in casos.items():
            with self.subTest(campo):
                r = self.pedir(**{campo: valor})
                self.assertEqual(r.status_code, 400)
                self.assertIn(campo, r.json()["errores"])

    def test_formatos(self):
        from .forms import formatear_rut, formatear_telefono
        self.assertEqual(formatear_rut("1000005k"), "1.000.005-K")
        self.assertEqual(formatear_rut("12.345.678-5"), "12.345.678-5")
        self.assertIsNone(formatear_rut("12.345.678-0"))
        self.assertEqual(formatear_telefono("912345678"), "+56 9 1234 5678")
        self.assertEqual(formatear_telefono("+56 9 1234 5678"), "+56 9 1234 5678")

    def test_saltos_de_linea_no_llegan_al_asunto(self):
        from django.core import mail
        self.pedir(nombre="Ana\nBcc: otro@example.com")
        self.assertNotIn("\n", mail.outbox[0].subject)

    def test_si_el_correo_falla_el_pedido_igual_se_crea(self):
        with _mock_dp.patch("catalogo.pedido_correo.EmailMessage.send", side_effect=OSError("Resend caído")):
            with self.assertLogs("catalogo.pedido_correo", "ERROR"):
                r = self.pedir()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Pedido.objects.filter(rut="11.111.111-1").exists())

    def test_carrito_pide_los_datos(self):
        html = Path(settings.BASE_DIR, "templates", "base.html").read_text(encoding="utf-8")
        js = Path(settings.BASE_DIR, "static", "js", "src", "base.js").read_text(encoding="utf-8")
        self.assertIn('id="cart-datos"', html)
        self.assertIn("cliente: datos", js)
        from .forms import REGIONES
        for region in REGIONES:
            self.assertIn(f"<option>{region}</option>", html)


# ---------- ingenieria-semana1: stock, consultas, healthcheck, logs y panel de ventas ----------
from datetime import date as _date_is, datetime as _datetime_is
from unittest import mock as _mock_is
from zoneinfo import ZoneInfo as _ZoneInfo_is

from django.db import connection as _connection_is
from django.test.utils import CaptureQueriesContext as _Captura_is
from django.utils import timezone as _tz_is

from .admin import descontar_stock, devolver_stock
from .models import ItemPedido, Resena


class StockTests(Base):
    """Aprobar descuenta stock una sola vez; rechazar lo repone una sola vez."""

    def pedido(self, *lineas):
        p = Pedido.objects.create(estado="pendiente")
        for pres, cantidad in lineas:
            ItemPedido.objects.create(pedido=p, perfume=pres.perfume, presentacion=pres, nombre=str(pres),
                                      precio=pres.precio_vigente, cantidad=cantidad)
        return p

    def stock(self, pres):
        pres.refresh_from_db()
        return pres.stock

    def test_aprobar_descuenta_y_actualiza_el_perfume(self):
        p = self.pedido((self.p1_decant, 2), (self.p1_frasco, 1))
        self.assertEqual(descontar_stock(p.pk), (True, []))
        self.assertEqual((self.stock(self.p1_decant), self.stock(self.p1_frasco)), (8, 2))
        p.refresh_from_db()
        self.assertEqual((p.estado, p.stock_descontado), ("aprobado", True))
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, 10)

    def test_aprobar_dos_veces_descuenta_una(self):
        p = self.pedido((self.p1_decant, 2))
        descontar_stock(p.pk)
        self.assertEqual(descontar_stock(p.pk), (True, []))
        self.assertEqual(self.stock(self.p1_decant), 8)

    def test_sin_stock_queda_pendiente(self):
        p = self.pedido((self.p1_frasco, 4))
        ok, faltan = descontar_stock(p.pk)
        self.assertFalse(ok)
        self.assertEqual(len(faltan), 1)
        p.refresh_from_db()
        self.assertEqual((p.estado, p.stock_descontado), ("pendiente", False))
        self.assertEqual(self.stock(self.p1_frasco), 3)

    def test_ultima_unidad_no_se_vende_dos_veces(self):
        a, b = self.pedido((self.p1_frasco, 3)), self.pedido((self.p1_frasco, 1))
        self.assertTrue(descontar_stock(a.pk)[0])
        self.assertFalse(descontar_stock(b.pk)[0])
        self.assertEqual(self.stock(self.p1_frasco), 0)

    def test_rechazar_aprobado_repone_una_vez(self):
        p = self.pedido((self.p1_decant, 3))
        descontar_stock(p.pk)
        devolver_stock(p.pk)
        devolver_stock(p.pk)
        self.assertEqual(self.stock(self.p1_decant), 10)
        p.refresh_from_db()
        self.assertEqual((p.estado, p.stock_descontado), ("rechazado", False))

    def test_rechazar_pendiente_no_toca_el_stock(self):
        p = self.pedido((self.p1_decant, 3))
        devolver_stock(p.pk)
        self.assertEqual(self.stock(self.p1_decant), 10)


class AdminPedidoTests(Base):
    """Aprobar y rechazar desde el admin (acción de la lista y estado en la ficha)."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User
        entrar_admin_verificado(self.client, User.objects.create_superuser("admin-stock", "s@example.com", "x"))
        self.p = Pedido.objects.create(estado="pendiente", cliente="Ana")
        self.item = ItemPedido.objects.create(pedido=self.p, perfume=self.p1, presentacion=self.p1_decant,
                                              nombre="No. 101 · Decant 5 ml", precio=6000, cantidad=2)

    def stock(self):
        self.p1_decant.refresh_from_db()
        return self.p1_decant.stock

    def test_accion_aprobar_de_la_lista(self):
        r = self.client.post(reverse("admin:catalogo_pedido_changelist"),
                             {"action": "aprobar_pedidos", "_selected_action": [self.p.pk]})
        self.assertEqual(r.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado, "aprobado")
        self.assertEqual(self.stock(), 8)

    def guardar_ficha(self, estado):
        datos = {
            "cliente": "Ana", "apellido": "", "rut": "", "telefono": "", "email": "",
            "direccion": "", "comuna": "", "region": "", "notas": "", "estado": estado,
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1",
            "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-id": str(self.item.pk), "items-0-pedido": str(self.p.pk),
            "items-0-perfume": str(self.p1.pk), "items-0-presentacion": str(self.p1_decant.pk),
            "items-0-nombre": self.item.nombre, "items-0-precio": "6000", "items-0-cantidad": "2",
            "_save": "Guardar",
        }
        r = self.client.post(reverse("admin:catalogo_pedido_change", args=[self.p.pk]), datos)
        errores = r.context.get("errors") if r.status_code == 200 and r.context else None
        self.assertEqual(r.status_code, 302, errores)

    def test_cambiar_estado_en_la_ficha(self):
        self.guardar_ficha("aprobado")
        self.p.refresh_from_db()
        self.assertEqual((self.p.estado, self.p.stock_descontado, self.p.total), ("aprobado", True, 12000))
        self.assertEqual(self.stock(), 8)
        self.guardar_ficha("rechazado")
        self.p.refresh_from_db()
        self.assertEqual((self.p.estado, self.p.stock_descontado), ("rechazado", False))
        self.assertEqual(self.stock(), 10)


class ConsultasTests(Base):
    """Sin consultas N+1: el número de consultas no crece con la cantidad de perfumes."""

    def agregar(self, n, **extra):
        for _ in range(n):
            p = self._perfume(f"Extra {Perfume.objects.count()}", **extra)
            Presentacion.objects.create(perfume=p, formato="frasco", ml=50, precio=9000, stock=4)

    def capturar(self, url):
        with _Captura_is(_connection_is) as ctx:
            self.assertEqual(self.client.get(url).status_code, 200)
        return [q["sql"] for q in ctx.captured_queries]

    def test_home_no_crece_con_los_destacados(self):
        self.agregar(1, destacado=True)
        antes = len(self.capturar(reverse("home")))
        self.agregar(4, destacado=True)
        self.assertEqual(len(self.capturar(reverse("home"))), antes)

    def test_ficha_sin_consultas_por_tarjeta(self):
        self.agregar(2)
        Resena.objects.create(perfume=self.p1, nombre="A", calificacion=5, comentario="Muy bueno", aprobado=True)
        sql = self.capturar(self.p1.get_absolute_url())
        sueltas = [q for q in sql if 'FROM "catalogo_marca"' in q or 'FROM "catalogo_familiaolfativa"' in q]
        self.assertEqual(sueltas, [])
        self.assertEqual(len([q for q in sql if 'FROM "catalogo_resena"' in q]), 1)

    def test_ficha_solo_resenas_aprobadas(self):
        Resena.objects.create(perfume=self.p1, nombre="Ana", calificacion=5, comentario="Muy bueno", aprobado=True)
        Resena.objects.create(perfume=self.p1, nombre="Luis", calificacion=3, comentario="Bien", aprobado=True)
        Resena.objects.create(perfume=self.p1, nombre="Spam", calificacion=1, comentario="x", aprobado=False)
        r = self.client.get(self.p1.get_absolute_url())
        self.assertEqual((r.context["total_resenas"], r.context["promedio"]), (2, 4))
        self.assertNotContains(r, "Spam")


class SaludTests(TestCase):
    def test_ok_y_sin_cache(self):
        r = self.client.get("/salud/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        self.assertIn("no-store", r["Cache-Control"])

    def test_migraciones_pendientes_da_503(self):
        with _mock_is.patch("django.db.migrations.executor.MigrationExecutor.migration_plan",
                            return_value=[("x", False)]):
            with self.assertLogs("core.salud", "ERROR"):
                r = self.client.get("/salud/")
        self.assertEqual(r.status_code, 503)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_no_redirige_a_https(self):
        # Railway consulta el healthcheck por HTTP interno: un 301 haría fallar el deploy
        self.assertEqual(self.client.get("/salud/").status_code, 200)
        self.assertEqual(self.client.get("/perfumes/").status_code, 301)


class LogsTests(SimpleTestCase):
    def test_errores_500_van_a_la_consola(self):
        import logging
        self.assertTrue(logging.getLogger("django.request").handlers)


class PanelVentasTests(TestCase):
    def test_hoy_en_hora_de_chile(self):
        from django.contrib.auth.models import User
        entrar_admin_verificado(self.client, User.objects.create_superuser("admin-ventas", "v@example.com", "x"))
        dia = _date_is(2026, 3, 10)
        noche = _datetime_is(2026, 3, 10, 22, 30, tzinfo=_ZoneInfo_is("America/Santiago"))  # 01:30 UTC del 11
        p = Pedido.objects.create(estado="aprobado", total=15000)
        Pedido.objects.filter(pk=p.pk).update(creado=noche)
        original = _tz_is.localdate
        with _mock_is.patch("django.utils.timezone.localdate",
                            side_effect=lambda value=None, timezone=None: dia if value is None else original(value, timezone)):
            r = self.client.get(reverse("admin:panel_ventas"))
        self.assertEqual(r.context["total_dia"], 15000)


# ---------- ingenieria-semana2: pedidos sin duplicar, purga de Cloudflare, filtros en caché, estáticos ----------
import os as _os_s2
import uuid as _uuid_s2
from unittest import mock as _mock_s2

from django.core import mail as _mail_s2
from django.db import connection as _connection_s2
from django.test.utils import CaptureQueriesContext as _Captura_s2

from . import purga as _purga_s2
from .admin import descontar_stock as _descontar_s2
from .models import ItemPedido as _Item_s2, Marca as _Marca_s2, Promocion as _Promocion_s2, Resena as _Resena_s2


@override_settings(PEDIDO_CORREO_SINCRONO=True)
class IdempotenciaTests(Base):
    """C2: el mismo envío del carrito (doble toque, reintento) devuelve el pedido ya creado."""

    def setUp(self):
        super().setUp()
        _mail_s2.outbox = []
        limite = _mock_s2.patch("catalogo.views._excede_limite", return_value=False)
        limite.start()
        self.addCleanup(limite.stop)

    def pedir(self, clave):
        cuerpo = json.dumps({"items": [{"id": f"v-{self.p1_frasco.pk}", "qty": 1}],
                             "cliente": DatosPedidoTests.DATOS, "clave": clave})
        return self.client.post(reverse("crear_pedido"), data=cuerpo, content_type="application/json")

    def test_mismo_envio_un_solo_pedido(self):
        clave = str(_uuid_s2.uuid4())
        a, b = self.pedir(clave).json(), self.pedir(clave).json()
        self.assertEqual((b["codigo"], b["total"], b["lineas"]), (a["codigo"], a["total"], a["lineas"]))
        self.assertTrue(b["repetido"])
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(len(_mail_s2.outbox), 1)

    def test_envios_distintos_son_pedidos_distintos(self):
        self.pedir(str(_uuid_s2.uuid4()))
        self.pedir(str(_uuid_s2.uuid4()))
        self.assertEqual(Pedido.objects.count(), 2)

    def test_clave_invalida_se_ignora(self):
        self.assertEqual(self.pedir("no-es-uuid").status_code, 200)
        self.assertIsNone(Pedido.objects.get().clave)

    def test_carrito_manda_la_clave(self):
        js = Path(settings.BASE_DIR, "static", "js", "src", "base.js").read_text(encoding="utf-8")
        self.assertIn("clave: claveId", js)
        self.assertIn("sessionStorage", js)


@override_settings(PURGA_SINCRONA=True)
class PurgaTests(Base):
    """E3: al cambiar stock, precio o contenido se purgan la ficha, el home y /perfumes/."""
    ENV = {"CF_ZONA_ID": "zona-ci", "CF_TOKEN_PURGA": "token-ci"}

    def purgadas(self, accion):
        with _mock_s2.patch.dict(_os_s2.environ, self.ENV), _mock_s2.patch("catalogo.purga.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"success": True}
            with self.captureOnCommitCallbacks(execute=True):
                accion()
        return {u for c in post.call_args_list for u in c.kwargs["json"].get("files", [])}

    def url(self, ruta):
        return settings.SITE_URL + ruta

    def test_cambio_de_stock_purga_ficha_home_y_catalogo(self):
        def cambiar():
            self.p1_decant.stock = 0
            self.p1_decant.save()
        urls = self.purgadas(cambiar)
        for ruta in (self.p1.get_absolute_url(), "/", "/perfumes/"):
            self.assertIn(self.url(ruta), urls)

    def test_aprobar_pedido_purga_la_ficha(self):
        p = Pedido.objects.create(estado="pendiente")
        _Item_s2.objects.create(pedido=p, perfume=self.p1, presentacion=self.p1_decant,
                                nombre="x", precio=6000, cantidad=1)
        self.assertIn(self.url(self.p1.get_absolute_url()), self.purgadas(lambda: _descontar_s2(p.pk)))

    def test_resena_y_promocion(self):
        urls = self.purgadas(lambda: _Resena_s2.objects.create(perfume=self.p2, nombre="A", comentario="x", aprobado=True))
        self.assertIn(self.url(self.p2.get_absolute_url()), urls)
        urls = self.purgadas(lambda: _Promocion_s2.objects.create(titulo="Dúo", precio=5000, unidades=5))
        self.assertIn(self.url("/"), urls)

    def test_sin_variables_no_llama_a_cloudflare(self):
        sin_cf = {k: v for k, v in _os_s2.environ.items() if k not in self.ENV}
        with _mock_s2.patch.dict(_os_s2.environ, sin_cf, clear=True), \
                _mock_s2.patch("catalogo.purga.requests.post") as post:
            with self.captureOnCommitCallbacks(execute=True):
                self.p1_decant.stock = 1
                self.p1_decant.save()
        post.assert_not_called()

    def test_muchas_rutas_purga_todo(self):
        with _mock_s2.patch.dict(_os_s2.environ, self.ENV), _mock_s2.patch("catalogo.purga.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"success": True}
            _purga_s2._enviar([f"/perfume/p{i}/" for i in range(40)])
        self.assertEqual(post.call_args.kwargs["json"], {"purge_everything": True})


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                       "LOCATION": "facetas-ci"}})
class FacetasTests(Base):
    """D3: los filtros del catálogo se calculan una vez y se borran al editar el catálogo."""

    def consultas(self, url):
        with _Captura_s2(_connection_s2) as ctx:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(ctx)

    def test_segunda_visita_no_repite_los_filtros(self):
        url = reverse("catalogo")
        primera = self.consultas(url)
        self.assertLessEqual(self.consultas(url), primera - 5)

    def test_guardar_borra_los_filtros(self):
        self.client.get(reverse("catalogo"))
        with self.captureOnCommitCallbacks(execute=True):
            marca = _Marca_s2.objects.create(nombre="Casa Nueva")
            Perfume.objects.create(nombre="Nuevo", marca=marca, familia=self.familia,
                                   descripcion="x", precio=0, imagen=IMG)
        r = self.client.get(reverse("catalogo"))
        self.assertIn("Casa Nueva", [m.nombre for m in r.context["marcas"]])


class EstaticosTests(SimpleTestCase):
    """E5: nombres con hash en producción, sin abortar por referencias que no existen."""

    def test_produccion_usa_nombres_con_hash(self):
        import core.settings as produccion
        self.assertEqual(produccion.STORAGES["staticfiles"]["BACKEND"], "core.estaticos.EstaticosConHash")

    def test_referencia_faltante_no_aborta(self):
        import tempfile
        from core.estaticos import EstaticosConHash
        with tempfile.TemporaryDirectory() as carpeta:
            s = EstaticosConHash(location=carpeta, base_url="/static/")
            self.assertEqual(s.hashed_name("vendor/chart.umd.js.map"), "vendor/chart.umd.js.map")
