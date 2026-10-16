// Reemplaza los onclick="" inline (bloqueados por la CSP estricta). Un solo listener delegado.
(function () {
    // Carrusel de marcas: la segunda copia (para el bucle continuo) se crea aquí y no en el HTML.
    // Así la página no repite 33 imágenes y 33 enlaces.
    document.querySelectorAll(".marquee-track").forEach(function (pista) {
        Array.prototype.slice.call(pista.children).forEach(function (n) {
            var copia = n.cloneNode(true);
            copia.setAttribute("aria-hidden", "true");
            copia.setAttribute("tabindex", "-1");
            copia.querySelectorAll("img").forEach(function (i) { i.loading = "lazy"; i.alt = ""; });
            pista.appendChild(copia);
        });
    });

    document.addEventListener("click", function (e) {
        var b = e.target.closest("[data-carrusel], [data-accion], [data-mapa]");
        if (!b) return;

        if (b.hasAttribute("data-carrusel")) {
            var pista = document.getElementById(b.getAttribute("data-carrusel"));
            if (pista) pista.scrollLeft += parseInt(b.getAttribute("data-paso"), 10) || 0;
            return;
        }

        if (b.getAttribute("data-accion") === "preferencias-cookies") {
            if (window.abrirPreferenciasCookies) window.abrirPreferenciasCookies();
            return;
        }

        if (b.hasAttribute("data-mapa")) {
            var f = document.createElement("iframe");
            f.src = b.getAttribute("data-mapa");
            f.title = "Mapa";
            f.loading = "lazy";
            f.referrerPolicy = "strict-origin-when-cross-origin";
            f.style.cssText = "width:100%;height:320px;border:0";
            b.replaceWith(f);
        }
    });
})();
