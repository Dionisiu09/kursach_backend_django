from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Administrator'
    USER = 'user', 'User'


class Author(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    patronymic = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Genre(models.Model):
    genre_name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.genre_name


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        db_column='author_id'
    )
    genre = models.ForeignKey(
        Genre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='genre_id'
    )
    publication_date = models.DateField(null=True, blank=True)
    page_count = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    cover_image = models.ImageField(
        upload_to='book_covers/',
        null=True,
        blank=True,
        help_text='Завантажте зображення обкладинки книги'
    )

    def __str__(self):
        return self.title

    def get_total_quantity(self):
        supply = self.inventorymovement_set.filter(movement_type='supply').aggregate(total=models.Sum('quantity'))['total'] or 0
        discard = self.inventorymovement_set.filter(movement_type='discard').aggregate(total=models.Sum('quantity'))['total'] or 0
        return supply - discard

    def get_loaned_quantity(self):
        return self.bookloan_set.filter(return_date__isnull=True).aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_reserved_quantity(self):
        return self.bookreservation_set.filter(status='active').aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_available_quantity(self):
        return self.get_total_quantity() - self.get_loaned_quantity() - self.get_reserved_quantity()

    def is_available_for_reservation(self):
        return self.get_available_quantity() > 0

    def is_available_for_loan(self):
        return self.get_available_quantity() > 0


class InventoryMovement(models.Model):
    MOVEMENT_TYPES = (
        ('supply', 'Supply'),
        ('discard', 'Discard'),
    )

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        db_column='book_id'
    )
    movement_type = models.CharField(
        max_length=10,
        choices=MOVEMENT_TYPES
    )
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)]
    )
    movement_date = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.movement_type} - {self.book.title}"

    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.movement_type == 'discard':
            current_quantity = self.book.get_total_quantity()
            if current_quantity < self.quantity:
                raise ValidationError(
                    f"Недостаточно книг для списания. На складе: {current_quantity}, "
                    f"пытаетесь списать: {self.quantity}"
                )


class BookLoan(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id'
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        db_column='book_id'
    )
    loan_date = models.DateTimeField(auto_now_add=True)
    return_date = models.DateTimeField(null=True, blank=True)
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(return_date__gte=models.F('loan_date')) | models.Q(return_date__isnull=True),
                name='check_return_date'
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.book.title}"


class BookReservation(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id'
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        db_column='book_id'
    )
    reservation_date = models.DateTimeField(auto_now_add=True)
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)]
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )

    def __str__(self):
        return f"{self.user.username} - {self.book.title} reservation"


class ContactMessage(models.Model):
    DEPARTMENT_CHOICES = (
        ('general', 'Загальний відділ'),
        ('children', 'Дитячий відділ'),
        ('scientific', 'Науковий відділ'),
        ('media', 'Медіатека'),
        ('administration', 'Адміністрація'),
        ('support', 'Технічна підтримка'),
    )
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, null=True, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_messages'
    )
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.name} - {self.subject}"
