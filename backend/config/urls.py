"""Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

admin.site.site_header = "聚焦好物管理后台"
admin.site.site_title = "聚焦好物后台"
admin.site.index_title = "店铺管理"

api_v1_patterns = [
    path("", include("apps.products.urls")),
    path("auth/", include("apps.authentication.urls")),
    path("profile/", include("apps.authentication.profile_urls")),
    path("", include("apps.cart_orders.urls")),
    path("contact/", include("apps.contact.urls")),
    path("after-sales/", include("apps.after_sales.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
