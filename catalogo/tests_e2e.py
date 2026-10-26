"""Pruebas en navegador real (Playwright): CSP, JavaScript, carrito, buscador, cookies, móvil y accesibilidad.

No corren con `manage.py test` normal: se activan con E2E=1 (el workflow e2e.yml lo hace).
Local, una vez:  pip install -r requirements-e2e.txt  y  playwright install chromium webkit
Correr:          E2E=1 DJANGO_SETTINGS_MODULE=core.settings_e2e python manage.py test catalogo.tests_e2e
Otro navegador:  E2E_NAVEGADOR=webkit (Safari) o firefox
Capturas y trazas de cada prueba quedan en e2e-capturas/ (abrir los .zip en https://trace.playwright.dev).
"""
import base64
import os
import re
import time
import unittest
from pathlib import Path
from urllib.parse import unquote

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from .models import FamiliaOlfativa, Marca, Nota, Pedido, Perfume, PerfumeNota, Presentacion

ACTIVO = os.environ.get("E2E") == "1"
NAVEGADOR = os.environ.get("E2E_NAVEGADOR", "chromium")
CAPTURAS = Path(os.environ.get("E2E_CAPTURAS", "e2e-capturas"))
A11Y_ESTRICTO = os.environ.get("A11Y_ESTRICTO") == "1"

if ACTIVO:
    # Playwright síncrono mantiene un event loop en este hilo; el ORM de Django lo confunde con código async.
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    from playwright.sync_api import expect, sync_playwright

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")

# Se ejecuta antes que los scripts de cada página. Registra las violaciones de CSP y
# salta el preloader (salvo con #preloader en la URL, para probarlo a propósito).
INIT = """
window.__csp = [];
document.addEventListener('securitypolicyviolation', function (e) {
  window.__csp.push(e.violatedDirective + ' bloqueó ' + (e.blockedURI || 'inline') +
    (e.sourceFile ? ' en ' + e.sourceFile + ':' + e.lineNumber : ''));
}, true);
try { if (location.hash !== '#preloader') sessionStorage.setItem('io_pre', '1'); } catch (e) {}
"""


