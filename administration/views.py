from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from .models import Book, Author, BookReservation, Genre, BookLoan, InventoryMovement, ContactMessage
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta, datetime
import json
import os
from django.conf import settings
from django.db import models
import tempfile
import subprocess
import gzip
import shutil
# afsdf

def about_us(request):
    return render(request, 'administration/html/about_us.html')


def contacts(request):
    """
    Форма контактів, зберігає повідомлення у базу даних
    і показує сторінку контактів
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        department = request.POST.get('department')
        message_text = request.POST.get('message')
        
        try:
            contact_message = ContactMessage(
                name=name,
                email=email,
                subject=subject,
                department=department,
                message=message_text
            )

            if request.user.is_authenticated:
                contact_message.user = request.user

            contact_message.save()
            
            messages.success(request, 'Ваше повідомлення успішно відправлено! Ми зв\'яжемося з вами найближчим часом.')
            return redirect('contacts')
        except Exception as e:
            messages.error(request, f'Помилка при відправленні повідомлення: {str(e)}')
    
    return render(request, 'administration/html/contacts.html')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def db_backups(request):
    """
    Керування копіями БД - тільки для адмінів!
    """
    if not request.user.is_superuser:
        messages.error(request, 'У вас немає прав для доступу до цієї сторінки.')
        return redirect('index')
    
    # Список резервних копій
    backup_files = []
    backup_folder = get_backup_folder()
    
    if os.path.exists(backup_folder):
        file_list = [f for f in os.listdir(backup_folder) if f.endswith('.psql') or f.endswith('.bin') or f.endswith('.gz')]
        for filename in sorted(file_list, key=lambda x: os.path.getmtime(os.path.join(backup_folder, x)), reverse=True):
            file_path = os.path.join(backup_folder, filename)
            size = os.path.getsize(file_path)
            timestamp = timezone.datetime.fromtimestamp(os.path.getmtime(file_path))
            backup_files.append({
                'name': filename,
                'path': file_path,
                'size': size,
                'timestamp': timestamp
            })

    if request.method == 'POST' and 'create_backup' in request.POST:
        try:
            filename = create_backup_file()
            messages.success(request, f'Резервна копія бази даних успішно створена: {filename}')
            return redirect('db_backups')
        except Exception as e:
            messages.error(request, f'Помилка при створенні резервної копії: {str(e)}')

    if request.method == 'POST' and 'restore_backup' in request.POST:
        try:
            backup_file = request.POST.get('backup_file')
            if not backup_file:
                messages.error(request, 'Помилка: файл для відновлення не вказано.')
                return redirect('db_backups')
            
            restore_from_backup(backup_file)
            messages.success(request, f'База даних успішно відновлена з резервної копії {backup_file}.')
            return redirect('index')
        except Exception as e:
            messages.error(request, f'Помилка при відновленні бази даних: {str(e)}')

    if request.method == 'POST' and 'delete_backup' in request.POST:
        filename = request.POST.get('filename')
        if filename:
            file_path = os.path.join(backup_folder, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    messages.success(request, f'Резервна копія "{filename}" успішно видалена.')
                except Exception as e:
                    messages.error(request, f'Помилка при видаленні резервної копії: {str(e)}')
            else:
                messages.error(request, f'Файл "{filename}" не знайдено.')
        return redirect('db_backups')
    
    context = {
        'backup_files': backup_files
    }
    
    return render(request, 'administration/html/db_backups.html', context)


def auth(request):
    """
    Реєстрація нових користувачів та автоматичний вхід 
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        username = request.POST.get('username')
        first_name = request.POST.get('firstName')
        last_name = request.POST.get('lastName')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirmPassword')

        if password != confirm_password:
            messages.error(request, 'Паролі не співпадають!')
            return redirect('auth')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Користувач з таким логіном вже існує!')
            return redirect('auth')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Користувач з такою поштою вже існує!')
            return redirect('auth')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_superuser=False,
            is_staff=False
        )
        
        auth_login(request, user)
        messages.success(request, 'Реєстрація успішна!')
        return redirect('index')

    return render(request, 'administration/html/auth.html')


