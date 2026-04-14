from django.db import models, transaction,IntegrityError
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.core.exceptions import ValidationError

class GrupoImagenes(models.Model):
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to='productos/')
    es_principal = models.BooleanField(default=False)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Si esta imagen se marca como principal, desmarcar las demás del mismo producto
        if self.es_principal:
            GrupoImagenes.objects.filter(
                producto=self.producto,
                es_principal=True
            ).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagen de {self.producto} - {'Principal' if self.es_principal else 'Secundaria'}"

# Modelo de Proveedor
class Proveedor(models.Model):
    nombre = models.CharField(max_length=255)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=12)  # Verifica si necesitas más caracteres
    nit = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre

# Modelo de Categoría
class Categoria(models.Model):
    TIPO_CATEGORIA_CHOICES = [
        ('producto', 'Producto'),
        ('material', 'Material'),
        ('ambos', 'Ambos'),
    ]

    nombre = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50, choices=TIPO_CATEGORIA_CHOICES)

    def __str__(self):
        return self.nombre

# Modelo de Material
class Material(models.Model):
    descripcion = models.CharField(max_length=255)
    color = models.CharField(max_length=50)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.IntegerField()
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)

    def __str__(self):
        return self.descripcion

# Modelo de Compra de Material
class CompraMaterial(models.Model):
    total = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(default=timezone.now)  # Se añade default
    proveedor = models.ForeignKey('Proveedor', on_delete=models.CASCADE)  # Corregido Proveedores a Proveedor

    def __str__(self):
        return f"Compra {self.id} - Total: {self.total}"

# Modelo de Detalle de Compra de Material
class DetalleCompraMaterial(models.Model):
    material = models.ForeignKey('Material', on_delete=models.CASCADE)  # Corregido Materiales a Material
    cantidad = models.IntegerField()
    compra = models.ForeignKey('CompraMaterial', on_delete=models.CASCADE)  # Corregido Compras a CompraMaterial

    def __str__(self):
        return f"{self.material} - Cantidad: {self.cantidad}"

# Modelo de Cliente
class Cliente(models.Model):
    nombre = models.CharField(max_length=255)
    apellido = models.CharField(max_length=255)
    identificacion = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    def total_ventas(self):
        return self.ventas.count()

# Modelo de Dirección
class Direccion(models.Model):
    cliente = models.ForeignKey(Cliente, related_name='direcciones', on_delete=models.CASCADE)
    destinatario = models.CharField(max_length=255)
    celular = models.CharField(max_length=15, null=True, blank=True)
    pais = models.CharField(max_length=100)
    departamento = models.CharField(max_length=100)
    ciudad = models.CharField(max_length=100)
    nomenclatura = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.destinatario}, {self.ciudad}, {self.pais}"

# Modelo de Producto
class Producto(models.Model):

    COLORES_CHOICES = [
        ('Naranja', 'Naranja'),
        ('Negro', 'Negro'),
        ('Roble', 'Roble'),
        ('Crudo', 'Crudo'),
        ('Azul Celeste', 'Azul Celeste'),
        ('Azul Rey', 'Azul Rey'),
        ('Amarillo', 'Amarillo'),
        ('Rojo', 'Rojo'),
        ('Rosado', 'Rosado'),
        ('Verde Claro', 'Verde Claro'),
        ('Verde Militar', 'Verde Militar'),
        ('Crudo Amarillo', 'Crudo Amarillo'),
        ('Blanco Natural', 'Blanco Natural'),
    ]

    tipo = models.CharField(max_length=255, choices=[
        ('Tejido', 'Tejido'),
        ('Rejo', 'Rejo'),
        ('Plano', 'Plano'),
        ('Sencillo', 'Sencillo'),
    ])

    modelo = models.CharField(max_length=255, choices=[
        ('4 Tornillos', '4 Tornillos'),
        ('Clasico', 'Clásico'),
        ('Charol', 'Charol'),
    ])

    precio = models.DecimalField(max_digits=12, decimal_places=2)

    colorPrincipal = models.CharField(max_length=255, choices=[
        ('Negro', 'Negro'),
        ('Roble', 'Roble'),
        ('Crudo', 'Crudo'),
        ('Chocolate', 'Chocolate'),
        ('Envejecido', 'Envejecido'),
    ])

    colorTejido = models.CharField(max_length=50)

    colorCordon1 = models.CharField(max_length=255, choices=COLORES_CHOICES, blank=True, null=True)
    colorCordon2 = models.CharField(max_length=255, choices=COLORES_CHOICES, blank=True, null=True)
    colorSogaRienda = models.CharField(max_length=255, choices=COLORES_CHOICES, blank=True, null=True)
    colorManzanos = models.CharField(max_length=255, choices=COLORES_CHOICES, blank=True, null=True)
    colorCoronas = models.CharField(max_length=255, choices=COLORES_CHOICES, blank=True, null=True)

    observaciones = models.TextField(blank=True, null=True)

    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.categoria.nombre}, {self.tipo}, {self.modelo}"
    