@unittest.skipUnless(ACTIVO, "pruebas de navegador: activar con E2E=1")
class NavegadorBase(StaticLiveServerTestCase):
    host = "localhost"
    dispositivo = None
    bypass_csp = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from core import security_headers as sh
        cls._csp_original = sh.CSP_SITIO
        # El servidor de pruebas es http: con upgrade-insecure-requests el navegador pediría todo por https.
        # Es la única directiva que se quita; el resto de la política se prueba tal cual.
        sh.CSP_SITIO = sh.CSP_SITIO.replace("; upgrade-insecure-requests", "")
        assert "upgrade-insecure-requests" not in sh.CSP_SITIO
        cls.pw = sync_playwright().start()
        cls.browser = getattr(cls.pw, NAVEGADOR).launch()
        CAPTURAS.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        from core import security_headers as sh
        sh.CSP_SITIO = cls._csp_original
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.crear_catalogo()
        self.errores, self.whatsapp, self.pixeles = [], [], []

        if self.dispositivo:
            opciones = dict(self.pw.devices[self.dispositivo])
            opciones.pop("default_browser_type", None)
            if NAVEGADOR == "firefox":
                opciones.pop("is_mobile", None)
        else:
            opciones = {"viewport": {"width": 1366, "height": 900}}
        self.ctx = self.browser.new_context(locale="es-CL", bypass_csp=self.bypass_csp, **opciones)
        self.ctx.add_init_script(INIT)
        # Las imágenes de prueba viven en memoria: se responden con un PNG de 1 px.
        self.ctx.route(re.compile(r".*(/media/|res\.cloudinary\.com/).*"),
                       lambda r: r.fulfill(body=PNG, content_type="image/png"))
        self.ctx.route(re.compile(r"https://(api\.)?wa\.me/.*"), self._whatsapp)
        self.ctx.route(re.compile(r"https://(www|maps)\.google\.com/maps.*"),
                       lambda r: r.fulfill(body="<html></html>", content_type="text/html"))
        self.ctx.route(re.compile(r"https://(connect\.facebook\.net|analytics\.tiktok\.com)/.*"), self._pixel)
        self.ctx.tracing.start(screenshots=True, snapshots=True)

        self.page = self.ctx.new_page()
        self.page.set_default_timeout(8000)
        self.page.on("pageerror", lambda e: self.errores.append(f"Error JS: {e}"))
        self.page.on("response", self._respuesta)

    def tearDown(self):
        nombre = f"{type(self).__name__}.{self._testMethodName}-{NAVEGADOR}"
        try:
            self.page.screenshot(path=CAPTURAS / f"{nombre}.png", full_page=True)
        except Exception:
            pass
        self.ctx.tracing.stop(path=CAPTURAS / f"{nombre}.zip")
        self.ctx.close()

    # ---------- datos ----------
    def crear_catalogo(self):
        marca = Marca.objects.create(nombre="Casa Prueba")
        familia = FamiliaOlfativa.objects.create(nombre="Amaderada")
        self.vainilla = Nota.objects.create(nombre="Vainilla")

        def perfume(nombre, **extra):
            return Perfume.objects.create(nombre=nombre, marca=marca, familia=familia,
                                          descripcion="Descripción de prueba.", precio=0,
                                          imagen="perfumes/ci.jpg", **extra)

        self.p1 = perfume("No. 101", genero="M", inspirado_en="Sauvage de Dior", concentracion="edp")
        Presentacion.objects.create(perfume=self.p1, formato="decant", ml=5, precio=6000, stock=10)
        Presentacion.objects.create(perfume=self.p1, formato="frasco", ml=100, precio=25000, stock=3)
        self.p2 = perfume("Brisa Cítrica", genero="F", concentracion="edt")
        Presentacion.objects.create(perfume=self.p2, formato="frasco", ml=50, precio=15000, stock=5)
        for p in (self.p1, self.p2):
            PerfumeNota.objects.create(perfume=p, nota=self.vainilla, nivel="fondo")
            p.refresh_from_db()

    # ---------- utilidades ----------
    def _respuesta(self, r):
        if r.url.startswith(self.live_server_url) and r.status >= 400 and r.request.resource_type != "document":
            self.errores.append(f"HTTP {r.status}: {r.url}")

    def _whatsapp(self, route):
        self.whatsapp.append(route.request.url)
        route.fulfill(body="<html>WhatsApp</html>", content_type="text/html")

    def _pixel(self, route):
        self.pixeles.append(route.request.url)
        route.fulfill(body="window.fbq=window.fbq||function(){};", content_type="application/javascript")

    def ir(self, ruta, estado=200):
        r = self.page.goto(self.live_server_url + ruta, wait_until="networkidle")
        self.assertEqual(r.status, estado, ruta)
        return r

    def sin_errores(self, donde):
        csp = self.page.evaluate("window.__csp || []")
        self.assertEqual(csp, [], f"Violaciones de CSP en {donde}")
        self.assertEqual(self.errores, [], f"Errores en {donde}")
        self.errores.clear()

    def esperar(self, condicion, mensaje, segundos=6):
        fin = time.monotonic() + segundos
        while time.monotonic() < fin:
            if condicion():
                return
            self.page.wait_for_timeout(100)
        self.fail(mensaje)


class PaginasTests(NavegadorBase):
    def test_sin_violaciones_csp_ni_errores_js(self):
        rutas = [
            reverse("home"), reverse("catalogo"), reverse("catalogo") + "?q=brisa",
            self.p1.get_absolute_url(), self.vainilla.get_absolute_url(),
            reverse("contacto"), reverse("nosotros"), reverse("politicas"),
            reverse("terminos"), reverse("privacidad"),
        ]
        for ruta in rutas:
            with self.subTest(ruta):
                self.ir(ruta)
                self.sin_errores(ruta)
        self.ir("/esta-pagina-no-existe/", estado=404)
        self.sin_errores("404")

    def test_estilos_y_fuentes_cargan(self):
        self.ir(reverse("home"))
        # Tailwind (css_inline con nonce) y el <style> propio de base.html
        self.assertEqual(self.page.eval_on_selector("header", "e => getComputedStyle(e).position"), "sticky")
        familia = self.page.eval_on_selector(".font-serif", "e => getComputedStyle(e).fontFamily")
        self.assertIn("Playfair", familia)
        self.assertTrue(self.page.evaluate(
            "document.fonts.ready.then(() => document.fonts.check('16px \"Playfair Display\"'))"),
            "Google Fonts no cargó (revisar style-src y font-src)")

    def test_preloader_desaparece(self):
        self.ir(reverse("home") + "#preloader")
        expect(self.page.locator("#preloader")).to_have_class(re.compile(r"preloader-hidden"), timeout=4000)


