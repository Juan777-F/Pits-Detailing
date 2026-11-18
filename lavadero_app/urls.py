from django.urls import path

from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('configuracion-inicial/', views.initial_admin_setup_view, name='initial_admin_setup'),
    path('iniciar-sesion/', views.login_view, name='login'),
    path('cerrar-sesion/', views.logout_view, name='logout'),
    path('panel/', views.dashboard_redirect, name='home'),
    path('panel/administrador/', views.admin_dashboard_view, name='admin_dashboard'),
    path('panel/empleado/', views.employee_dashboard_view, name='employee_dashboard'),
    path('jornada/', views.jornada_view, name='jornada'),
    path('jornada/registrar/', views.job_create_view, name='job_create'),
    path('jornada/<int:job_id>/estado/', views.job_status_view, name='job_status'),
    path('pagos/', views.pagos_view, name='pagos'),
    path('pagos/<int:job_id>/registrar/', views.payment_create_view, name='payment_create'),
    path('estadisticas/', views.estadisticas_view, name='estadisticas'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('empleados/', views.employees_view, name='employees'),
]
