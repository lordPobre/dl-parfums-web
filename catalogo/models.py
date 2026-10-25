from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


def slug_unico(modelo, texto, pk=None, largo=200):
    """Genera un slug a partir de 'texto' que no exista en 'modelo' (agrega -2, -3...)."""
    base = (slugify(texto) or "item")[: largo - 4]
    slug, n = base, 2
    while modelo.objects.filter(slug=slug).exclude(pk=pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, help_text="Parte de la URL: /casa/<slug>/. Se genera solo si lo dejas vacío.")
    logo = models.ImageField(upload_to='marcas/', blank=True, null=True)
    descripcion = models.TextField(blank=True, verbose_name="Historia de la marca", help_text="Se muestra como introducción en /casa/<slug>/.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unico(Marca, self.nombre, self.pk, 120)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalogo_casa", args=[self.slug])

    class Meta:
        verbose_name_plural = "Marcas"

    def __str__(self):
        return self.nombre

class FamiliaOlfativa(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, help_text="Parte de la URL: /familia/<slug>/. Se genera solo si lo dejas vacío.")
    descripcion = models.TextField(blank=True, help_text="Se muestra como introducción en /familia/<slug>/ (ideal 80–150 palabras).")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unico(FamiliaOlfativa, self.nombre, self.pk, 120)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalogo_familia", args=[self.slug])

    def __str__(self):
        return self.nombre

class Nota(models.Model):
    """Nota olfativa (vainilla, bergamota, oud...). Tiene su propia página /nota/<slug>/."""
    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text="Parte de la URL: /nota/<slug>/. Se genera solo si lo dejas vacío.")
    descripcion = models.TextField(blank=True, help_text="Introducción de /nota/<slug>/ (ideal 60–120 palabras): cómo huele, en qué perfumes destaca.")

    class Meta:
        ordering = ['nombre']
        verbose_name = "Nota olfativa"
        verbose_name_plural = "Notas olfativas"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unico(Nota, self.nombre, self.pk, 100)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalogo_nota", args=[self.slug])

    def __str__(self):
        return self.nombre


