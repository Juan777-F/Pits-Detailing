from django.contrib import admin

from .models import Payment, WashJob


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('registered_by', 'created_at')


@admin.register(WashJob)
class WashJobAdmin(admin.ModelAdmin):
    list_display = ('plate', 'customer_name', 'service_name', 'total', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('plate', 'customer_name', 'vehicle_model')
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('job', 'amount', 'method', 'registered_by', 'created_at')
    list_filter = ('method', 'created_at')
    search_fields = ('job__plate', 'job__customer_name')