def login_view(request):
    if request.method == 'POST':
        login_identifier = request.POST.get('login')
        password = request.POST.get('password')

        user = None
        if '@' in login_identifier:
            try:
                user = User.objects.get(email=login_identifier)
                user = authenticate(username=user.username, password=password)
            except User.DoesNotExist:
                pass
        else:
            user = authenticate(username=login_identifier, password=password)

        if user is not None:
            auth_login(request, user)
            messages.success(request, 'Вхід успішний!')
            return redirect('index')
        else:
            messages.error(request, 'Невірний логін або пароль!')
            return redirect('login')

    return render(request, 'administration/html/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Ви успішно вийшли з системи!')
    return redirect('index')


def index(request):
    return render(request, 'administration/index.html')


def login(request):
    return render(request, 'administration/html/login.html')


def catalog(request):
    """
    Каталог книг з фільтрами, сортуванням і пагінацією
    """
    sort_by = request.GET.get('sort', 'title')
    order = request.GET.get('order', 'asc')
    items_per_page = int(request.GET.get('items_per_page', 20))
    page_number = request.GET.get('page', 1)

    search_query = request.GET.get('search', '')
    author_id = request.GET.get('author')
    min_pages = request.GET.get('min_pages')
    max_pages = request.GET.get('max_pages')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    availability = request.GET.get('availability')
    reserved = request.GET.get('reserved')

    books = Book.objects.all()

    if search_query:
        books = books.filter(title__icontains=search_query)
    
    if author_id:
        books = books.filter(author_id=author_id)
    
    if min_pages:
        books = books.filter(page_count__gte=min_pages)
    
    if max_pages:
        books = books.filter(page_count__lte=max_pages)
    
    if start_date:
        books = books.filter(publication_date__gte=start_date)
    
    if end_date:
        books = books.filter(publication_date__lte=end_date)

    books = list(books)

    if availability == 'available':
        books = [book for book in books if book.get_available_quantity() > 0]
    elif availability == 'unavailable':
        books = [book for book in books if book.get_available_quantity() <= 0]

    if not request.user.is_staff and reserved:
        user_reserved_books = BookReservation.objects.filter(
            user=request.user,
            status='active'
        ).values_list('book_id', flat=True)
        
        if reserved == 'reserved':
            books = [book for book in books if book.id in user_reserved_books]
        elif reserved == 'not_reserved':
            books = [book for book in books if book.id not in user_reserved_books]

    if sort_by == 'available':
        books = sorted(books, key=lambda x: x.get_available_quantity(), reverse=(order == 'desc'))
    elif sort_by == 'author':
        books = sorted(books, key=lambda x: str(x.author), reverse=(order == 'desc'))
    elif sort_by == 'genre':
        books = sorted(books, key=lambda x: str(x.genre) if x.genre else '', reverse=(order == 'desc'))
    else:
        books = sorted(books, key=lambda x: getattr(x, sort_by) or '', reverse=(order == 'desc'))

    authors = Author.objects.all()

    user_reserved_books = []
    if request.user.is_authenticated and not request.user.is_staff:
        user_reserved_books = BookReservation.objects.filter(
            user=request.user,
            status='active'
        ).values_list('book_id', flat=True)

    paginator = Paginator(books, items_per_page)
    try:
        books = paginator.page(page_number)
    except PageNotAnInteger:
        books = paginator.page(1)
    except EmptyPage:
        books = paginator.page(paginator.num_pages)

    context = {
        'books': books,
        'authors': authors,
        'user_reserved_books': user_reserved_books,
        'sort_by': sort_by,
        'order': order,
        'items_per_page': items_per_page,
    }

    return render(request, 'administration/html/catalog.html', context)


