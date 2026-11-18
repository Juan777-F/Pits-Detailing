from decimal import Decimal

from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce

from .models import WashJob


def lavadero_context(request):
    if not request.user.is_authenticated:
        return {}
    pending_count = (
        WashJob.objects.exclude(status=WashJob.Status.CANCELLED)
        .annotate(
            amount_paid=Coalesce(
                Sum('payments__amount'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .filter(total__gt=F('amount_paid'))
        .count()
    )
    return {'pending_payment_count': pending_count}
