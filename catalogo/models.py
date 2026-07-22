from django.db import models

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to='marcas/', blank=True, null=True)
    descripcion = models.TextField(blank=True, verbose_name="Historia de la marca")

    class Meta:
        verbose_name_plural = "Marcas"

    def __str__(self):
        return self.nombre

class FamiliaOlfativa(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class Perfume(models.Model):
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('U', 'Unisex'),
    ]

    nombre = models.CharField(max_length=200)
    marca = models.ForeignKey(Marca, on_delete=models.CASCADE, related_name='productos')
    familia = models.ForeignKey(FamiliaOlfativa, on_delete=models.SET_NULL, null=True, blank=True)
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, default='U')
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=0) # Ideal para CLP
    stock = models.PositiveIntegerField(default=0)
    es_oferta = models.BooleanField(default=False, verbose_name="¿Es oferta?")
    precio_oferta = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True, verbose_name="Precio de oferta")
    imagen = models.ImageField(upload_to='perfumes/', verbose_name="Imagen Principal")
    notas_salida = models.CharField(max_length=255, help_text="Lo que se siente al aplicar")
    notas_corazon = models.CharField(max_length=255, help_text="El alma del perfume")
    notas_fondo = models.CharField(max_length=255, help_text="Lo que perdura en la piel")
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField(default=False, help_text="Mostrar en la página de inicio")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.marca.nombre} - {self.nombre}"
    
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

class Promocion(models.Model):
    """Promociones y combos gestionables desde el admin.
    Ej: título="2 x $10.000", descripción="Llévate dos fragancias seleccionadas"."""
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
    # Opcional: relaciona los perfumes incluidos (solo informativo/visual).
    perfumes = models.ManyToManyField(
        'Perfume', blank=True, related_name='promociones',
        help_text="Perfumes incluidos en la promoción (opcional)."
    )
    orden = models.PositiveIntegerField(default=0, help_text="Menor número aparece primero.")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Promoción"
        verbose_name_plural = "Promociones"

    def __str__(self):
        return self.titulo
