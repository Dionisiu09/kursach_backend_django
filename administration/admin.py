from django.contrib import admin
from django.utils import timezone
from .models import Author, Genre, Book, InventoryMovement, BookLoan, BookReservation, ContactMessage

class AuthorAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'patronymic', 'get_books_count']
    search_fields = ['first_name', 'last_name', 'patronymic']
    list_filter = ['last_name']
    
    def get_books_count(self, obj):
        return obj.book_set.count()
    get_books_count.short_description = 'Кількість книг'

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'department', 'created_at', 'is_read')
    list_filter = ('is_read', 'department', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Відмітити як прочитані"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
    mark_as_unread.short_description = "Відмітити як непрочитані"

class GenreAdmin(admin.ModelAdmin):
    list_display = ['genre_name', 'get_books_count']
    search_fields = ['genre_name']
    
    def get_books_count(self, obj):
        return obj.book_set.count()
    get_books_count.short_description = 'Кількість книг'

class BookAdmin(admin.ModelAdmin):
    list_display = [
        'title', 
        'author', 
        'genre', 
        'publication_date', 
        'page_count',
        'get_total_quantity',
        'get_available_quantity',
        'get_loaned_quantity',
        'get_reserved_quantity'
    ]
    list_filter = ['genre', 'author', 'publication_date']
    search_fields = ['title', 'author__first_name', 'author__last_name', 'genre__genre_name']
    date_hierarchy = 'publication_date'
    
    def get_total_quantity(self, obj):
        return obj.get_total_quantity()
    get_total_quantity.short_description = 'Всього на складі'
    
    def get_available_quantity(self, obj):
        return obj.get_available_quantity()
    get_available_quantity.short_description = 'Доступно'
    
    def get_loaned_quantity(self, obj):
        return obj.get_loaned_quantity()
    get_loaned_quantity.short_description = 'Видано'
    
    def get_reserved_quantity(self, obj):
        return obj.get_reserved_quantity()
    get_reserved_quantity.short_description = 'Заброньовано'

class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ['book', 'movement_type', 'quantity', 'movement_date', 'reason']
    list_filter = ['movement_type', 'movement_date']
    search_fields = ['book__title', 'reason']
    date_hierarchy = 'movement_date'
    actions = ['mark_as_supply', 'mark_as_discard']
    
    def mark_as_supply(self, request, queryset):
        updated = queryset.update(movement_type='supply')
        self.message_user(request, f'{updated} записів позначено як постачання.')
    mark_as_supply.short_description = "Позначити як постачання"
    
    def mark_as_discard(self, request, queryset):
        updated = queryset.update(movement_type='discard')
        self.message_user(request, f'{updated} записів позначено як списання.')
    mark_as_discard.short_description = "Позначити як списання"

    def save_model(self, request, obj, form, change):
        obj.clean()
        super().save_model(request, obj, form, change)

class BookLoanAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'loan_date', 'return_date', 'quantity', 'get_loan_duration']
    list_filter = ['loan_date', 'return_date']
    search_fields = ['user__username', 'book__title']
    date_hierarchy = 'loan_date'
    actions = ['mark_as_returned']
    
    def get_loan_duration(self, obj):
        if obj.return_date:
            duration = obj.return_date - obj.loan_date
            return f"{duration.days} днів"
        return "В процесі"
    get_loan_duration.short_description = 'Тривалість позики'
    
    def mark_as_returned(self, request, queryset):
        updated = queryset.update(return_date=timezone.now())
        self.message_user(request, f'{updated} позик позначено як повернені.')
    mark_as_returned.short_description = "Позначити як повернені"

    def save_model(self, request, obj, form, change):
        if obj.return_date and obj.return_date < obj.loan_date:
            from django.core.exceptions import ValidationError
            raise ValidationError("Дата повернення не може бути раніше дати видачі")
        
        if not obj.book.is_available_for_loan():
            from django.core.exceptions import ValidationError
            raise ValidationError("Книга недоступна для видачі. Перевірте наявність на складі.")
        
        if obj.quantity > obj.book.get_available_quantity():
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Недостатньо книг на складі. Доступно: {obj.book.get_available_quantity()}")
        
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['return_date'].required = False
        return form

class BookReservationAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'reservation_date', 'quantity', 'status']
    list_filter = ['status', 'reservation_date']
    search_fields = ['user__username', 'book__title']
    date_hierarchy = 'reservation_date'
    actions = ['make_inactive', 'convert_to_loan', 'make_active']

    def make_inactive(self, request, queryset):
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} бронювань позначено як неактивні.')
    make_inactive.short_description = "Позначити як неактивні (скасувати бронювання)"

    def make_active(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} бронювань позначено як активні.')
    make_active.short_description = "Активувати бронювання"

    def convert_to_loan(self, request, queryset):
        loan_count = 0
        for reservation in queryset:
            if reservation.book.is_available_for_loan():
                BookLoan.objects.create(
                    user=reservation.user,
                    book=reservation.book,
                    quantity=reservation.quantity,
                    loan_date=timezone.now()
                )
                reservation.status = 'inactive'
                reservation.save()
                loan_count += 1
            else:
                self.message_user(request, f'Книга "{reservation.book.title}" недоступна для видачі.', level='ERROR')

        self.message_user(request, f'{loan_count} бронювань переведено у видачу книг.')
    convert_to_loan.short_description = "Видати книги за бронюванням"

    def save_model(self, request, obj, form, change):
        if not obj.book.is_available_for_reservation():
            from django.core.exceptions import ValidationError
            raise ValidationError("Книга недоступна для бронювання. Перевірте наявність на складі.")
        
        if obj.quantity > obj.book.get_available_quantity():
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Недостатньо книг на складі. Доступно: {obj.book.get_available_quantity()}")
        
        super().save_model(request, obj, form, change)

admin.site.register(Author, AuthorAdmin)
admin.site.register(Genre, GenreAdmin)
admin.site.register(Book, BookAdmin)
admin.site.register(InventoryMovement, InventoryMovementAdmin)
admin.site.register(BookLoan, BookLoanAdmin)
admin.site.register(BookReservation, BookReservationAdmin)
