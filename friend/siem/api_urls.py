from django.urls import path
from . import views

urlpatterns = [
    path('ingest/', views.IngestViewSet.as_view({'post': 'create'}), name='ingest'),
    path('ingest/inventory/', views.InventoryIngestViewSet.as_view({'post': 'create'}),
          name='ingest_inventory'),
    path('ingest/login-history/', views.LoginHistoryIngestViewSet.as_view({'post': 'create'}),
          name='ingest_login_history'),
    path('ingest/host-info/', views.ExtendedHostInfoViewSet.as_view({'post': 'create'}),
          name='ingest_host_info'),
    path('hosts/', views.HostListView.as_view(), name='api-hosts'),
    path('events/', views.SecurityEventListView.as_view(), name='api-events'),
    path('dashboard/', views.SIEMDashboardView.as_view(), name='api-dashboard'),
]
