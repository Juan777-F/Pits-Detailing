from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


class WashJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        IN_PROGRESS = 'in_progress', 'En proceso'
        COMPLETED = 'completed', 'Terminado'
        CANCELLED = 'cancelled', 'Cancelado'

    plate = models.CharField('placa', max_length=10, db_index=True)
    vehicle_type = models.CharField('tipo de vehículo', max_length=40)
    vehicle_model = models.CharField('vehículo', max_length=100)
    customer_name = models.CharField('cliente', max_length=120)
    service_name = models.CharField('servicio', max_length=120)
    total = models.DecimalField(
        'total',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    status = models.CharField(
        'estado',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wash_jobs_created',
    )
    created_at = models.DateTimeField('fecha de ingreso', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('última actualización', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'servicio de lavado'
        verbose_name_plural = 'servicios de lavado'

    def __str__(self):
        return f'{self.plate} · {self.customer_name}'

    @property
    def paid_total(self):
        return self.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    @property
    def balance(self):
        return max(self.total - self.paid_total, Decimal('0.00'))


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = 'cash', 'Efectivo'
        TRANSFER = 'transfer', 'Transferencia'
        CARD = 'card', 'Tarjeta'

    job = models.ForeignKey(
        WashJob,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='servicio',
    )
    amount = models.DecimalField(
        'valor',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    method = models.CharField('método', max_length=20, choices=Method.choices)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wash_payments_registered',
    )
    created_at = models.DateTimeField('fecha de pago', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'pago'
        verbose_name_plural = 'pagos'

    def __str__(self):
        return f'{self.job.plate} · ${self.amount}'