# Modificar el modelo ContadorUnidadProducto para manejar fechas
class ContadorUnidadProducto(models.Model):
    contador = models.IntegerField(default=0)
    fecha = models.DateField(default=timezone.now)  # NUEVO: campo para la fecha

    @classmethod
    def obtener_contador_diario(cls):
        """
        Obtiene el contador para el día actual.
        Si es un nuevo día, reinicia el contador a 0.
        """
        from datetime import date
        hoy = date.today()

        obj, created = cls.objects.get_or_create(id=1)

        # Si es un nuevo día, reiniciar contador
        if obj.fecha != hoy:
            obj.contador = 0
            obj.fecha = hoy
            obj.save()
            print(f"🔄 Contador reiniciado para nueva fecha: {hoy}")

        return obj.contador

    @classmethod
    def incrementar_contador_diario(cls):
        """
        Incrementa el contador para el día actual.
        """
        from datetime import date
        hoy = date.today()

        obj, created = cls.objects.get_or_create(id=1)

        # Si es un nuevo día, reiniciar antes de incrementar
        if obj.fecha != hoy:
            obj.contador = 0
            obj.fecha = hoy
            print(f"🔄 Contador reiniciado para nueva fecha: {hoy}")

        obj.contador += 1
        obj.save()
        return obj.contador



# AGREGAR ESTE CAMPO AL MODELO UnidadProducto
class UnidadProducto(models.Model):
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE)
    venta = models.ForeignKey('Ventas', on_delete=models.CASCADE, null=True, blank=True)
    # ↓ CAMBIO: Agregar blank=True para permitir vacío antes del signal
    numeroSerie = models.CharField(max_length=100, unique=True, blank=True)
    estado = models.CharField(max_length=10, choices=[
        ('disponible', 'Disponible'),
        ('vendido', 'Vendido'),
        ('reparacion', 'En reparación'),
    ])
    fechaCreacion = models.DateTimeField(default=timezone.now)

    def clean(self):
        if self.estado == 'vendido' and self.venta is None:
            raise ValidationError(
                "Una unidad marcada como vendida debe estar asociada a una venta."
            )

        if self.estado != 'vendido' and self.venta is not None:
            raise ValidationError(
                "Solo las unidades vendidas pueden tener una venta asociada."
            )

    def save(self, *args, **kwargs):
        # ↓ CAMBIO: Validar solo si ya tiene numeroSerie
        if self.numeroSerie:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.tipo} - {self.numeroSerie} ({self.estado})"

# Signal para manejar la creación de números de serie



