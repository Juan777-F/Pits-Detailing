import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Payment, WashJob


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def role_required(admin_only=False):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            if admin_only and not is_admin(request.user):
                messages.error(request, 'Esta sección está disponible solo para administración.')
                return redirect('employee_dashboard')
            if not admin_only and is_admin(request.user):
                return view_func(request, *args, **kwargs)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def panel_url(user):
    return 'admin_dashboard' if is_admin(user) else 'employee_dashboard'


def money(value):
    return f'$ {value:,.0f}'.replace(',', '.')


def local_time(value):
    formatted = timezone.localtime(value).strftime('%I:%M %p').lower()
    return formatted.lstrip('0').replace('am', 'a.m.').replace('pm', 'p.m.')


def parse_cop_amount(value):
    value = value.strip().replace('$', '').replace(' ', '')
    grouped_value = re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?', value)
    plain_value = re.fullmatch(r'\d+(?:[,.]\d{1,2})?', value)
    if not grouped_value and not plain_value:
        raise InvalidOperation
    normalized = value.replace('.', '') if grouped_value else value
    return Decimal(normalized.replace(',', '.'))


def dashboard_context(request, employee=False):
    today = timezone.localdate()
    today_jobs = WashJob.objects.filter(created_at__date=today).exclude(
        status=WashJob.Status.CANCELLED
    )
    jobs = WashJob.objects.exclude(status=WashJob.Status.CANCELLED)
    income = Payment.objects.filter(created_at__date=today).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    outstanding = sum((job.balance for job in jobs), Decimal('0'))

    stats = [
        {'label': 'Vehículos hoy', 'value': today_jobs.count(), 'icon': 'car'},
        {'label': 'En proceso', 'value': today_jobs.filter(status=WashJob.Status.IN_PROGRESS).count(), 'icon': 'clock'},
        {'label': 'Terminados', 'value': today_jobs.filter(status=WashJob.Status.COMPLETED).count(), 'icon': 'check'},
        {'label': 'Pendientes', 'value': today_jobs.filter(status=WashJob.Status.PENDING).count(), 'icon': 'alert'},
    ]
    recent_jobs = jobs.select_related('created_by').prefetch_related('payments')[:6]
    vehicles = [{
        'plate': job.plate,
        'brand': job.vehicle_type,
        'vehicle_name': job.vehicle_model,
        'owner': job.customer_name,
        'service': job.service_name,
        'time': local_time(job.created_at),
        'status': job.get_status_display(),
        'status_kind': {
            WashJob.Status.PENDING: 'warning',
            WashJob.Status.IN_PROGRESS: 'info',
            WashJob.Status.COMPLETED: 'success',
        }.get(job.status, 'warning'),
        'paid': job.balance == 0,
        'amount': money(job.balance),
    } for job in recent_jobs]
    return {
        'stats': stats,
        'vehicles': vehicles,
        'page': 'home',
        'is_employee': employee,
        'income_today': money(income),
        'outstanding_total': money(outstanding),
        'job_count': jobs.count(),
    }


def landing_view(request):
    if request.user.is_authenticated:
        return redirect(panel_url(request.user))
    return render(request, 'lavadero_app/landing.html')


def initial_admin_setup_view(request):
    User = get_user_model()
    if User.objects.filter(is_staff=True).exists():
        return redirect('login')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        password = request.POST.get('password', '')
        if not username or not first_name or not password:
            messages.error(request, 'Completa tu nombre, usuario y contraseña.')
        elif User.objects.filter(is_staff=True).exists():
            messages.error(request, 'La primera cuenta de administrador ya fue configurada.')
            return redirect('login')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Ese nombre de usuario ya está en uso.')
        else:
            try:
                validate_password(password)
            except ValidationError as error:
                messages.error(request, ' '.join(error.messages))
            else:
                user = User.objects.create_superuser(
                    username=username,
                    password=password,
                    first_name=first_name,
                )
                login(request, user)
                messages.success(request, 'Cuenta de administrador configurada. Ya puedes comenzar.')
                return redirect('admin_dashboard')
    return render(request, 'lavadero_app/initial_setup.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect(panel_url(request.user))
    selected_role = request.GET.get('rol', request.POST.get('role', 'admin'))
    if selected_role not in ('admin', 'empleado'):
        selected_role = 'admin'
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, 'Usuario o contraseña incorrectos.')
        elif selected_role == 'admin' and not is_admin(user):
            messages.error(request, 'Esta cuenta no tiene acceso de administrador.')
        elif selected_role == 'empleado' and is_admin(user):
            messages.error(request, 'Selecciona Administrador para esta cuenta.')
        else:
            login(request, user)
            return redirect(panel_url(user))
    return render(request, 'lavadero_app/login.html', {
        'selected_role': selected_role,
        'setup_available': not get_user_model().objects.filter(is_staff=True).exists(),
    })