class Perfume(models.Model):
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('U', 'Unisex'),
    ]

    nombre = models.CharField(max_length=200)
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, related_name='productos')
    familia = models.ForeignKey(FamiliaOlfativa, on_delete=models.SET_NULL, null=True, blank=True)
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, default='U')
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=0) # Ideal para CLP
    stock = models.PositiveIntegerField(default=0)
    es_oferta = models.BooleanField(default=False, verbose_name="¿Es oferta?")
    precio_oferta = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True, verbose_name="Precio de oferta")
    imagen = models.ImageField(upload_to='perfumes/', verbose_name="Imagen Principal")
    notas_salida  = models.CharField(max_length=255, blank=True)
    notas_corazon = models.CharField(max_length=255, blank=True)
    notas_fondo   = models.CharField(max_length=255, blank=True)
    # Las notas se editan en "Notas olfativas (pirámide)"; los 3 campos de texto de arriba
    # se rellenan solos desde ahí (los usan la búsqueda y como respaldo en la ficha).
    notas = models.ManyToManyField('Nota', through='PerfumeNota', related_name='perfumes', blank=True)
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField(default=False, help_text="Mostrar en la página de inicio")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True, help_text="Parte de la URL: /perfume/<slug>/. Se genera solo si lo dejas vacío. Cambiarlo rompe enlaces existentes.")
    inspirado_en = models.CharField(max_length=200, blank=True, help_text="Perfume original de referencia, ej: 'Sauvage de Dior'. Se muestra bajo el nombre y se usa en la búsqueda.")
    meta_titulo = models.CharField(max_length=70, blank=True, help_text="Opcional. Título para Google (máx. 60–70 caracteres). Si lo dejas vacío se genera solo.")
    meta_descripcion = models.CharField(max_length=160, blank=True, help_text="Opcional. Descripción para Google (140–155 caracteres). Si la dejas vacía se genera sola.")

    CONCENTRACIONES = [
        ('', '—'),
        ('edt', 'Eau de Toilette'),
        ('edp', 'Eau de Parfum'),
        ('parfum', 'Parfum'),
        ('extrait', 'Extrait de Parfum'),
    ]
    concentracion = models.CharField(max_length=10, choices=CONCENTRACIONES, blank=True)
    fusionado_en = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='fusionados',
        help_text="Si este perfume se unió a otro como presentación, su URL redirige allí.",
    )
    n_presentaciones = models.PositiveSmallIntegerField(default=1, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unico(Perfume, self.nombre, self.pk, 220)
        elif self.pk:
            # Si cambias el slug a mano, la URL anterior redirige (301) a la nueva
            anterior = Perfume.objects.filter(pk=self.pk).values_list('slug', flat=True).first()
            if anterior and anterior != self.slug:
                SlugAntiguo.objects.update_or_create(slug=anterior, defaults={'perfume': self})
        super().save(*args, **kwargs)

    def actualizar_resumen(self):
        """Copia en el perfume el precio 'desde', el stock total y si hay oferta, a partir
        de sus presentaciones activas. Lo usan tarjetas, home, filtros y el orden del catálogo."""
        pres = list(self.presentaciones.filter(activo=True))
        disponibles = [p for p in pres if p.stock > 0] or pres
        if disponibles:
            base = min(disponibles, key=lambda p: p.precio_vigente)
            datos = {
                'precio': base.precio,
                'precio_oferta': base.precio_oferta,
                'es_oferta': any(p.precio_oferta for p in pres),
                'stock': sum(p.stock for p in pres),
                'n_presentaciones': len(pres),
            }
        else:
            datos = {'stock': 0, 'n_presentaciones': 0, 'es_oferta': False, 'precio_oferta': None}
        datos['actualizado'] = timezone.now()
        Perfume.objects.filter(pk=self.pk).update(**datos)
        for campo, valor in datos.items():
            setattr(self, campo, valor)

    @property
    def piramide(self):
        """{'salida': [Nota...], 'corazon': [...], 'fondo': [...]} (usa el prefetch si existe)."""
        p = {'salida': [], 'corazon': [], 'fondo': []}
        for pn in self.notas_perfume.all():
            p[pn.nivel].append(pn.nota)
        return p

    def sincronizar_notas(self):
        """Copia las notas del modelo a notas_salida / notas_corazon / notas_fondo."""
        p = {'salida': [], 'corazon': [], 'fondo': []}
        for pn in PerfumeNota.objects.filter(perfume_id=self.pk).select_related('nota'):
            p[pn.nivel].append(pn.nota.nombre)
        datos = {f'notas_{nivel}': ', '.join(nombres)[:255] for nivel, nombres in p.items()}
        datos['actualizado'] = timezone.now()
        Perfume.objects.filter(pk=self.pk).update(**datos)

    def get_absolute_url(self):
        return reverse("perfume_detalle", args=[self.slug])

    @property
    def precio_vigente(self):
        return self.precio_oferta if (self.es_oferta and self.precio_oferta) else self.precio

    def __str__(self):
        return self.nombre
    
class Presentacion(models.Model):
    """Lo que realmente se vende: un tamaño de un perfume, con su propio precio y stock."""
    FORMATOS = [('decant', 'Decant'), ('frasco', 'Frasco')]

    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, related_name='presentaciones')
    formato = models.CharField(max_length=10, choices=FORMATOS, default='frasco')
    ml = models.PositiveSmallIntegerField(help_text="Contenido en ml (5, 10, 30, 50...).")
    sku = models.CharField(max_length=40, unique=True, blank=True, help_text="Se genera solo si lo dejas vacío.")
    precio = models.PositiveIntegerField(help_text="Precio en CLP.")
    precio_oferta = models.PositiveIntegerField(null=True, blank=True, help_text="Opcional. Debe ser menor que el precio.")
    stock = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'ml']
        verbose_name = "Presentación"
        verbose_name_plural = "Presentaciones"
        constraints = [
            models.UniqueConstraint(fields=['perfume', 'formato', 'ml'], name='presentacion_unica'),
            models.CheckConstraint(
                condition=models.Q(precio_oferta__isnull=True) | models.Q(precio_oferta__lt=models.F('precio')),
                name='oferta_menor_que_precio',
            ),
        ]
        indexes = [models.Index(fields=['perfume', 'activo'], name='catalogo_pr_perfume_activo_idx')]

    def __str__(self):
        return f"{self.perfume.nombre} · {self.etiqueta}"

    @property
    def etiqueta(self):
        return f"{self.get_formato_display()} {self.ml} ml"

    @property
    def precio_vigente(self):
        return self.precio_oferta or self.precio

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = f"IO-{self.perfume_id}-{self.ml}{self.formato[0].upper()}"
        super().save(*args, **kwargs)