# Modelo de Ventas - CORREGIDO
class Ventas(models.Model):
    ESTADO_VENTA_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_proceso', 'En Proceso'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ]

    total = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_venta = models.DateTimeField(default=timezone.now)
    fecha_entrega_estimada = models.DateTimeField()
    fecha_entrega_real = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_VENTA_CHOICES, default='pendiente')
    is_pagado = models.BooleanField(default=False)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    motivo_cancelacion = models.TextField(null=True, blank=True)
    comentarios = models.TextField(null=True, blank=True)
    cliente = models.ForeignKey('Cliente', related_name='ventas', on_delete=models.CASCADE)

    def __str__(self):
        return f"Venta {self.id} - Total: {self.total} - Estado: {self.estado}"

    def total_abonado(self):
        """Calcula el total abonado sumando todos los abonos relacionados."""
        return sum(abono.monto_abonado for abono in self.abonos.all())

    @property
    def debe(self):
        """Calcula cuánto debe el cliente (total - total_abonado)"""
        return max(0, self.total - self.total_abonado())

    def marcar_pagado(self):
        """
        Marca o desmarca la venta como pagada según el total de abonos.
        Si el pago se marca como realizado, se cambia el estado a 'cancelado'.
        """
        total_abonado = self.total_abonado()
        estado_anterior = self.is_pagado

        if total_abonado >= self.total and total_abonado > 0:
            self.is_pagado = True
            self.estado = 'cancelado'  # Cambia el estado a cancelado cuando se marque como pagado
        else:
            self.is_pagado = False

        # Solo guarda si cambió el estado para evitar saves innecesarios
        if estado_anterior != self.is_pagado or self.estado == 'cancelado':
            self.save(update_fields=['is_pagado', 'estado'])
            print(f"Venta {self.id}: Estado de pago actualizado a {self.is_pagado} y estado de la venta a {self.estado}")



    def cancelar_venta(self, motivo):
        """Cancela la venta y almacena la fecha y el motivo de cancelación."""
        self.estado = 'cancelado'
        self.fecha_cancelacion = timezone.now()
        self.motivo_cancelacion = motivo
        self.save()
        
# Modelo de Abonos
class Abono(models.Model):
    venta = models.ForeignKey('Ventas', on_delete=models.CASCADE, related_name='abonos')
    fecha_abono = models.DateTimeField(default=timezone.now)
    monto_abonado = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(max_length=50, null=True, blank=True)  # Opcional: registrar método de pago
    comentario = models.TextField(null=True, blank=True)  # Opcional: notas sobre el abono

    def __str__(self):
        return f"Abono de {self.monto_abonado} - Venta {self.venta.id} - Fecha: {self.fecha_abono}"




