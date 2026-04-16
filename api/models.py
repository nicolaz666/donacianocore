import logging
from django.db import models, transaction
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.db.models import F, Sum
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class GrupoImagenes(models.Model):
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to='productos/')
    es_principal = models.BooleanField(default=False)
    descripcion = models.CharField(max_length=255, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.es_principal:
            GrupoImagenes.objects.filter(
                producto=self.producto,
                es_principal=True
            ).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagen de {self.producto} - {'Principal' if self.es_principal else 'Secundaria'}"


class Proveedor(models.Model):
    nombre = models.CharField(max_length=255)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=12)
    nit = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre


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


class Material(models.Model):
    descripcion = models.CharField(max_length=255)
    color = models.CharField(max_length=50)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.IntegerField()
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)

    def __str__(self):
        return self.descripcion


class CompraMaterial(models.Model):
    total = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(default=timezone.now)
    proveedor = models.ForeignKey('Proveedor', on_delete=models.CASCADE)

    def __str__(self):
        return f"Compra {self.id} - Total: {self.total}"


class DetalleCompraMaterial(models.Model):
    material = models.ForeignKey('Material', on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    compra = models.ForeignKey('CompraMaterial', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.material} - Cantidad: {self.cantidad}"


class Cliente(models.Model):
    nombre = models.CharField(max_length=255)
    apellido = models.CharField(max_length=255)
    identificacion = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    def total_ventas(self):
        return self.ventas.count()


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


# ---------------------------------------------------------------------------
# FIX P1: Race condition en generación de números de serie
#
# PROBLEMA ORIGINAL:
#   ContadorUnidadProducto.incrementar_contador_diario() leía el contador,
#   sumaba 1 en Python y guardaba. Con dos requests simultáneos ambos leían
#   el mismo valor y generaban números de serie duplicados (violación de
#   unique=True en numeroSerie).
#
# SOLUCIÓN:
#   Se reemplaza el patrón read-modify-write por una operación atómica en BD:
#   - select_for_update() bloquea la fila para otros procesos hasta que la
#     transacción termine (lock pesimista).
#   - F('contador') + 1 delega la suma a la BD en una sola operación SQL,
#     eliminando el window de race condition.
#   - El modelo ContadorUnidadProducto se conserva para no romper migraciones
#     existentes. Solo se reescriben los métodos de clase.
# ---------------------------------------------------------------------------
class ContadorUnidadProducto(models.Model):
    contador = models.IntegerField(default=0)
    fecha = models.DateField(default=timezone.now)

    @classmethod
    def obtener_contador_diario(cls):
        """
        Obtiene el contador actual para el día de hoy.
        Usa select_for_update para evitar lecturas sucias en entornos concurrentes.
        """
        from datetime import date
        hoy = date.today()

        with transaction.atomic():
            obj, created = cls.objects.select_for_update().get_or_create(
                id=1,
                defaults={'contador': 0, 'fecha': hoy}
            )
            if obj.fecha != hoy:
                obj.contador = 0
                obj.fecha = hoy
                obj.save(update_fields=['contador', 'fecha'])
            return obj.contador

    @classmethod
    def incrementar_contador_diario(cls):
        """
        Incrementa atómicamente el contador del día actual y retorna el nuevo valor.

        Usa select_for_update() + F() para garantizar que en entornos con
        múltiples workers nunca se genere el mismo número dos veces.
        """
        from datetime import date
        hoy = date.today()

        with transaction.atomic():
            obj, created = cls.objects.select_for_update().get_or_create(
                id=1,
                defaults={'contador': 1, 'fecha': hoy}
            )

            if created:
                # Fila recién creada, contador ya es 1
                logger.debug("Contador diario creado para fecha %s", hoy)
                return 1

            if obj.fecha != hoy:
                # Nuevo día: reiniciar contador
                obj.contador = 1
                obj.fecha = hoy
                obj.save(update_fields=['contador', 'fecha'])
                logger.debug("Contador diario reiniciado para fecha %s", hoy)
                return 1

            # Mismo día: incrementar con operación atómica en BD
            cls.objects.filter(id=1).update(contador=F('contador') + 1)
            obj.refresh_from_db()
            return obj.contador


class UnidadProducto(models.Model):
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE)
    venta = models.ForeignKey('Ventas', on_delete=models.CASCADE, null=True, blank=True)
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
        if self.numeroSerie:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.tipo} - {self.numeroSerie} ({self.estado})"


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

    # ---------------------------------------------------------------------------
    # FIX P2 (parcial): total_abonado usando aggregate en lugar de sum() en Python
    #
    # PROBLEMA ORIGINAL:
    #   sum(abono.monto_abonado for abono in self.abonos.all())
    #   Cargaba TODOS los objetos Abono en memoria para sumarlos en Python.
    #   En un listado de 500 ventas con 10 abonos c/u = 5.000 objetos en RAM.
    #
    # SOLUCIÓN:
    #   Delegar la suma a la BD con aggregate(Sum(...)). Una sola query SQL
    #   retorna el total directamente. El resultado es idéntico funcionalmente.
    # ---------------------------------------------------------------------------
    def total_abonado(self):
        """Calcula el total abonado con una sola query SQL (aggregate)."""
        resultado = self.abonos.aggregate(total=Sum('monto_abonado'))
        return resultado['total'] or 0

    @property
    def debe(self):
        """Calcula cuánto debe el cliente (total - total_abonado)."""
        return max(0, self.total - self.total_abonado())

    # ---------------------------------------------------------------------------
    # FIX P2 (bug semántico): marcar_pagado ya no cambia estado a 'cancelado'
    #
    # PROBLEMA ORIGINAL:
    #   Cuando una venta quedaba completamente pagada, el código la marcaba
    #   como estado='cancelado'. Eso era un bug conceptual: "cancelado" debe
    #   reservarse para ventas que no se completaron, no para ventas pagadas.
    #   El estado correcto al pagar completamente es 'entregado' (o el que
    #   tenga la venta en ese momento; no se fuerza ningún estado aquí).
    #
    # SOLUCIÓN:
    #   marcar_pagado() solo actualiza is_pagado. El estado del flujo de la
    #   venta (pendiente → en_proceso → entregado) se maneja por separado.
    #   cancelar_venta() sigue siendo el único camino hacia estado='cancelado'.
    # ---------------------------------------------------------------------------
    def marcar_pagado(self):
        """
        Actualiza is_pagado según el total de abonos.
        NO modifica el estado del flujo de la venta.
        """
        total_abonado = self.total_abonado()
        nuevo_is_pagado = total_abonado >= self.total and total_abonado > 0

        if self.is_pagado != nuevo_is_pagado:
            self.is_pagado = nuevo_is_pagado
            self.save(update_fields=['is_pagado'])
            logger.info(
                "Venta %s: is_pagado actualizado a %s (abonado: %s / total: %s)",
                self.id, self.is_pagado, total_abonado, self.total
            )

    def cancelar_venta(self, motivo):
        """Cancela la venta y almacena la fecha y el motivo de cancelación."""
        self.estado = 'cancelado'
        self.fecha_cancelacion = timezone.now()
        self.motivo_cancelacion = motivo
        self.save()
        logger.info("Venta %s cancelada. Motivo: %s", self.id, motivo)


