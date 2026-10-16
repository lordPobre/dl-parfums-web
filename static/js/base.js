// Movido desde templates/base.html (seo2).
        document.addEventListener("DOMContentLoaded", () => {
            const btnMenu = document.getElementById('mobile-menu-button');
            const menuMovil = document.getElementById('mobile-menu');
            if (btnMenu) btnMenu.addEventListener('click', () => menuMovil.classList.toggle('hidden'));
        });
        // Preloader: solo la primera página de la sesión. Mínimo visible 0,4 s en móvil y 0,9 s en escritorio; máximo 2,5 s
        (function () {
            var p = document.getElementById('preloader');
            if (!p) return;
            if (sessionStorage.getItem('io_pre')) { p.remove(); return; }
            var t0 = performance.now(), MIN = window.innerWidth < 768 ? 400 : 900, hecho = false;
            function ocultar() {
                if (hecho) return; hecho = true;
                sessionStorage.setItem('io_pre', '1');
                setTimeout(function () { p.classList.add('preloader-hidden'); },
                        Math.max(0, MIN - (performance.now() - t0)));
            }
            document.addEventListener('DOMContentLoaded', ocultar);
            setTimeout(ocultar, 2500);
        })();

        // Disuasivos de descarga de imágenes
        document.addEventListener('contextmenu', function (e) {
            if (e.target && e.target.tagName === 'IMG') e.preventDefault();
        });
        document.addEventListener('dragstart', function (e) {
            if (e.target && e.target.tagName === 'IMG') e.preventDefault();
        });

        /* Token CSRF bajo demanda: las páginas se cachean en el CDN y no traen token propio */
        window.obtenerCsrf = function () {
            return fetch("/api/csrf/", { credentials: "same-origin", cache: "no-store" })
                .then(function (r) { return r.json(); })
                .then(function (d) { return d.token; });
        };

        /* ==================== BUSCADOR ==================== */
        (function () {
            var caja = document.getElementById("buscador");
            var input = document.getElementById("buscador-input");
            var lista = document.getElementById("buscador-resultados");
            var boton = document.getElementById("buscar-toggle");
            if (!caja || !input) return;
            var espera, ultima = "";

            function abrir() {
                caja.classList.remove("hidden");
                boton.setAttribute("aria-expanded", "true");
                document.body.style.overflow = "hidden";
                setTimeout(function () { input.focus(); }, 30);
            }
            function cerrar() {
                caja.classList.add("hidden");
                boton.setAttribute("aria-expanded", "false");
                document.body.style.overflow = "";
            }
            function el(tag, clases, texto) {
                var n = document.createElement(tag);
                if (clases) n.className = clases;
                if (texto) n.textContent = texto;
                return n;
            }
            function pintar(data, texto) {
                lista.innerHTML = "";
                if (!data.resultados.length) {
                    lista.appendChild(el("p", "py-6 text-center font-serif italic text-gray-500", "Sin resultados para \u201C" + texto + "\u201D. Prueba con el nombre del perfume original o una nota."));
                    return;
                }
                var ul = el("ul", "divide-y divide-gray-100");
                data.resultados.forEach(function (r) {
                    var li = el("li");
                    var a = el("a", "flex items-center gap-4 py-3 hover:bg-gray-50 transition-colors");
                    a.href = r.url;
                    var foto = el("div", "w-14 h-16 flex-shrink-0 bg-[#f8f8f8] flex items-center justify-center overflow-hidden");
                    if (r.img) { var img = el("img", "max-h-[85%] max-w-[85%] object-contain"); img.src = r.img; img.alt = ""; img.width = 56; img.height = 64; foto.appendChild(img); }
                    var info = el("div", "flex-1 min-w-0");
                    info.appendChild(el("p", "text-[9px] tracking-[0.2em] uppercase text-gray-500", r.casa));
                    info.appendChild(el("p", "font-serif text-[15px] text-gray-900 leading-snug truncate", r.nombre));
                    if (r.inspirado_en) info.appendChild(el("p", "text-[12px] font-light text-gray-500 truncate", "Inspirado en " + r.inspirado_en));
                    var precio = el("p", "text-[13px] whitespace-nowrap " + (r.agotado ? "text-gray-500" : "text-gray-800"), r.agotado ? "Agotado" : (r.desde ? "Desde " : "") + r.precio);
                    a.appendChild(foto); a.appendChild(info); a.appendChild(precio);
                    li.appendChild(a); ul.appendChild(li);
                });
                lista.appendChild(ul);
                var todos = el("a", "mt-4 flex items-center justify-center h-11 border border-gray-900 text-[11px] tracking-[0.2em] uppercase text-gray-900 hover:bg-gray-900 hover:text-white transition-colors", "Ver todos los resultados");
                todos.href = data.ver_todos;
                lista.appendChild(todos);
            }
            input.addEventListener("input", function () {
                var texto = input.value.trim();
                clearTimeout(espera);
                if (texto.length < 2) { lista.innerHTML = ""; ultima = ""; return; }
                espera = setTimeout(function () {
                    if (texto === ultima) return;
                    ultima = texto;
                    fetch("/api/buscar/?q=" + encodeURIComponent(texto))
                        .then(function (r) { return r.json(); })
                        .then(function (d) { if (input.value.trim() === texto) pintar(d, texto); })
                        .catch(function () {});
                }, 200);
            });
            boton.addEventListener("click", abrir);
            caja.addEventListener("click", function (e) { if (e.target.closest("[data-cerrar-buscador]")) cerrar(); });
            document.addEventListener("keydown", function (e) {
                if (e.key === "Escape" && !caja.classList.contains("hidden")) cerrar();
                var escribiendo = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "");
                if (e.key === "/" && !escribiendo && caja.classList.contains("hidden")) { e.preventDefault(); abrir(); }
            });
        })();

        /* ==================== CARRITO ==================== */
        (function () {
            var WHATSAPP = "56962169898";
            var KEY = "io_cart";
            var cart = [];
            try { cart = JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { cart = []; }

            function guardar() { try { localStorage.setItem(KEY, JSON.stringify(cart)); } catch (e) {} }
            function fmt(n) { return "$" + (n || 0).toLocaleString("es-CL"); }
            function totalItems() { return cart.reduce(function (s, i) { return s + i.qty; }, 0); }
            function totalPrecio() { return cart.reduce(function (s, i) { return s + i.precio * i.qty; }, 0); }

            var panel = document.getElementById("cart-panel");
            var overlay = document.getElementById("cart-overlay");
            var badge = document.getElementById("cart-badge");
            var cont = document.getElementById("cart-items");
            var vacio = document.getElementById("cart-empty");
            var pie = document.getElementById("cart-footer");
            var elTotal = document.getElementById("cart-total");

            function abrir() { overlay.classList.remove("hidden"); panel.classList.remove("translate-x-full"); requestAnimationFrame(function () { overlay.classList.remove("opacity-0"); }); document.body.style.overflow = "hidden"; }
            function cerrar() { overlay.classList.add("opacity-0"); panel.classList.add("translate-x-full"); document.body.style.overflow = ""; setTimeout(function () { overlay.classList.add("hidden"); }, 300); }

            function toast(msg) {
                var t = document.getElementById("cart-toast");
                t.textContent = msg; t.classList.remove("hidden");
                requestAnimationFrame(function () { t.classList.remove("opacity-0", "translate-y-2"); });
                clearTimeout(t._to);
                t._to = setTimeout(function () { t.classList.add("opacity-0", "translate-y-2"); setTimeout(function () { t.classList.add("hidden"); }, 300); }, 1800);
            }

            function render() {
                badge.textContent = totalItems();
                badge.classList.toggle("hidden", totalItems() === 0);
                if (!cart.length) {
                    cont.innerHTML = ""; cont.classList.add("hidden");
                    vacio.classList.remove("hidden"); pie.classList.add("hidden");
                    return;
                }
                cont.classList.remove("hidden"); vacio.classList.add("hidden"); pie.classList.remove("hidden");
                elTotal.textContent = fmt(totalPrecio());
                cont.innerHTML = cart.map(function (i, idx) {
                    return '<div class="flex gap-4 items-start">' +
                        (i.img ? '<div class="w-16 h-20 bg-[#f8f8f8] flex-shrink-0 flex items-center justify-center overflow-hidden"><img src="' + i.img + '" alt="" class="max-h-[85%] max-w-[85%] object-contain"></div>' : '') +
                        '<div class="flex-1 min-w-0">' +
                            '<p class="text-[9px] tracking-[0.2em] uppercase text-gray-500">' + (i.marca || "") + '</p>' +
                            '<h4 class="font-serif text-sm text-gray-900 leading-snug mb-1">' + i.nombre + '</h4>' +
                            '<p class="text-[13px] text-gray-700 font-light">' + fmt(i.precio) + '</p>' +
                            '<div class="flex items-center gap-2 mt-2">' +
                                '<button data-menos="' + idx + '" class="w-6 h-6 border border-gray-200 text-gray-600 hover:border-gray-900 flex items-center justify-center text-sm">−</button>' +
                                '<span class="text-sm w-6 text-center">' + i.qty + '</span>' +
                                '<button data-mas="' + idx + '" class="w-6 h-6 border border-gray-200 text-gray-600 hover:border-gray-900 flex items-center justify-center text-sm">+</button>' +
                                '<button data-quitar="' + idx + '" class="ml-auto text-[10px] tracking-[0.14em] uppercase text-gray-500 hover:text-red-700">Quitar</button>' +
                            '</div>' +
                        '</div>' +
                    '</div>';
                }).join("");
            }

            window.agregarAlCarrito = function (p) {
                var ex = cart.find(function (i) { return i.id === p.id; });
                if (ex) { ex.qty += 1; } else { cart.push({ id: p.id, nombre: p.nombre, marca: p.marca, precio: Number(p.precio) || 0, img: p.img || "", qty: 1 }); }
                guardar(); render(); toast("Agregado a tu selección"); abrir();
            };

            cont.addEventListener("click", function (e) {
                var t = e.target;
                if (t.dataset.mas !== undefined) { cart[+t.dataset.mas].qty += 1; }
                else if (t.dataset.menos !== undefined) { var i = +t.dataset.menos; cart[i].qty -= 1; if (cart[i].qty <= 0) cart.splice(i, 1); }
                else if (t.dataset.quitar !== undefined) { cart.splice(+t.dataset.quitar, 1); }
                else return;
                guardar(); render();
            });

            document.getElementById("cart-toggle").addEventListener("click", function () { render(); abrir(); });
            document.getElementById("cart-close").addEventListener("click", cerrar);
            overlay.addEventListener("click", cerrar);
            document.getElementById("cart-clear").addEventListener("click", function () { cart = []; guardar(); render(); });

            document.getElementById("cart-checkout").addEventListener("click", function () {
                if (!cart.length) return;
                // Se abre la pestaña en el mismo clic (evita el bloqueo de pop-ups) y se completa
                // con el mensaje cuando el servidor devuelve el N.º de pedido y el total validado.
                var w = window.open("", "_blank");
                var enviado = false;

                function mensaje(codigo, total) {
                    var lineas = ["Hola! Quiero solicitar los siguientes perfumes:", ""];
                    cart.forEach(function (i) {
                        lineas.push("• " + i.nombre + (i.marca ? " (" + i.marca + ")" : "") + " — " + i.qty + " x " + fmt(i.precio));
                    });
                    lineas.push("");
                    lineas.push("TOTAL: " + fmt(total));
                    if (codigo) lineas.push("N.º de pedido: " + codigo);
                    return "https://wa.me/" + WHATSAPP + "?text=" + encodeURIComponent(lineas.join("\n"));
                }
                function ir(url) {
                    if (enviado) return;
                    enviado = true;
                    if (w && !w.closed) { w.location.href = url; } else { window.location.href = url; }
                }

                // Si el servidor tarda más de 4 s, se envía igual sin número de pedido
                var espera = setTimeout(function () { ir(mensaje(null, totalPrecio())); }, 4000);

                window.obtenerCsrf().then(function (token) {
                    return fetch("/api/pedido/", {
                        method: "POST",
                        credentials: "same-origin",
                        headers: { "Content-Type": "application/json", "X-CSRFToken": token },
                        body: JSON.stringify({ items: cart.map(function (i) { return { id: i.id, qty: i.qty }; }) })
                    });
                })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (d) {
                    clearTimeout(espera);
                    ir(d && d.ok ? mensaje(d.codigo, d.total) : mensaje(null, totalPrecio()));
                })
                .catch(function () { clearTimeout(espera); ir(mensaje(null, totalPrecio())); });
            });

            function getCookie(name) {
                var m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
                return m ? m.pop() : "";
            }

            // Botones "Agregar al carrito" (delegación)
            document.addEventListener("click", function (e) {
                var btn = e.target.closest("[data-add-cart]");
                if (!btn) return;
                e.preventDefault();
                agregarAlCarrito({
                    id: btn.getAttribute("data-id"),
                    nombre: btn.getAttribute("data-nombre"),
                    marca: btn.getAttribute("data-marca"),
                    precio: btn.getAttribute("data-precio"),
                    img: btn.getAttribute("data-img")
                });
            });

            render();
        })();