# Modelo de Detalle de Venta - CORREGIDO
class DetalleVenta(models.Model):
    venta = models.ForeignKey('Ventas', on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    unidad = models.ForeignKey('UnidadProducto', on_delete=models.SET_NULL, null=True, blank=True)
    # ↑ NUEVO: Para ventas de unidades específicas

    def __str__(self):
        return f"Detalle de Venta {self.id} - Producto: {self.producto.tipo} - Cantidad: {self.cantidad}"

# SIGNALS

# Signal para generar automáticamente el numeroSerie
@receiver(pre_save, sender=UnidadProducto)
def generar_numero_serie(sender, instance, **kwargs):
    """
    ALTERNATIVA: Mantiene AAMM pero con contador que se reinicia diariamente
    FORMATO: TIPO-AAMMX (ej: TEJ-25061 para Junio 2025, contador 1 del día)
    """
    if not instance.numeroSerie:
        try:
            from datetime import datetime

            tipo_map = {
                'Tejido': 'TEJ',
                'Rejo': 'REJ',
                'Plano': 'PLA',
                'Sencillo': 'SEN'
            }

            prefijo = tipo_map.get(instance.producto.tipo, 'PROD')

            # Obtener año y mes actual (formato AAMM)
            ahora = datetime.now()
            ano_mes = f"{ahora.year % 100:02d}{ahora.month:02d}"

            # Usar contador diario (se reinicia cada día)
            contador = ContadorUnidadProducto.incrementar_contador_diario()

            # Formato: TIPO-AAMMX (ej: TEJ-25061 para Junio 2025, unidad 1 del día)
            instance.numeroSerie = f"{prefijo}-{ano_mes}{contador}"
            print(f"📋 Número de serie generado: {instance.numeroSerie}")

        except Exception as e:
            print(f"❌ Error generando número de serie: {e}")
            import time
            instance.numeroSerie = f"PROD-{int(time.time())}"

@receiver(post_save, sender=Abono)
def actualizar_pago_al_guardar_abono(sender, instance, created, **kwargs):
    """Se ejecuta cada vez que se crea o modifica un abono"""
    instance.venta.marcar_pagado()


@receiver(post_delete, sender=Abono)
def actualizar_pago_al_eliminar_abono(sender, instance, **kwargs):
    """Se ejecuta cuando se elimina un abono"""
    instance.venta.marcar_pagado()


@receiver(post_save, sender=DetalleVenta)
def crear_o_actualizar_unidades_producto(sender, instance, created, **kwargs):
    """
    Maneja dos casos:
    1. Venta por plantilla: Crea nuevas unidades
    2. Venta de unidad específica: Actualiza la unidad existente
    """
    if created:
        # CASO 1: Si hay una unidad específica asociada (venta de unidad específica)
        if instance.unidad:
            print(f"🔧 Venta de unidad específica: {instance.unidad.numeroSerie}")
            
            # Actualizar la unidad existente
            instance.unidad.estado = 'vendido'
            instance.unidad.venta = instance.venta
            instance.unidad.save()
            
            print(f"✅ Unidad {instance.unidad.numeroSerie} actualizada a 'vendido'")
        
        # CASO 2: Venta por plantilla - crear nuevas unidades
        else:
            print(f"📦 Venta por plantilla: creando {instance.cantidad} unidades")
            
            unidades_creadas = []
            try:
                with transaction.atomic():
                    for i in range(instance.cantidad):
                        unidad = UnidadProducto.objects.create(
                            producto=instance.producto,
                            venta=instance.venta,
                            estado='vendido'
                        )
                        unidades_creadas.append(unidad.numeroSerie)

                    print(f"✅ Creadas {instance.cantidad} unidades para {instance.producto}")
                    print(f"   Números de serie: {', '.join(unidades_creadas)}")

            except Exception as e:
                print(f"❌ Error creando unidades para DetalleVenta {instance.id}: {e}")




@receiver(post_delete, sender=DetalleVenta)
def eliminar_unidades_producto_al_eliminar_detalle_venta(sender, instance, **kwargs):
    """
    Se ejecuta cuando se elimina un DetalleVenta.
    Elimina las UnidadProducto asociadas a ese detalle.
    """
    try:
        unidades_eliminadas = UnidadProducto.objects.filter(
            producto=instance.producto,
            venta=instance.venta
        )
        count = unidades_eliminadas.count()
        unidades_eliminadas.delete()
        print(f"🗑️ Eliminadas {count} unidades de producto para DetalleVenta eliminado")
    except Exception as e:
        print(f"❌ Error eliminando unidades: {e}")


@receiver(post_save, sender=DetalleCompraMaterial)
def actualizar_stock_material(sender, instance, created, **kwargs):
    """Actualiza el stock del material cuando se crea un detalle de compra"""
    if created:
        instance.material.stock += instance.cantidad
        instance.material.save(update_fields=['stock'])
        print(f"📦 Stock actualizado: {instance.material.descripcion} (+{instance.cantidad})")


# Signal adicional para debug y logging
@receiver(post_save, sender=UnidadProducto)
def log_creacion_unidad_producto(sender, instance, created, **kwargs):
    """Log cuando se crea una nueva unidad de producto"""
    if created:
        # CAMBIAR: instance.producto.nombre → instance.producto.tipo
        print(f"🏷️ Nueva unidad creada: {instance.numeroSerie} - {instance.producto.tipo} - Estado: {instance.estado}")
