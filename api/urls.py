from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterView,GrupoImagenesViewSet, LoginView, LogoutView, UserProfileView, ProveedorViewSet, CategoriaViewSet, MaterialViewSet, CompraMaterialViewSet, DetalleCompraMaterialViewSet, ClienteViewSet, ProductoViewSet, VentaViewSet, AbonoViewSet, DetalleVentaViewSet, DireccionViewSet, UnidadProductoViewSet



router = DefaultRouter()
router.register(r'proveedores', ProveedorViewSet)
router.register(r'categorias', CategoriaViewSet)
router.register(r'materiales', MaterialViewSet)
router.register(r'compras', CompraMaterialViewSet)
router.register(r'detalles-compras', DetalleCompraMaterialViewSet)
router.register(r'clientes', ClienteViewSet)
router.register(r'direcciones', DireccionViewSet)
router.register(r'productos', ProductoViewSet)
router.register(r'Unidadproductos', UnidadProductoViewSet)
router.register(r'ventas', VentaViewSet)
router.register(r'abonos', AbonoViewSet)
router.register(r'detalles-ventas', DetalleVentaViewSet)
router.register(r'grupo-imagenes', GrupoImagenesViewSet)

urlpatterns = [
    # Rutas de autenticación
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]