@login_required
def reserve_book(request, book_id):
    if request.user.is_staff:
        messages.error(request, 'Персонал не може бронювати книги')
        return redirect('catalog')
    
    book = get_object_or_404(Book, id=book_id)
    
    existing_reservation = BookReservation.objects.filter(
        user=request.user,
        book=book,
        status='active'
    ).exists()
    
    if existing_reservation:
        messages.warning(request, 'Ви вже забронювали цю книгу')
    else:
        BookReservation.objects.create(
            user=request.user,
            book=book,
            quantity=1,
            status='active'
        )
        messages.success(request, 'Бронь успішно заброньовано')
    
    return redirect('catalog')


@login_required
def delete_book(request, book_id):
    if not request.user.is_staff:
        messages.error(request, 'У вас нема прав для видалення книг.')
        return redirect('catalog')
    
    book = get_object_or_404(Book, id=book_id)
    if request.method == 'POST':
        book.delete()
        messages.success(request, 'Книга успішно добавленна.')
        return redirect('catalog')
    
    return render(request, 'administration/html/confirm_delete.html', {'book': book})


@login_required
def edit_book(request, book_id):
    if not request.user.is_staff:
        messages.error(request, 'У вас нема прав для редагування книг.')
        return redirect('catalog')
    
    book = get_object_or_404(Book, id=book_id)
    authors = Author.objects.all()
    genres = Genre.objects.all()
    
    if request.method == 'POST':
        title = request.POST.get('title')
        author_id = request.POST.get('author')
        genre_id = request.POST.get('genre')
        publication_date = request.POST.get('publication_date')
        page_count = request.POST.get('page_count')
        cover_image = request.FILES.get('cover_image')
        remove_cover = request.POST.get('remove_cover_image') == 'on'
        
        try:
            author = Author.objects.get(id=author_id)
            genre = Genre.objects.get(id=genre_id)
            
            book.title = title
            book.author = author
            book.genre = genre
            book.publication_date = publication_date
            book.page_count = page_count
            
            if remove_cover and book.cover_image:
                old_image_path = book.cover_image.path if book.cover_image else None
                
                book.cover_image = None
                
                if old_image_path and os.path.isfile(old_image_path):
                    os.remove(old_image_path)
            
            if cover_image:
                book.cover_image = cover_image
            
            book.save()
            messages.success(request, 'Книга успешно обновлена.')
            return redirect('catalog')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении книги: {str(e)}')
    
    context = {
        'book': book,
        'authors': authors,
        'genres': genres,
    }
    return render(request, 'administration/html/edit_book.html', context)


@login_required
def cancel_reservation(request, book_id):
    if request.user.is_staff:
        messages.error(request, 'Персонал не может отменять бронирования')
        return redirect('catalog')
    
    book = get_object_or_404(Book, id=book_id)
    
    reservation = BookReservation.objects.filter(
        user=request.user,
        book=book,
        status='active'
    ).first()
    
    if reservation:
        reservation.status = 'inactive'
        reservation.save()
        messages.success(request, 'Бронювання успішно скасовано')
    else:
        messages.warning(request, 'Бронювання не знайдено')
    
    return redirect('catalog')


@login_required
def add_book(request):
    if not request.user.is_staff:
        messages.error(request, 'У вас немає прав для додавання книг.')
        return redirect('catalog')
    
    authors = Author.objects.all()
    genres = Genre.objects.all()
    
    if request.method == 'POST':
        title = request.POST.get('title')
        author_id = request.POST.get('author')
        genre_id = request.POST.get('genre')
        publication_date = request.POST.get('publication_date')
        page_count = request.POST.get('page_count')
        cover_image = request.FILES.get('cover_image')
        supply_quantity = request.POST.get('supply_quantity', 0)
        
        try:
            author = Author.objects.get(id=author_id)
            genre = Genre.objects.get(id=genre_id)
            
            book = Book.objects.create(
                title=title,
                author=author,
                genre=genre,
                publication_date=publication_date,
                page_count=page_count,
                cover_image=cover_image
            )
            
            # Створюємо запис про надходження книг
            if supply_quantity and int(supply_quantity) > 0:
                InventoryMovement.objects.create(
                    book=book,
                    movement_type='supply',
                    quantity=int(supply_quantity),
                    reason='Початкове додавання книги'
                )
            
            messages.success(request, 'Книга успішно додана.')
            return redirect('catalog')
        except Exception as e:
            messages.error(request, f'Помилка при додаванні книги: {str(e)}')
    
    context = {
        'authors': authors,
        'genres': genres,
    }
    return render(request, 'administration/html/add_book.html', context)


