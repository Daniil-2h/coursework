from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

class Customer(models.Model):
    name = models.CharField(max_length=200, verbose_name='Имя')
    email = models.EmailField(unique=True, blank=True, null=True, verbose_name='Email')
    phone = models.CharField(max_length=15, blank=True, null=True, verbose_name='Телефон')
    address = models.TextField(blank=True, null=True, verbose_name='Адрес')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    stock = models.PositiveIntegerField(default=0, verbose_name='Остаток')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    def __str__(self):
        return self.name


class Invoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='Клиент')
    invoice_number = models.CharField(max_length=20, unique=True, verbose_name='Номер счёта')
    date = models.DateTimeField(default=timezone.now, verbose_name='Дата')
    due_date = models.DateTimeField(blank=True, null=True, verbose_name='Дата погашения')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Промежуточный итог')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='Ставка налога')  # например, 18.00 для 18%
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Сумма налога')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Сумма скидки')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Итоговая сумма')
    paid = models.BooleanField(default=False, verbose_name='Оплачено')

    def __str__(self):
        return f"Счёт №{self.invoice_number}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items', verbose_name='Счёт')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name='Товар')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена за единицу')
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Итого')
    def clean(self):
        """Проверяем, что количество не превышает доступный остаток с учётом редактирования."""
        orig_qty = 0
        if self.pk:
            try:
                orig_item = InvoiceItem.objects.get(pk=self.pk)
                if orig_item.product == self.product:
                    orig_qty = orig_item.quantity
            except InvoiceItem.DoesNotExist:
                pass
        
        if self.product and self.quantity > (self.product.stock + orig_qty):
            raise ValidationError(
                f"Недостаточно товара «{self.product.name}». "
                f"Доступно: {self.product.stock + orig_qty}, запрошено: {self.quantity}"
            )

    def save(self, *args, **kwargs):
        self.clean()
        
        # Рассчитываем общую стоимость
        self.total = self.quantity * self.unit_price

        orig_qty = 0
        orig_product = None
        if self.pk:
            try:
                orig_item = InvoiceItem.objects.get(pk=self.pk)
                orig_qty = orig_item.quantity
                orig_product = orig_item.product
            except InvoiceItem.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Обновляем остатки на складе
        if self.product:
            if orig_product == self.product:
                qty_diff = self.quantity - orig_qty
                if qty_diff != 0:
                    self.product.stock -= qty_diff
                    self.product.save()
            else:
                if orig_product:
                    orig_product.stock += orig_qty
                    orig_product.save()
                self.product.stock -= self.quantity
                self.product.save()
        elif orig_product:
            orig_product.stock += orig_qty
            orig_product.save()

    def delete(self, *args, **kwargs):
        # Восстанавливаем остаток при удалении позиции
        if self.product:
            self.product.stock += self.quantity
            self.product.save()
        super().delete(*args, **kwargs)

    def __str__(self):
        prod_name = self.product.name if self.product else "Удалённый товар"
        return f"{prod_name} x {self.quantity}"


class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, verbose_name='Счёт')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Оплаченная сумма')
    payment_date = models.DateTimeField(default=timezone.now, verbose_name='Дата оплаты')
    payment_method = models.CharField(max_length=50, choices=[
        ('cash', 'Наличные'),
        ('card', 'Карта'),
        ('upi', 'UPI'),
        ('bank', 'Банковский перевод')
    ], verbose_name='Способ оплаты')
    transaction_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='ID транзакции')

    def __str__(self):
        return f"Платёж по счёту №{self.invoice.invoice_number}"