class SlugAntiguo(models.Model):
    """URLs anteriores de un perfume: /perfume/<slug-antiguo>/ redirige (301) a la actual."""
    slug = models.SlugField(max_length=220, unique=True)
    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, related_name='slugs_antiguos')

    def __str__(self):
        return self.slug


@receiver([post_save, post_delete], sender=Presentacion)
def _actualizar_resumen_perfume(sender, instance, **kwargs):
    perfume = Perfume.objects.filter(pk=instance.perfume_id).first()
    if perfume:
        perfume.actualizar_resumen()


class PerfumeNota(models.Model):
    """Una nota dentro de la pirámide de un perfume."""
    NIVELES = [('salida', 'Salida'), ('corazon', 'Corazón'), ('fondo', 'Fondo')]

    perfume = models.ForeignKey(Perfume, on_delete=models.CASCADE, related_name='notas_perfume')
    nota = models.ForeignKey(Nota, on_delete=models.PROTECT, related_name='en_perfumes')
    nivel = models.CharField(max_length=8, choices=NIVELES, default='corazon')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Nota del perfume"
        verbose_name_plural = "Notas olfativas (pirámide)"
        constraints = [
            models.UniqueConstraint(fields=['perfume', 'nota', 'nivel'], name='nota_unica_por_nivel'),
        ]
        indexes = [models.Index(fields=['nota', 'perfume'], name='catalogo_pn_nota_perfume_idx')]

    def __str__(self):
        return f"{self.nota.nombre} ({self.get_nivel_display()})"


@receiver([post_save, post_delete], sender=PerfumeNota)
def _sincronizar_notas_perfume(sender, instance, **kwargs):
    perfume = Perfume.objects.filter(pk=instance.perfume_id).first()
    if perfume:
        perfume.sincronizar_notas()


