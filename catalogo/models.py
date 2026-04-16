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
    
    # Imagen de alta calidad para el catálogo
    imagen = models.ImageField(upload_to='perfumes/', verbose_name="Imagen Principal")
    
    # Pirámide Olfativa (Esencial para la elegancia del sitio)
    notas_salida = models.CharField(max_length=255, help_text="Lo que se siente al aplicar")
    notas_corazon = models.CharField(max_length=255, help_text="El alma del perfume")
    notas_fondo = models.CharField(max_length=255, help_text="Lo que perdura en la piel")
    
    # Control de visibilidad
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField(default=False, help_text="Mostrar en la página de inicio")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.marca.nombre} - {self.nombre}"