@login_required
def add_author(request):
    if not request.user.is_staff:
        messages.error(request, 'У вас немає прав для додавання авторів.')
        return redirect('add_book')
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        patronymic = request.POST.get('patronymic', '')
        
        try:
            Author.objects.create(
                first_name=first_name,
                last_name=last_name,
                patronymic=patronymic
            )
            messages.success(request, 'Автор успішно доданий.')
            return redirect('add_book')
        except Exception as e:
            messages.error(request, f'Помилка при додаванні автора: {str(e)}')
    
    return render(request, 'administration/html/add_author.html')


@login_required
def add_genre(request):
    if not request.user.is_staff:
        messages.error(request, 'У вас немає прав для додавання жанрів.')
        return redirect('add_book')
    
    if request.method == 'POST':
        genre_name = request.POST.get('genre_name')
        
        try:
            Genre.objects.create(genre_name=genre_name)
            messages.success(request, 'Жанр успішно доданий.')
            return redirect('add_book')
        except Exception as e:
            messages.error(request, f'Помилка при додаванні жанру: {str(e)}')
    
    return render(request, 'administration/html/add_genre.html')


@login_required
def reports(request):
    """Генерація звітів про стан бібліотеки"""
    if not request.user.is_staff:
        messages.error(request, 'У вас немає прав для перегляду звітів.')
        return redirect('index')
        
    period = request.GET.get('period', 'all')
    
    # Визначаємо період для звіту
    now = timezone.now()
    if period == 'today':
        start_date = now - timedelta(days=1)
    elif period == 'week':
        start_date = now - timedelta(weeks=1)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == 'year':
        start_date = now - timedelta(days=365)
    else:
        start_date = None

    books_data = Book.objects.all()
    authors_data = Author.objects.all()
    genres_data = Genre.objects.all()
    users_data = User.objects.all()
    reservations_data = BookReservation.objects.all()
    loans_data = BookLoan.objects.all()
    inventory_data = InventoryMovement.objects.all()

    if start_date:
        reservations_data = reservations_data.filter(reservation_date__gte=start_date)
        loans_data = loans_data.filter(loan_date__gte=start_date)
        inventory_data = inventory_data.filter(movement_date__gte=start_date)

    total_books = sum(book.get_total_quantity() for book in books_data)
    available_books = sum(book.get_available_quantity() for book in books_data)
    availability_percentage = (available_books / total_books * 100) if total_books > 0 else 0

    books_by_genre = list(books_data.values('genre__genre_name').annotate(count=Count('id')).values('genre__genre_name', 'count'))
    books_by_author = list(books_data.values('author__last_name').annotate(count=Count('id')).values('author__last_name', 'count'))
    
    reservations_by_date = [{
        'date': item['reservation_date__date'].strftime('%Y-%m-%d'),
        'count': item['count']
    } for item in reservations_data.filter(status='active').values('reservation_date__date').annotate(count=Count('id')).values('reservation_date__date', 'count')]
    
    loans_by_date = [{
        'date': item['loan_date__date'].strftime('%Y-%m-%d'),
        'count': item['count']
    } for item in loans_data.filter(return_date__isnull=True).values('loan_date__date').annotate(count=Count('id')).values('loan_date__date', 'count')]
    
    inventory_movements = [{
        'date': item['movement_date__date'].strftime('%Y-%m-%d'),
        'movement_type': item['movement_type'],
        'count': item['count']
    } for item in inventory_data.values('movement_date__date', 'movement_type').annotate(count=Sum('quantity')).values('movement_date__date', 'movement_type', 'count')]

    context = {
        'period': period,
        'books_count': books_data.count(),
        'authors_count': authors_data.count(),
        'genres_count': genres_data.count(),
        'users_count': users_data.count(),
        'reservations_count': reservations_data.filter(status='active').count(),
        'loans_count': loans_data.filter(return_date__isnull=True).count(),
        'total_books': total_books,
        'available_books': available_books,
        'availability_percentage': round(availability_percentage, 1),
        'books_by_genre': json.dumps(books_by_genre),
        'books_by_author': json.dumps(books_by_author),
        'reservations_by_date': json.dumps(reservations_by_date),
        'loans_by_date': json.dumps(loans_by_date),
        'inventory_movements': json.dumps(inventory_movements),
    }

    return render(request, 'administration/html/reports_graphs.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def user_inquiries_and_book_reservations(request):
    """видача та бронювання книг"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'toggle_read':
            message_id = request.POST.get('message_id')
            message = get_object_or_404(ContactMessage, id=message_id)
            message.is_read = not message.is_read
            message.save()
            status_text = "прочитане" if message.is_read else "непрочитане"
            messages.success(request, f"Повідомлення позначено як {status_text}.")
            
        elif action == 'issue_reserved_book':
            reservation_id = request.POST.get('reservation_id')
            reservation = get_object_or_404(BookReservation, id=reservation_id)
            
            if not reservation.book.is_available_for_loan():
                messages.error(request, "Книга недоступна для видачі.")
                return redirect('user_inquiries')
            
            loan = BookLoan(
                user=reservation.user,
                book=reservation.book,
                quantity=reservation.quantity,
                loan_date=timezone.now()
            )
            loan.save()
            
            reservation.status = 'inactive'
            reservation.save()
            
            messages.success(request, f"Книга '{reservation.book.title}' успішно видана {reservation.user.username}.")

        elif action == 'issue_book_directly':
            user_id = request.POST.get('user_id')
            book_id = request.POST.get('book_id')
            return_date_str = request.POST.get('return_date')
            
            user = get_object_or_404(User, id=user_id)
            book = get_object_or_404(Book, id=book_id)
            
            if not book.is_available_for_loan():
                messages.error(request, "Книга недоступна для видачі.")
                return redirect('user_inquiries')
            
            try:
                return_date = datetime.strptime(return_date_str, '%Y-%m-%d').date()
                return_date = timezone.make_aware(datetime.combine(return_date, datetime.min.time()))
            except ValueError:
                messages.error(request, "Невірний формат дати.")
                return redirect('user_inquiries')
            
            loan = BookLoan(
                user=user,
                book=book,
                quantity=1,
                loan_date=timezone.now(),
                return_date=None
            )
            loan.save()
            
            messages.success(request, f"Книга '{book.title}' успішно видана {user.username}.")

        elif action == 'mark_as_returned':
            loan_id = request.POST.get('loan_id')
            loan = get_object_or_404(BookLoan, id=loan_id)
            
            loan.return_date = timezone.now()
            loan.save()
            
            messages.success(request, f"Книга '{loan.book.title}' відмічена як повернена.")
    
    contact_messages = ContactMessage.objects.all().order_by('-created_at')
    active_reservations = BookReservation.objects.filter(status='active').order_by('-reservation_date')
    active_loans = BookLoan.objects.filter(return_date__isnull=True).order_by('-loan_date')
    users = User.objects.filter(is_active=True).order_by('username')
    books = Book.objects.all().order_by('title')
    
    loan_search = request.GET.get('loan_search', '')
    if loan_search:
        active_loans = active_loans.filter(
            models.Q(user__username__icontains=loan_search) | 
            models.Q(user__first_name__icontains=loan_search) | 
            models.Q(user__last_name__icontains=loan_search) | 
            models.Q(book__title__icontains=loan_search) |
            models.Q(book__author__first_name__icontains=loan_search) |
            models.Q(book__author__last_name__icontains=loan_search)
        )
    
    sort_param = request.GET.get('sort', '')
    if sort_param == 'date_old':
        active_loans = active_loans.order_by('loan_date')
    elif sort_param == 'user':
        active_loans = active_loans.order_by('user__username')
    elif sort_param == 'book':
        active_loans = active_loans.order_by('book__title')
    
    active_tab = 'inquiries'
    if 'tab' in request.GET:
        active_tab = request.GET.get('tab')
    elif loan_search or sort_param:
        active_tab = 'loans'
    
    context = {
        'contact_messages': contact_messages,
        'active_reservations': active_reservations,
        'active_loans': active_loans,
        'users': users,
        'books': books,
        'active_tab': active_tab,
        'loan_search': loan_search,
        'sort_param': sort_param,
    }
    
    return render(request, 'administration/html/user_inquiries_and_book_reservations.html', context)

"""
Знизу Допоміжні функції для роботи з бекапами
"""

def get_db_connection_params():
    db_settings = settings.DATABASES['default']
    return {
        'db_name': db_settings['NAME'],
        'db_user': db_settings['USER'],
        'db_password': db_settings['PASSWORD'],
        'db_host': db_settings['HOST'],
        'db_port': db_settings['PORT'],
    }


def get_db_connection_string():
    params = get_db_connection_params()
    return f"postgresql://{params['db_user']}:{params['db_password']}@{params['db_host']}:{params['db_port']}/{params['db_name']}"


def get_backup_folder():
    backup_folder = settings.DBBACKUP_STORAGE_OPTIONS['location']
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)
    return backup_folder


def create_backup_file(timestamp=None):
    """Створення файлу бекапу у форматі .psql.bin.gz"""
    if timestamp is None:
        timestamp = timezone.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    backup_folder = get_backup_folder()
    filename = f"backup_{timestamp}.psql.bin.gz"
    output_file = os.path.join(backup_folder, filename)
    
    # Тимчасовий файл для бінарного дампу
    temp_bin = os.path.join(backup_folder, f"temp_{timestamp}.bin")
    
    dump_command = [
        'pg_dump',
        '--dbname=' + get_db_connection_string(),
        '--format=custom',
        '--compress=9',
        '--blobs',
        '--encoding=UTF8',
        '--file=' + temp_bin
    ]
    
    try:
        # Створюємо бінарний дамп .bin
        result = subprocess.run(dump_command, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Помилка при створенні дампу: {result.stderr}")

        with open(temp_bin, 'rb') as f_in:
            with gzip.open(output_file, 'wb', compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return filename
    except Exception as e:
        raise e
    finally:
        if os.path.exists(temp_bin):
            os.remove(temp_bin)


def restore_from_backup(backup_file):
    backup_folder = get_backup_folder()
    backup_file_path = os.path.join(backup_folder, backup_file)
    
    if not os.path.exists(backup_file_path):
        raise Exception(f'Файл {backup_file} не знайдено.')
    
    is_gzipped = backup_file.endswith('.gz')
    temp_file = None
    
    try:
        if is_gzipped:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
            temp_file.close()
            
            # Розпаковуємо .gzip
            with gzip.open(backup_file_path, 'rb') as f_in:
                with open(temp_file.name, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            file_to_restore = temp_file.name
        else:
            file_to_restore = backup_file_path
        
        command = [
            'pg_restore',
            '--dbname=' + get_db_connection_string(),
            '--clean',
            '--if-exists',
            '--single-transaction',
            '--format=custom',
            file_to_restore
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0 and result.returncode != 1:  # pg_restore іноді повертає 1 при попередженнях
            raise Exception(f"Помилка при відновленні: {result.stderr}")
        
        return True
    finally:
        if temp_file and os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