class BuscadorTests(NavegadorBase):
    def test_lupa_busca_cierra_y_atajo(self):
        self.ir(reverse("home"))
        self.page.click("#buscar-toggle")
        expect(self.page.locator("#buscador")).to_be_visible()
        expect(self.page.locator("#buscador-input")).to_be_focused()
        self.page.fill("#buscador-input", "brisa")
        expect(self.page.locator("#buscador-resultados")).to_contain_text("Brisa Cítrica")
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#buscador")).to_be_hidden()
        self.page.keyboard.press("/")
        expect(self.page.locator("#buscador")).to_be_visible()
        self.sin_errores("buscador")

    def test_sin_resultados_y_enter(self):
        self.ir(reverse("home"))
        self.page.click("#buscar-toggle")
        self.page.fill("#buscador-input", "zzqxw")
        expect(self.page.locator("#buscador-resultados")).to_contain_text("Sin resultados")
        self.page.fill("#buscador-input", "brisa")
        self.page.press("#buscador-input", "Enter")
        self.page.wait_for_url(re.compile(r"/perfumes/\?q=brisa"))
        self.sin_errores("búsqueda con Enter")


class CarritoTests(NavegadorBase):
    def test_agregar_cambiar_persistir_y_quitar(self):
        self.ir(self.p1.get_absolute_url())
        panel, badge = self.page.locator("#cart-panel"), self.page.locator("#cart-badge")
        self.page.click("#btn-agregar")
        expect(panel).not_to_have_class(re.compile(r"translate-x-full"))
        expect(badge).to_have_text("1")
        with self.page.expect_response(lambda r: "/api/cotizar/" in r.url and "%3A2" in r.url):
            self.page.click('[data-mas="0"]')
        expect(badge).to_have_text("2")
        self.page.click("#cart-close")
        expect(panel).to_have_class(re.compile(r"translate-x-full"))

        self.page.reload(wait_until="networkidle")
        expect(badge).to_have_text("2")

        self.page.click("#cart-toggle")
        self.page.click('[data-quitar="0"]')
        expect(self.page.locator("#cart-empty")).to_be_visible()
        expect(badge).to_be_hidden()
        self.sin_errores("carrito")

    def test_solicitar_crea_pedido_y_abre_whatsapp(self):
        self.ir(self.p1.get_absolute_url())
        self.page.click("#btn-agregar")
        self.page.click("#cart-checkout")
        self.esperar(lambda: self.whatsapp, "No se abrió WhatsApp")
        self.assertEqual(Pedido.objects.count(), 1, "El servidor no creó el pedido (revisar /api/csrf/ y CSRF)")
        texto = unquote(self.whatsapp[0])
        self.assertIn(Pedido.objects.get().codigo, texto)
        self.assertIn("TOTAL:", texto)
        self.sin_errores("checkout")


class ContactoTests(NavegadorBase):
    def test_mapa_carga_al_clic(self):
        self.ir(reverse("contacto"))
        expect(self.page.locator("iframe")).to_have_count(0)
        self.page.click("[data-mapa]")
        expect(self.page.locator('iframe[title="Mapa"]')).to_have_attribute("src", re.compile(r"google\.com/maps"))
        self.sin_errores("mapa")

    def test_formulario_envia_correo(self):
        self.ir(reverse("contacto"))
        self.page.fill('[name="nombre"]', "Ana Prueba")
        self.page.fill('[name="email"]', "ana@example.com")
        self.page.fill('[name="mensaje"]', "Hola, ¿tienen decants de 10 ml?")
        self.page.locator('form:has([name="mensaje"]) [type="submit"]').click()
        self.page.wait_for_load_state("networkidle")
        expect(self.page.locator('[role="status"]')).to_be_visible()
        self.assertEqual(len(mail.outbox), 1)
        self.sin_errores("formulario de contacto")