@login_required
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'Sesión cerrada correctamente.')
    return redirect('landing')


@login_required
def dashboard_redirect(request):
    return redirect(panel_url(request.user))


@role_required(admin_only=True)
def admin_dashboard_view(request):
    return render(request, 'lavadero_app/home.html', dashboard_context(request))


@role_required()
def employee_dashboard_view(request):
    if is_admin(request.user):
        return redirect('admin_dashboard')
    return render(
        request,
        'lavadero_app/home.html',
        dashboard_context(request, employee=True),
    )


@role_required()
def jornada_view(request):
    jobs = WashJob.objects.exclude(status=WashJob.Status.CANCELLED).prefetch_related('payments')
    return render(request, 'lavadero_app/jornada.html', {
        'jobs': jobs,
        'page': 'jornada',
        'status_choices': WashJob.Status.choices[:3],
    })


@role_required()
def job_create_view(request):
    if request.method != 'POST':
        return redirect('jornada')
    plate = request.POST.get('plate', '').strip().upper().replace(' ', '').replace('-', '')
    vehicle_type = request.POST.get('vehicle_type', '').strip()
    vehicle_model = request.POST.get('vehicle_model', '').strip()
    customer_name = request.POST.get('customer_name', '').strip()
    service_name = request.POST.get('service_name', '').strip()
    try:
        total = parse_cop_amount(request.POST.get('total', ''))
    except (InvalidOperation, TypeError):
        total = Decimal('0')
    if (
        not all((plate, vehicle_type, vehicle_model, customer_name, service_name))
        or not total.is_finite()
        or total <= 0
        or total.as_tuple().exponent < -2
        or total.adjusted() > 9
    ):
        messages.error(request, 'Completa todos los campos y registra un valor mayor que cero.')
        return redirect('jornada')
    if len(plate) > 10:
        messages.error(request, 'La placa no puede superar 10 caracteres.')
        return redirect('jornada')
    WashJob.objects.create(
        plate=plate,
        vehicle_type=vehicle_type,
        vehicle_model=vehicle_model,
        customer_name=customer_name,
        service_name=service_name,
        total=total,
        created_by=request.user,
    )
    messages.success(request, f'Servicio de {plate} registrado correctamente.')
    return redirect('jornada')


@role_required()
def job_status_view(request, job_id):
    if request.method == 'POST':
        job = get_object_or_404(WashJob, pk=job_id)
        new_status = request.POST.get('status')
        allowed_statuses = {choice[0] for choice in WashJob.Status.choices[:3]}
        if new_status not in allowed_statuses:
            messages.error(request, 'El estado seleccionado no es válido.')
        else:
            job.status = new_status
            job.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'Estado de {job.plate} actualizado.')
    return redirect('jornada')


@role_required()
def pagos_view(request):
    selected = request.GET.get('estado', 'pendiente')
    if selected not in ('pendiente', 'pagado'):
        selected = 'pendiente'
    jobs = WashJob.objects.exclude(status=WashJob.Status.CANCELLED).prefetch_related('payments')
    rows = []
    pending_count = 0
    paid_count = 0
    collected = Decimal('0')
    outstanding = Decimal('0')
    for job in jobs:
        paid = job.paid_total
        balance = job.balance
        latest_payment = job.payments.first()
        collected += paid
        outstanding += balance
        if balance:
            pending_count += 1
        else:
            paid_count += 1
        if (selected == 'pagado') != (balance == 0):
            continue
        rows.append({
            'job': job,
            'paid': money(paid),
            'balance': money(balance),
            'total': money(job.total),
            'is_paid': balance == 0,
            'payment_method': latest_payment.get_method_display() if latest_payment else '',
            'payment_date': latest_payment.created_at if latest_payment else None,
        })
    return render(request, 'lavadero_app/pagos.html', {
        'rows': rows,
        'outstanding_total': money(outstanding),
        'collected_total': money(collected),
        'pending_count': pending_count,
        'paid_count': paid_count,
        'selected_status': selected,
        'page': 'pagos',
    })


