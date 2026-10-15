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
