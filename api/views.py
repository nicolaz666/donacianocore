from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from .models import Proveedor, Categoria, Material, CompraMaterial, DetalleCompraMaterial, Cliente, Producto, Ventas, Abono, DetalleVenta, Direccion, UnidadProducto, Color
from .serializers import ProveedorSerializer, GrupoImagenes, CategoriaSerializer, MaterialSerializer, CompraMaterialSerializer, DetalleCompraMaterialSerializer, ClienteSerializer, ProductoSerializer, VentaSerializer, AbonoSerializer, DetalleVentaSerializer, DireccionSerializer, UnidadProductoSerializer, ColorSerializer
from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from .serializers import UserSerializer, RegisterSerializer, LoginSerializer,GrupoImagenesSerializer

@api_view(['GET'])
@permission_classes([AllowAny])
def ping(request):
    return Response({"status": "ok"})


class GrupoImagenesViewSet(viewsets.ModelViewSet):
    queryset = GrupoImagenes.objects.all()
    serializer_class = GrupoImagenesSerializer

    # Filtrar imágenes por producto
    def get_queryset(self):
        queryset = GrupoImagenes.objects.all()
        producto_id = self.request.query_params.get('producto_id')
        if producto_id:
            queryset = queryset.filter(producto_id=producto_id)
        return queryset

    # Endpoint para marcar una imagen como principal
    @action(detail=True, methods=['patch'])
    def marcar_principal(self, request, pk=None):
        imagen = self.get_object()
        imagen.es_principal = True
        imagen.save()  # El método save() del modelo se encarga de desmarcar las demás
        serializer = self.get_serializer(imagen)
        return Response(serializer.data)

class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer

class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer

class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer

class CompraMaterialViewSet(viewsets.ModelViewSet):
    queryset = CompraMaterial.objects.all()
    serializer_class = CompraMaterialSerializer

class DetalleCompraMaterialViewSet(viewsets.ModelViewSet):
    queryset = DetalleCompraMaterial.objects.all()
    serializer_class = DetalleCompraMaterialSerializer

class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.prefetch_related('direcciones', 'ventas').all()
    serializer_class = ClienteSerializer

class DireccionViewSet(viewsets.ModelViewSet):
    queryset = Direccion.objects.all()
    serializer_class = DireccionSerializer


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.select_related('categoria').prefetch_related('imagenes').all()
    serializer_class = ProductoSerializer

class UnidadProductoViewSet(viewsets.ModelViewSet):
    queryset = UnidadProducto.objects.select_related('producto__categoria').all()
    serializer_class = UnidadProductoSerializer
    
    # Permitir actualizaciones parciales con PATCH
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    # O si prefieres un endpoint específico para cambiar estado
    @action(detail=True, methods=['patch'])
    def cambiar_estado(self, request, pk=None):
        unidad = self.get_object()
        nuevo_estado = request.data.get('estado')
        
        if nuevo_estado:
            unidad.estado = nuevo_estado
            unidad.save()
            serializer = self.get_serializer(unidad)
            return Response(serializer.data)
        
        return Response({'error': 'Estado no proporcionado'}, status=400)

class VentaViewSet(viewsets.ModelViewSet):
    queryset = Ventas.objects.select_related('cliente').prefetch_related('abonos', 'detalles').all()
    serializer_class = VentaSerializer

class AbonoViewSet(viewsets.ModelViewSet):
    queryset = Abono.objects.all()
    serializer_class = AbonoSerializer

class DetalleVentaViewSet(viewsets.ModelViewSet):
    queryset = DetalleVenta.objects.all()
    serializer_class = DetalleVentaSerializer
    

class ColorViewSet(viewsets.ModelViewSet):
    queryset = Color.objects.all().order_by('nombre')
    serializer_class = ColorSerializer
    http_method_names = ['get', 'post', 'head', 'options']


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Usuario registrado exitosamente'
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Login exitoso'
        }, status=status.HTTP_200_OK)

class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({
                'message': 'Logout exitoso'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)