class ImagenPortada(models.Model):
    """Diapositivas del carrusel de fondo del hero (home). Se gestionan desde el admin."""
    titulo = models.CharField(
        max_length=120, blank=True,
        help_text="Referencia interna (no se muestra en la web)."
    )
    imagen = models.ImageField(
        upload_to='portada/',
        help_text="Imagen de fondo. Recomendado: horizontal, mínimo 1920px de ancho."
    )
    orden = models.PositiveIntegerField(
        default=0,
        help_text="Menor número aparece primero."
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Imagen de portada"
        verbose_name_plural = "Imágenes de portada (carrusel)"

    def __str__(self):
        return self.titulo or f"Portada #{self.pk}"

TEMAS_PROMO = [
    ('especial', 'Oferta especial'),
    ('navidad', 'Navidad'),
    ('valentin', 'San Valentín'),
    ('madre', 'Día de la Madre'),
    ('padre', 'Día del Padre'),
    ('patrias', 'Fiestas Patrias'),
    ('black', 'Black Friday'),
]

# Encabezado de la sección del home (antetítulo, título). Se usa el del tema
# cuando todas las promociones visibles lo comparten; si no, el de 'especial'.
ENCABEZADO_TEMA = {
    'especial': ('Ofertas especiales', 'Promociones'),
    'navidad': ('Especial de Navidad', 'Regalos que se recuerdan'),
    'valentin': ('San Valentín', 'Para regalar en pareja'),
    'madre': ('Día de la Madre', 'Para ella, con gratitud'),
    'padre': ('Día del Padre', 'Clásicos para papá'),
    'patrias': ('Fiestas Patrias', 'Celebra el 18 con aroma'),
    'black': ('Black Friday', 'Precios que no vuelven'),
}


class Promocion(models.Model):
    """Promociones y combos gestionables desde el admin.
    Ej: título="2 x $10.000", descripción="Llévate dos fragancias seleccionadas".
    El tema cambia el estilo de la tarjeta en el home; las fechas la muestran/ocultan solas."""
    titulo = models.CharField(
        max_length=120,
        help_text="Ej: '2 Perfumes por $10.000' o 'Combo Pareja'."
    )
    descripcion = models.CharField(
        max_length=255, blank=True,
        help_text="Texto corto que explica la promoción."
    )
    precio = models.PositiveIntegerField(
        help_text="Precio total de la promoción, ej: 10000."
    )
    etiqueta = models.CharField(
        max_length=40, blank=True, default="Promoción",
        help_text="Etiqueta que aparece sobre la tarjeta (ej: 'Oferta', '2x1')."
    )
    imagen = models.ImageField(
        upload_to='promociones/', blank=True, null=True,
        help_text="Imagen opcional para la promoción."
    )
    perfumes = models.ManyToManyField(
        'Perfume', blank=True, related_name='promociones',
        help_text="Perfumes incluidos en la promoción (opcional)."
    )
    tema = models.CharField(
        max_length=12, choices=TEMAS_PROMO, default='especial',
        help_text="Estilo de la tarjeta en el home (colores, adorno y etiqueta)."
    )
    precio_normal = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Opcional. Precio sin la promoción; muestra el precio tachado, el % y el ahorro."
    )
    fecha_inicio = models.DateField(blank=True, null=True, help_text="Opcional. Desde este día aparece en el home.")
    fecha_fin = models.DateField(blank=True, null=True, help_text="Opcional. Último día visible; la tarjeta muestra «Hasta el …».")
    unidades = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Unidades disponibles. Si no hay fecha de término, es obligatorio: la tarjeta muestra «Hasta agotar N unidades».",
    )
    orden = models.PositiveIntegerField(default=0, help_text="Menor número aparece primero.")
    activo = models.BooleanField(default=True)
    # Combo automático (ej. 2 Smart Collection de 25 o 30 ml por $10.000): ver catalogo/combos.py
    combo_cantidad = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name="Cantidad del combo",
        help_text="Combo automático: cuántos perfumes forman el combo (ej. 2). Si lo llenas, el precio "
                  "de la promoción se aplica solo en la selección y en el pedido cuando el cliente junta "
                  "esa cantidad de perfumes que califican.",
    )
    combo_ml = models.CharField(
        max_length=40, blank=True, verbose_name="Tamaños que califican (ml)",
        help_text="Separados por coma, ej: 25,30. Vacío = cualquier tamaño.",
    )
    combo_nombre = models.CharField(
        max_length=80, blank=True, verbose_name="Nombre empieza con",
        help_text="Ej: Smart Collection. Vacío = cualquier perfume.",
    )
    combo_solo_incluidos = models.BooleanField(
        default=False, verbose_name="Solo los perfumes incluidos",
        help_text="Si lo marcas, solo califican los perfumes elegidos en «Perfumes».",
    )

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Promoción"
        verbose_name_plural = "Promociones"

    def __str__(self):
        return self.titulo

    def clean(self):
        errores = {}
        if self.precio_normal is not None and self.precio is not None and self.precio_normal <= self.precio:
            errores['precio_normal'] = "Debe ser mayor que el precio de la promoción."
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errores['fecha_fin'] = "Debe ser igual o posterior a la fecha de inicio."
        if not self.fecha_fin and not self.unidades:
            errores['fecha_fin'] = ("Indica la fecha de término o las unidades disponibles: "
                                    "la ley exige informar cuánto dura la promoción.")
        if self.combo_cantidad is not None and self.combo_cantidad < 2:
            errores['combo_cantidad'] = "Un combo necesita al menos 2 perfumes."
        if self.combo_ml and not all(p.strip().isdigit() for p in self.combo_ml.split(',') if p.strip()):
            errores['combo_ml'] = "Escribe solo números separados por coma, ej: 25,30."
        if errores:
            raise ValidationError(errores)

    @classmethod
    def vigentes(cls):
        """Activas y dentro de sus fechas (hora de Chile)."""
        hoy = timezone.localdate()
        return cls.objects.filter(activo=True).filter(
            models.Q(fecha_inicio__isnull=True) | models.Q(fecha_inicio__lte=hoy),
            models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=hoy),
        )

    @property
    def texto_etiqueta(self):
        """La etiqueta propia ('2x1'); si quedó la genérica, el nombre del tema."""
        propia = (self.etiqueta or '').strip()
        return propia if propia and propia != 'Promoción' else self.get_tema_display()

    @property
    def descuento(self):
        if self.precio_normal and self.precio and self.precio_normal > self.precio:
            return round((1 - self.precio / self.precio_normal) * 100)
        return None

    @property
    def ahorro(self):
        return self.precio_normal - self.precio if self.descuento else None

    @property
    def ml_combo(self):
        return {int(p) for p in (self.combo_ml or '').replace(' ', '').split(',') if p.isdigit()}

    def califica(self, presentacion):
        """¿Esta presentación cuenta para el combo automático?"""
        ml = self.ml_combo
        if ml and presentacion.ml not in ml:
            return False
        prefijo = (self.combo_nombre or '').strip().lower()
        if prefijo and not presentacion.perfume.nombre.lower().startswith(prefijo):
            return False
        if self.combo_solo_incluidos and presentacion.perfume_id not in {p.pk for p in self.perfumes.all()}:
            return False
        return True