@role_required()
def payment_create_view(request, job_id):
    if request.method != 'POST':
        return redirect('pagos')
    with transaction.atomic():
        job = get_object_or_404(WashJob.objects.select_for_update(), pk=job_id)
        balance = job.balance
        method = request.POST.get('method')
        valid_methods = {choice[0] for choice in Payment.Method.choices}
        if balance <= 0:
            messages.info(request, 'Este servicio ya está pagado.')
        elif method not in valid_methods:
            messages.error(request, 'Selecciona un método de pago válido.')
        else:
            Payment.objects.create(
                job=job,
                amount=balance,
                method=method,
                registered_by=request.user,
            )
            messages.success(request, f'Pago de {money(balance)} registrado para {job.plate}.')
    return redirect('pagos')


@role_required(admin_only=True)
def estadisticas_view(request):
    today = timezone.localdate()
    start = today - timedelta(days=6)
    daily_payments = (
        Payment.objects.filter(created_at__date__gte=start, created_at__date__lte=today)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('amount'))
    )
    totals_by_day = {row['day']: row['total'] for row in daily_payments}
    bars = [
        {
            'label': (start + timedelta(days=index)).strftime('%a').capitalize(),
            'value': totals_by_day.get(start + timedelta(days=index), Decimal('0')),
        }
        for index in range(7)
    ]
    max_value = max((item['value'] for item in bars), default=Decimal('0'))
    for bar in bars:
        bar['height'] = int(bar['value'] / max_value * 100) if max_value else 0
        bar['amount'] = money(bar['value'])
    jobs = WashJob.objects.exclude(status=WashJob.Status.CANCELLED)
    today_jobs = jobs.filter(created_at__date=today)
    income = Payment.objects.filter(created_at__date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    outstanding = sum((job.balance for job in jobs), Decimal('0'))
    return render(request, 'lavadero_app/estadisticas.html', {
        'bars': bars,
        'income': money(income),
        'outstanding': money(outstanding),
        'vehicles_today': today_jobs.count(),
        'completed_today': today_jobs.filter(status=WashJob.Status.COMPLETED).count(),
        'billed_today': money(today_jobs.aggregate(total=Sum('total'))['total'] or Decimal('0')),
        'cancelled_today': WashJob.objects.filter(
            status=WashJob.Status.CANCELLED,
            created_at__date=today,
        ).count(),
        'page': 'estadisticas',
    })


@role_required()
def perfil_view(request):
    return render(request, 'lavadero_app/perfil.html', {
        'page': 'perfil',
        'is_admin': is_admin(request.user),
    })


@role_required(admin_only=True)
def employees_view(request):
    User = get_user_model()
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        password = request.POST.get('password', '')
        if not username or not first_name or not password:
            messages.error(request, 'Completa el nombre, usuario y contraseña.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Ese nombre de usuario ya existe.')
        else:
            try:
                validate_password(password)
            except ValidationError as error:
                messages.error(request, ' '.join(error.messages))
            else:
                User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    password=password,
                    is_staff=False,
                )
                messages.success(request, f'Cuenta de empleado "{username}" creada.')
                return redirect('employees')
    return render(request, 'lavadero_app/empleados.html', {
        'employees': User.objects.filter(is_staff=False, is_superuser=False).order_by('first_name'),
        'page': 'empleados',
    })


@role_required(admin_only=True)
def employee_toggle_active_view(request, user_id):
    if request.method != 'POST':
        return redirect('employees')
    User = get_user_model()
    employee = get_object_or_404(
        User,
        pk=user_id,
        is_staff=False,
        is_superuser=False,
    )
    employee.is_active = not employee.is_active
    employee.save(update_fields=['is_active'])
    status = 'activada' if employee.is_active else 'desactivada'
    messages.success(request, f'Cuenta de {employee.username} {status}.')
    return redirect('employees')