class Abono(models.Model):
    venta = models.ForeignKey('Ventas', on_delete=models.CASCADE, related_name='abonos')
    fecha_abono = models.DateTimeField(default=timezone.now)
    monto_abonado = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(max_length=50, null=True, blank=True)
    comentario = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Abono de {self.monto_abonado} - Venta {self.venta.id} - Fecha: {self.fecha_abono}"


class DetalleVenta(models.Model):
    venta = models.ForeignKey('Ventas', on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    unidad = models.ForeignKey('UnidadProducto', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Detalle de Venta {self.id} - Producto: {self.producto.tipo} - Cantidad: {self.cantidad}"


# ---------------------------------------------------------------------------
# SIGNALS — se conservan para no romper el comportamiento existente.
# Los comentarios explican qué hace cada uno y por qué no se eliminan aún.
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=UnidadProducto)
def generar_numero_serie(sender, instance, **kwargs):
    """
    Genera el numeroSerie antes de guardar si aún no tiene uno.
    Ahora llama a incrementar_contador_diario() que es thread-safe (FIX P1).
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

            ahora = datetime.now()
            ano_mes = f"{ahora.year % 100:02d}{ahora.month:02d}"

            # Ahora es thread-safe gracias al FIX P1
            contador = ContadorUnidadProducto.incrementar_contador_diario()

            instance.numeroSerie = f"{prefijo}-{ano_mes}{contador}"
            logger.debug("Número de serie generado: %s", instance.numeroSerie)

        except Exception as e:
            logger.error("Error generando número de serie: %s", e, exc_info=True)
            import time
            instance.numeroSerie = f"PROD-{int(time.time())}"


@receiver(post_save, sender=Abono)
def actualizar_pago_al_guardar_abono(sender, instance, created, **kwargs):
    """Se ejecuta cada vez que se crea o modifica un abono."""
    instance.venta.marcar_pagado()


@receiver(post_delete, sender=Abono)
def actualizar_pago_al_eliminar_abono(sender, instance, **kwargs):
    """Se ejecuta cuando se elimina un abono."""
    instance.venta.marcar_pagado()


@receiver(post_save, sender=DetalleVenta)
def crear_o_actualizar_unidades_producto(sender, instance, created, **kwargs):
    """
    Maneja dos casos:
    1. Venta de unidad específica: actualiza la unidad existente a 'vendido'.
    2. Venta por plantilla: crea N unidades nuevas con estado 'vendido'.
    """
    if created:
        if instance.unidad:
            logger.debug("Venta de unidad específica: %s", instance.unidad.numeroSerie)
            instance.unidad.estado = 'vendido'
            instance.unidad.venta = instance.venta
            instance.unidad.save()
            logger.info("Unidad %s actualizada a 'vendido'", instance.unidad.numeroSerie)

        else:
            logger.debug(
                "Venta por plantilla: creando %d unidades para producto %s",
                instance.cantidad, instance.producto
            )
            unidades_creadas = []
            try:
                with transaction.atomic():
                    for _ in range(instance.cantidad):
                        unidad = UnidadProducto.objects.create(
                            producto=instance.producto,
                            venta=instance.venta,
                            estado='vendido'
                        )
                        unidades_creadas.append(unidad.numeroSerie)

                logger.info(
                    "Creadas %d unidades para %s. Series: %s",
                    instance.cantidad, instance.producto, ', '.join(unidades_creadas)
                )
            except Exception as e:
                logger.error(
                    "Error creando unidades para DetalleVenta %s: %s",
                    instance.id, e, exc_info=True
                )


@receiver(post_delete, sender=DetalleVenta)
def eliminar_unidades_producto_al_eliminar_detalle_venta(sender, instance, **kwargs):
    """Elimina las UnidadProducto asociadas cuando se borra un DetalleVenta."""
    try:
        unidades = UnidadProducto.objects.filter(
            producto=instance.producto,
            venta=instance.venta
        )
        count = unidades.count()
        unidades.delete()
        logger.info("Eliminadas %d unidades para DetalleVenta %s", count, instance.id)
    except Exception as e:
        logger.error("Error eliminando unidades: %s", e, exc_info=True)


@receiver(post_save, sender=DetalleCompraMaterial)
def actualizar_stock_material(sender, instance, created, **kwargs):
    """
    Actualiza el stock del material cuando se crea un detalle de compra.
    Usa F() para evitar race conditions en actualizaciones de stock.
    """
    if created:
        Material.objects.filter(pk=instance.material_id).update(
            stock=F('stock') + instance.cantidad
        )
        logger.info(
            "Stock actualizado: %s (+%d)",
            instance.material.descripcion, instance.cantidad
        )


@receiver(post_save, sender=UnidadProducto)
def log_creacion_unidad_producto(sender, instance, created, **kwargs):
    """Log estructurado al crear una nueva unidad de producto."""
    if created:
        logger.info(
            "Nueva unidad creada: serie=%s tipo=%s estado=%s",
            instance.numeroSerie, instance.producto.tipo, instance.estado
        )