class ImagenPerfume(models.Model):
    """Imágenes adicionales de un perfume (galería). La imagen principal sigue
    siendo el campo `imagen` del modelo Perfume; estas son las secundarias."""
    perfume = models.ForeignKey(
        'Perfume', on_delete=models.CASCADE, related_name='galeria'
    )
    imagen = models.ImageField(upload_to='perfumes/galeria/')
    orden = models.PositiveIntegerField(default=0, help_text="Menor número aparece primero.")

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Imagen de galería"
        verbose_name_plural = "Galería de imágenes"

    def __str__(self):
        return f"Imagen de {self.perfume.nombre}"


class Resena(models.Model):
    """Reseñas de clientes sobre un perfume. Se moderan desde el admin
    con el campo `aprobado` (solo las aprobadas se muestran en la web)."""
    perfume = models.ForeignKey(
        'Perfume', on_delete=models.CASCADE, related_name='resenas'
    )
    nombre = models.CharField(max_length=80, help_text="Nombre del cliente.")
    calificacion = models.PositiveSmallIntegerField(
        default=5, choices=[(i, f"{i} estrellas") for i in range(1, 6)]
    )
    comentario = models.TextField()
    aprobado = models.BooleanField(
        default=False, help_text="Marca para que la reseña aparezca en la web."
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Reseña"
        verbose_name_plural = "Reseñas"

    def __str__(self):
        return f"{self.nombre} — {self.perfume.nombre} ({self.calificacion}★)"

    @property
    def estrellas_llenas(self):
        return range(self.calificacion)

    @property
    def estrellas_vacias(self):
        return range(5 - self.calificacion)

class PaginaNosotros(models.Model):
    """Contenido editable de la sección Nosotros. Pensado como registro único
    (singleton): edita siempre la misma entrada desde el admin."""
    titulo = models.CharField(
        max_length=150, default="Nuestra Historia",
        help_text="Título principal de la sección."
    )
    subtitulo = models.CharField(
        max_length=200, blank=True,
        help_text="Frase corta bajo el título (opcional)."
    )
    contenido = models.TextField(
        help_text="Texto principal. Puedes separar en varios párrafos con saltos de línea."
    )
    # Bloques adicionales con su propio subtítulo (opcionales)
    subtitulo2 = models.CharField(max_length=200, blank=True, help_text="Segundo subtítulo (opcional).")
    contenido2 = models.TextField(blank=True, help_text="Texto del segundo bloque (opcional).")
    subtitulo3 = models.CharField(max_length=200, blank=True, help_text="Tercer subtítulo (opcional).")
    contenido3 = models.TextField(blank=True, help_text="Texto del tercer bloque (opcional).")
    imagen = models.ImageField(
        upload_to='nosotros/', blank=True, null=True,
        help_text="Imagen destacada de la sección (opcional)."
    )
    # Bloque de cierre / cita (opcional)
    cita = models.CharField(
        max_length=255, blank=True,
        help_text="Frase destacada o cita al final (opcional)."
    )
    cita_autor = models.CharField(
        max_length=120, blank=True, default="Dirección Instinto Olfativo",
        help_text="Autor/firma de la cita."
    )
    # Pilares (3 bloques)
    pilar1_titulo = models.CharField(max_length=80, blank=True, default="Autenticidad Absoluta")
    pilar1_texto = models.TextField(blank=True)
    pilar2_titulo = models.CharField(max_length=80, blank=True, default="Asesoría Experta")
    pilar2_texto = models.TextField(blank=True)
    pilar3_titulo = models.CharField(max_length=80, blank=True, default="Servicio Discreto")
    pilar3_texto = models.TextField(blank=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Página Nosotros"
        verbose_name_plural = "Página Nosotros"

    def __str__(self):
        return "Contenido de la página Nosotros"

    def save(self, *args, **kwargs):
        # Fuerza un único registro (siempre pk=1)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def cargar(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

class Pedido(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    cliente = models.CharField(max_length=120, blank=True, help_text="Nombre del cliente (opcional).")
    telefono = models.CharField(max_length=40, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default='pendiente')
    total = models.PositiveIntegerField(default=0, help_text="Total en CLP.")
    stock_descontado = models.BooleanField(default=False, help_text="Marca interna: evita descontar stock dos veces.")
    descuento = models.PositiveIntegerField(default=0, help_text="Descuento por combos automáticos (CLP). Ya está restado del total.")
    detalle_descuento = models.CharField(max_length=255, blank=True, verbose_name="Detalle del descuento")
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = "Venta / Pedido"
        verbose_name_plural = "Ventas / Pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} — {self.get_estado_display()} — ${self.total}"

    @property
    def codigo(self):
        return f"IO-{self.pk:06d}" if self.pk else "—"

    def recalcular_total(self):
        self.total = max(0, sum(i.subtotal for i in self.items.all()) - (self.descuento or 0))
        return self.total


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    perfume = models.ForeignKey('Perfume', on_delete=models.SET_NULL, null=True, related_name='ventas')
    presentacion = models.ForeignKey('Presentacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas')
    nombre = models.CharField(max_length=200, help_text="Nombre guardado (por si el perfume se elimina).")
    precio = models.PositiveIntegerField(default=0)
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Producto del pedido"
        verbose_name_plural = "Productos del pedido"

    def __str__(self):
        return f"{self.cantidad}× {self.nombre}"

    @property
    def subtotal(self):
        return self.precio * self.cantidad


class LimiteSolicitud(models.Model):
    """Conteo anónimo de envíos por IP (hash, no la IP) para frenar abusos. Se borra a las 24 h.
    Lo usa catalogo/limites.py; no aparece en el admin."""
    clave = models.CharField(max_length=40)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "límite de solicitudes"
        verbose_name_plural = "límites de solicitudes"
        indexes = [models.Index(fields=["clave", "creado"], name="limite_clave_creado_idx")]