@override_settings(META_PIXEL_ID="123456789", TIKTOK_PIXEL_ID="CPRUEBA123")
class CookiesTests(NavegadorBase):
    def test_pixeles_solo_despues_de_aceptar(self):
        self.ir(reverse("politicas"))
        aviso = self.page.locator("#io-cookies")
        expect(aviso).to_be_visible()
        self.page.wait_for_timeout(800)
        self.assertEqual(self.pixeles, [], "Un píxel cargó antes del consentimiento")

        self.page.click('[data-consent="si"]')
        expect(aviso).to_be_hidden()
        self.esperar(lambda: any("facebook" in u for u in self.pixeles), "El píxel de Meta no cargó tras aceptar")
        self.esperar(lambda: any("tiktok" in u for u in self.pixeles), "El píxel de TikTok no cargó tras aceptar")
        self.sin_errores("píxeles con strict-dynamic")

        self.page.reload(wait_until="networkidle")
        expect(aviso).to_be_hidden()

    def test_rechazar_y_reabrir_preferencias(self):
        self.ir(reverse("politicas"))
        self.page.click('[data-consent="no"]')
        self.page.reload(wait_until="networkidle")
        expect(self.page.locator("#io-cookies")).to_be_hidden()
        self.assertEqual(self.pixeles, [])
        self.page.click('[data-accion="preferencias-cookies"]')
        expect(self.page.locator("#io-cookies")).to_be_visible()
        self.sin_errores("preferencias de cookies")


class MovilTests(NavegadorBase):
    dispositivo = "iPhone 13" if NAVEGADOR == "webkit" else "Pixel 7"

    def test_menu_movil(self):
        self.ir(reverse("home"))
        menu = self.page.locator("#mobile-menu")
        expect(menu).to_be_hidden()
        self.page.click("#mobile-menu-button")
        expect(menu).to_be_visible()
        menu.get_by_role("link", name="Catálogo").click()
        self.page.wait_for_url(re.compile(r"/perfumes/$"))
        self.sin_errores("menú móvil")

    def test_sin_scroll_horizontal(self):
        for ruta in (reverse("home"), reverse("catalogo"), self.p1.get_absolute_url(), reverse("contacto")):
            with self.subTest(ruta):
                self.ir(ruta)
                ancho = self.page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
                self.assertLessEqual(ancho[0], ancho[1], f"La página es más ancha que la pantalla: {ancho}")

    def test_carrito_en_movil(self):
        self.ir(self.p1.get_absolute_url())
        self.page.click("#btn-agregar")
        expect(self.page.locator("#cart-checkout")).to_be_in_viewport()
        self.sin_errores("carrito en móvil")


class AccesibilidadTests(NavegadorBase):
    bypass_csp = True  # para inyectar axe-core; la CSP ya se prueba en las otras clases

    def test_axe_sin_problemas_criticos(self):
        from axe_playwright_python.sync_playwright import Axe
        axe, criticos, serios = Axe(), [], []
        for ruta in (reverse("home"), reverse("catalogo"), self.p1.get_absolute_url(), reverse("contacto")):
            self.ir(ruta)
            for v in axe.run(self.page).response["violations"]:
                linea = f"{ruta} · {v['id']} ({len(v['nodes'])}): {v['help']}"
                (criticos if v["impact"] == "critical" else serios if v["impact"] == "serious" else []).append(linea)
        if serios:
            print("\nAccesibilidad, problemas serios:\n  " + "\n  ".join(serios))
        self.assertEqual(criticos + (serios if A11Y_ESTRICTO else []), [])

    def test_teclado_llega_a_buscador_y_carrito(self):
        self.ir(reverse("home"))
        vistos = set()
        for _ in range(20):
            self.page.keyboard.press("Tab")
            vistos.add(self.page.evaluate("document.activeElement.id"))
        self.assertTrue({"buscar-toggle", "cart-toggle"} <= vistos, f"Con Tab se llegó a: {sorted(vistos)}")
        self.page.focus("#cart-toggle")
        self.page.keyboard.press("Enter")
        expect(self.page.locator("#cart-panel")).not_to_have_class(re.compile(r"translate-x-full"))
