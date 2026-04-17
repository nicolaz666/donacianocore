from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Proveedor, GrupoImagenes, Categoria, Material, CompraMaterial, DetalleCompraMaterial, Cliente, Producto, Ventas, Abono, DetalleVenta, Direccion, UnidadProducto

class GrupoImagenesSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrupoImagenes
        fields = ['id', 'producto', 'imagen', 'es_principal', 'descripcion']

class ProductoSerializer(serializers.ModelSerializer):
    categoria_id = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all(), source='categoria', write_only=True)
    categoria = serializers.SerializerMethodField()
    imagenes = GrupoImagenesSerializer(many=True, read_only=True)

    class Meta:
        model = Producto
        fields = [
            'id', 'tipo', 'modelo', 'precio',
            'colorPrincipal', 'colorTejido',
            'colorCordon1', 'colorCordon2',
            'colorSogaRienda', 'colorManzanos', 'colorCoronas',
            'observaciones', 'categoria_id', 'categoria', 'imagenes'
        ]

    def get_categoria(self, obj):
        return {"id": obj.categoria.id, "nombre": obj.categoria.nombre}
    
class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = '__all__'

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'

class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = '__all__'

class CompraMaterialSerializer(serializers.ModelSerializer):
    proveedor = ProveedorSerializer(read_only=True)

    class Meta:
        model = CompraMaterial
        fields = '__all__'

class DetalleCompraMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleCompraMaterial
        fields = '__all__'


class DireccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direccion
        fields = '__all__'
        # Asegúrate de que no se permita el campo 'cliente' desde el serializer
        extra_kwargs = {'cliente': {'required': False, 'allow_null': True}}

class ClienteSerializer(serializers.ModelSerializer):
    direcciones = DireccionSerializer(many=True, required=False)

    class Meta:
        model = Cliente
        fields = ['id', 'nombre', 'apellido', 'identificacion', 'direcciones', 'total_ventas']

    def create(self, validated_data):
        direcciones_data = validated_data.pop('direcciones', [])
        cliente = Cliente.objects.create(**validated_data)
        for direccion_data in direcciones_data:
            Direccion.objects.create(cliente=cliente, **direccion_data)
        return cliente

    def update(self, instance, validated_data):
        direcciones_data = validated_data.pop('direcciones', [])
        instance.nombre = validated_data.get('nombre', instance.nombre)
        instance.apellido = validated_data.get('apellido', instance.apellido)
        instance.identificacion = validated_data.get('identificacion', instance.identificacion)
        instance.save()

        # Actualizar o crear direcciones
        existing_direcciones = {direccion.id: direccion for direccion in instance.direcciones.all()}

        for direccion_data in direcciones_data:
            direccion_id = direccion_data.get('id', None)
            if direccion_id and direccion_id in existing_direcciones:
                # Actualizar dirección existente
                direccion = existing_direcciones[direccion_id]
                for key, value in direccion_data.items():
                    setattr(direccion, key, value)
                direccion.save()
            else:
                # Crear nueva dirección
                Direccion.objects.create(cliente=instance, **direccion_data)

        return instance


class UnidadProductoSerializer(serializers.ModelSerializer):
    # Campo para leer los detalles completos del producto
    producto_detalle = ProductoSerializer(source='producto', read_only=True)
    
    # Campo para escribir (crear/actualizar) solo con el ID del producto
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(),
        write_only=True
    )
    
    class Meta:
        model = UnidadProducto
        fields = ['id', 'numeroSerie', 'estado', 'fechaCreacion', 'producto', 'producto_detalle', 'venta']
        read_only_fields = ('numeroSerie', 'fechaCreacion')
    
    def to_representation(self, instance):
        """
        Sobrescribe la representación para que 'producto' contenga el objeto completo en GET
        """
        representation = super().to_representation(instance)
        # Mover producto_detalle a producto para mantener consistencia
        representation['producto'] = representation.pop('producto_detalle')
        return representation
    

class VentaSerializer(serializers.ModelSerializer):
    cliente = ClienteSerializer(read_only=True)
    cliente_id = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all(), write_only=True)
    abonos = serializers.StringRelatedField(many=True, read_only=True)
    detalles = serializers.StringRelatedField(many=True, read_only=True)
    debe = serializers.SerializerMethodField()
    
    # NUEVO: Campo para recibir productos
    productos = serializers.ListField(write_only=True, required=False)

    class Meta:
        model = Ventas
        fields = '__all__'

    def create(self, validated_data):
        cliente = validated_data.pop('cliente_id')
        productos_data = validated_data.pop('productos', [])  # Extraer productos
        
        # Crear la venta
        venta = Ventas.objects.create(cliente=cliente, **validated_data)
        
        # Crear los detalles de venta
        for producto_data in productos_data:
            DetalleVenta.objects.create(
                venta=venta,
                producto_id=producto_data.get('producto_id'),
                cantidad=producto_data.get('cantidad'),
                unidad_id=producto_data.get('unidad_id')  # Para unidades específicas
            )
        
        return venta

    def get_debe(self, obj):
        return obj.debe




class AbonoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Abono
        fields = '__all__'

class DetalleVentaSerializer(serializers.ModelSerializer):
    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(), 
        source='producto', 
        write_only=True
    )
    producto = ProductoSerializer(read_only=True)
    
    # NUEVO: Campo para unidad específica
    unidad_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadProducto.objects.all(),
        source='unidad',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = DetalleVenta
        fields = ['id', 'venta', 'producto_id', 'producto', 'cantidad', 'unidad_id']

# Serializers para autenticación y registro de usuarios


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'first_name', 'last_name']
    
    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        return data
    
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Credenciales inválidas')
            if not user.is_active:
                raise serializers.ValidationError('Usuario inactivo')
            data['user'] = user
        else:
            raise serializers.ValidationError('Debe incluir username y password')
        
        return data