from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Payment, WashJob


class ApplicationWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.admin = user_model.objects.create_user(
            username='admin-test',
            password='SecureAdminPass!934',
            first_name='Admin',
            is_staff=True,
        )
        cls.employee = user_model.objects.create_user(
            username='employee-test',
            password='SecureEmployeePass!934',
            first_name='Empleado',
        )

    def login_as(self, user_type):
        user = self.admin if user_type == 'admin' else self.employee
        self.client.force_login(user)

    def test_public_home_and_role_login(self):
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pits Detailing')
        self.assertEqual(self.client.get(reverse('jornada')).status_code, 302)
        self.assertIn(reverse('login'), self.client.get(reverse('jornada')).url)

        response = self.client.post(reverse('login'), {
            'role': 'empleado',
            'username': self.employee.username,
            'password': 'SecureEmployeePass!934',
        })
        self.assertRedirects(response, reverse('employee_dashboard'))

    def test_login_animation_only_follows_successful_authentication(self):
        response = self.client.post(reverse('login'), {
            'role': 'admin',
            'username': self.admin.username,
            'password': 'IncorrectPassword!123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario o contraseña incorrectos.')
        self.assertNotContains(response, 'data-startup-overlay')

        response = self.client.post(reverse('login'), {
            'role': 'admin',
            'username': self.admin.username,
            'password': 'SecureAdminPass!934',
        })
        self.assertRedirects(
            response,
            reverse('admin_dashboard'),
            fetch_redirect_response=False,
        )

        dashboard = self.client.get(reverse('admin_dashboard'))
        self.assertContains(dashboard, 'data-startup-overlay')
        next_dashboard = self.client.get(reverse('admin_dashboard'))
        self.assertNotContains(next_dashboard, 'data-startup-overlay')

    def test_role_permissions_and_employee_creation(self):
        self.login_as('employee')
        response = self.client.get(reverse('estadisticas'))
        self.assertRedirects(response, reverse('employee_dashboard'))
        response = self.client.get(reverse('employees'))
        self.assertRedirects(response, reverse('employee_dashboard'))

        self.login_as('admin')
        response = self.client.post(reverse('employees'), {
            'first_name': 'Nuevo empleado',
            'username': 'nuevo-empleado',
            'password': 'ValidEmployeePassword!472',
        })
        self.assertRedirects(response, reverse('employees'))
        self.assertTrue(get_user_model().objects.filter(username='nuevo-empleado', is_staff=False).exists())
        employee = get_user_model().objects.get(username='nuevo-empleado')
        response = self.client.post(reverse('employee_toggle_active', args=[employee.id]))
        self.assertRedirects(response, reverse('employees'))
        employee.refresh_from_db()
        self.assertFalse(employee.is_active)
        self.assertFalse(self.client.login(username=employee.username, password='ValidEmployeePassword!472'))
        response = self.client.post(reverse('employee_toggle_active', args=[employee.id]))
        self.assertRedirects(response, reverse('employees'))
        employee.refresh_from_db()
        self.assertTrue(employee.is_active)

    def test_admin_pages_render_and_employee_panel_is_available(self):
        self.login_as('admin')
        dashboard = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(dashboard.content.count(b'data-open-modal'), 1)
        self.assertNotContains(dashboard, 'quick-add-btn')
        for route_name in (
            'admin_dashboard',
            'jornada',
            'pagos',
            'estadisticas',
            'perfil',
            'employees',
        ):
            with self.subTest(route=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)

        self.login_as('employee')
        self.assertEqual(self.client.get(reverse('employee_dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('jornada')).status_code, 200)
        self.assertEqual(self.client.get(reverse('pagos')).status_code, 200)

    def test_payments_screen_summarizes_and_filters_services(self):
        self.login_as('admin')
        pending_job = WashJob.objects.create(
            plate='PEN123',
            vehicle_type='Automóvil',
            vehicle_model='Vehículo pendiente',
            customer_name='Cliente pendiente',
            service_name='Lavado general',
            total='50000',
            created_by=self.admin,
        )
        paid_job = WashJob.objects.create(
            plate='PAG123',
            vehicle_type='Camioneta',
            vehicle_model='Vehículo pagado',
            customer_name='Cliente pagado',
            service_name='Lavado completo',
            total='75000',
            created_by=self.admin,
        )
        Payment.objects.create(
            job=paid_job,
            amount='75000',
            method=Payment.Method.TRANSFER,
            registered_by=self.admin,
        )

        pending_response = self.client.get(reverse('pagos'))
        self.assertContains(pending_response, '$ 50.000')
        self.assertContains(pending_response, 'Por cobrar')
        self.assertContains(pending_response, '1 servicio pendiente')
        self.assertRegex(
            pending_response.content.decode(),
            r'\d{1,2}:\d{2} [ap]\.m\.',
        )
        self.assertNotContains(pending_response, 'PAG123')

        paid_response = self.client.get(reverse('pagos'), {'estado': 'pagado'})
        self.assertContains(paid_response, 'PAG123')
        self.assertContains(paid_response, 'Transferencia')
        self.assertContains(paid_response, 'Pago recibido por')
        self.assertNotContains(paid_response, 'PEN123')

    def test_vehicle_status_and_payment_are_persisted(self):
        self.login_as('employee')
        response = self.client.post(reverse('job_create'), {
            'plate': 'abc-123',
            'vehicle_type': 'Automóvil',
            'vehicle_model': 'Mazda 3 gris',
            'customer_name': 'Cliente de prueba',
            'service_name': 'Lavado general',
            'total': '50.000',
        })
        self.assertRedirects(response, reverse('jornada'))
        job = WashJob.objects.get(plate='ABC123')
        self.assertEqual(job.created_by, self.employee)
        self.assertEqual(job.total, Decimal('50000'))

        response = self.client.post(reverse('job_status', args=[job.id]), {
            'status': WashJob.Status.IN_PROGRESS,
        })
        self.assertRedirects(response, reverse('jornada'))
        job.refresh_from_db()
        self.assertEqual(job.status, WashJob.Status.IN_PROGRESS)

        response = self.client.post(reverse('payment_create', args=[job.id]), {'method': 'cash'})
        self.assertRedirects(response, reverse('pagos'))
        job.refresh_from_db()
        payment = Payment.objects.get(job=job)
        self.assertEqual(payment.amount, job.total)
        self.assertEqual(payment.registered_by, self.employee)
        self.assertEqual(job.balance, 0)

    def test_payment_cannot_exceed_or_duplicate_a_paid_balance(self):
        self.login_as('admin')
        job = WashJob.objects.create(
            plate='XYZ123',
            vehicle_type='Automóvil',
            vehicle_model='Vehículo de prueba',
            customer_name='Cliente',
            service_name='Lavado',
            total='25000',
            created_by=self.admin,
        )
        self.client.post(reverse('payment_create', args=[job.id]), {'method': 'transfer'})
        self.client.post(reverse('payment_create', args=[job.id]), {'method': 'transfer'})
        self.assertEqual(Payment.objects.filter(job=job).count(), 1)

    def test_employee_cannot_toggle_employee_accounts(self):
        self.login_as('employee')
        response = self.client.post(reverse('employee_toggle_active', args=[self.admin.id]))
        self.assertRedirects(response, reverse('employee_dashboard'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class FirstAdminSetupTests(TestCase):
    def test_setup_creates_and_secures_the_first_admin_account(self):
        setup_url = reverse('initial_admin_setup')
        self.assertEqual(self.client.get(setup_url).status_code, 200)

        response = self.client.post(setup_url, {
            'first_name': 'Pits Admin',
            'username': 'piets-admin',
            'password': 'UniqueFirstAdminPassword!937',
        })
        self.assertRedirects(response, reverse('admin_dashboard'))
        admin = get_user_model().objects.get(username='piets-admin')
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(self.client.get(setup_url).url.startswith(reverse('login')))
