"""
api/services.py — Capa de servicios de donacianocore.

PROPÓSITO:
    Centraliza la lógica de negocio compleja en funciones independientes
    de los modelos y las vistas. Los modelos persisten datos; los servicios
    coordinan operaciones que involucran varios modelos.

USO EN VISTAS (ejemplo):
    from api.services import VentaService

    # En lugar de manejar la lógica directamente en la vista:
    venta = VentaService.crear_venta(
        cliente=cliente,
        fecha_entrega_estimada=fecha,
        detalles=[{'producto': p, 'cantidad': 2}]
    )

NOTAS:
    - Los signals existentes siguen activos. Esta capa no los reemplaza;
      los complementa para operaciones de alto nivel.
    - Cada método es una unidad testeable de forma aislada.
    - Todas las operaciones que modifican múltiples tablas usan
      transaction.atomic() para garantizar consistencia.
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import (
    Ventas, DetalleVenta, Abono, UnidadProducto,
    CompraMaterial, DetalleCompraMaterial, Material
)

logger = logging.getLogger(__name__)


class VentaService:
    """Operaciones de negocio relacionadas con Ventas y sus detalles."""

    @staticmethod
    @transaction.atomic
    def crear_venta(cliente, fecha_entrega_estimada, detalles: list, comentarios: str = '') -> Ventas:
        """
        Crea una venta completa con sus detalles en una sola transacción.

        Args:
            cliente: instancia de Cliente.
            fecha_entrega_estimada: datetime con la fecha estimada de entrega.
            detalles: lista de dicts con claves 'producto' (Producto) y
                      'cantidad' (int). Opcionalmente 'unidad' (UnidadProducto)
                      para ventas de unidades específicas del inventario.
            comentarios: texto libre opcional.

        Returns:
            Instancia de Ventas creada y guardada.

        Raises:
            ValidationError: si algún detalle tiene cantidad <= 0 o si una
                             unidad específica ya está vendida.
        """
        if not detalles:
            raise ValidationError("La venta debe tener al menos un detalle.")

        # Calcular total sumando precio * cantidad por cada línea
        total = Decimal('0')
        for detalle in detalles:
            cantidad = detalle.get('cantidad', 0)
            if cantidad <= 0:
                raise ValidationError(
                    f"La cantidad para {detalle['producto']} debe ser mayor a 0."
                )
            # Si es venta de unidad específica, verificar que esté disponible
            unidad = detalle.get('unidad')
            if unidad and unidad.estado != 'disponible':
                raise ValidationError(
                    f"La unidad {unidad.numeroSerie} no está disponible "
                    f"(estado actual: {unidad.estado})."
                )
            total += detalle['producto'].precio * cantidad

        venta = Ventas.objects.create(
            cliente=cliente,
            total=total,
            fecha_entrega_estimada=fecha_entrega_estimada,
            comentarios=comentarios,
        )

        for detalle in detalles:
            DetalleVenta.objects.create(
                venta=venta,
                producto=detalle['producto'],
                cantidad=detalle['cantidad'],
                unidad=detalle.get('unidad'),
            )

        logger.info(
            "Venta %s creada para cliente %s. Total: %s. Líneas: %d",
            venta.id, cliente, total, len(detalles)
        )
        return venta

    @staticmethod
    @transaction.atomic
    def registrar_abono(venta: Ventas, monto: Decimal, metodo_pago: str = '', comentario: str = '') -> Abono:
        """
        Registra un abono sobre una venta y actualiza su estado de pago.

        Args:
            venta: instancia de Ventas.
            monto: monto a abonar (debe ser > 0).
            metodo_pago: texto libre, ej: 'efectivo', 'transferencia'.
            comentario: nota opcional sobre el abono.

        Returns:
            Instancia de Abono creada.

        Raises:
            ValidationError: si el monto es <= 0 o si la venta está cancelada.
        """
        if monto <= 0:
            raise ValidationError("El monto del abono debe ser mayor a 0.")

        if venta.estado == 'cancelado':
            raise ValidationError(
                f"No se puede abonar a la venta {venta.id} porque está cancelada."
            )

        abono = Abono.objects.create(
            venta=venta,
            monto_abonado=monto,
            metodo_pago=metodo_pago,
            comentario=comentario,
        )
        # marcar_pagado() se dispara también desde el signal post_save de Abono,
        # pero llamarlo aquí explícitamente permite usar el servicio sin signals.
        venta.marcar_pagado()

        logger.info(
            "Abono %s registrado en venta %s. Monto: %s. Método: %s. Pagado: %s",
            abono.id, venta.id, monto, metodo_pago, venta.is_pagado
        )
        return abono

    @staticmethod
    @transaction.atomic
    def cancelar_venta(venta: Ventas, motivo: str) -> Ventas:
        """
        Cancela una venta y libera las unidades de producto asociadas.

        Al cancelar:
        - El estado de la venta pasa a 'cancelado'.
        - Las unidades de inventario vuelven a estado 'disponible'.
        - Los abonos existentes no se eliminan (quedan como registro).

        Args:
            venta: instancia de Ventas a cancelar.
            motivo: descripción del motivo de cancelación.

        Returns:
            La venta actualizada.

        Raises:
            ValidationError: si la venta ya está cancelada o entregada.
        """
        if venta.estado in ('cancelado', 'entregado'):
            raise ValidationError(
                f"No se puede cancelar una venta en estado '{venta.estado}'."
            )

        # Liberar unidades de inventario vinculadas a esta venta
        unidades_liberadas = UnidadProducto.objects.filter(
            venta=venta, estado='vendido'
        )
        count_liberadas = unidades_liberadas.count()
        unidades_liberadas.update(estado='disponible', venta=None)

        venta.cancelar_venta(motivo)

        logger.info(
            "Venta %s cancelada. Motivo: %s. Unidades liberadas: %d",
            venta.id, motivo, count_liberadas
        )
        return venta


class CompraService:
    """Operaciones de negocio relacionadas con compras de materiales."""

    @staticmethod
    @transaction.atomic
    def registrar_compra(proveedor, detalles: list) -> CompraMaterial:
        """
        Registra una compra de materiales y actualiza el stock en una sola transacción.

        Args:
            proveedor: instancia de Proveedor.
            detalles: lista de dicts con claves 'material' (Material) y
                      'cantidad' (int).

        Returns:
            Instancia de CompraMaterial creada.

        Raises:
            ValidationError: si no hay detalles o si alguna cantidad es <= 0.
        """
        if not detalles:
            raise ValidationError("La compra debe tener al menos un material.")

        total = Decimal('0')
        for detalle in detalles:
            if detalle.get('cantidad', 0) <= 0:
                raise ValidationError(
                    f"La cantidad para {detalle['material']} debe ser mayor a 0."
                )
            total += detalle['material'].precio * detalle['cantidad']

        compra = CompraMaterial.objects.create(
            proveedor=proveedor,
            total=total,
        )

        for detalle in detalles:
            DetalleCompraMaterial.objects.create(
                compra=compra,
                material=detalle['material'],
                cantidad=detalle['cantidad'],
            )
            # El signal post_save de DetalleCompraMaterial también actualiza
            # el stock, pero si se prefiere desactivar signals en el futuro,
            # este update() con F() es la forma segura de hacerlo aquí.

        logger.info(
            "Compra %s registrada para proveedor %s. Total: %s. Materiales: %d",
            compra.id, proveedor, total, len(detalles)
        )
        return compra
