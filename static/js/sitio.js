// Reemplaza los onclick="" inline (bloqueados por la CSP estricta). Un solo listener delegado.
(function () {
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
