from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about_us, name='about_us'),
    path('contacts/', views.contacts, name='contacts'),
    path('auth/', views.auth, name='auth'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('catalog/', views.catalog, name='catalog'),
    path('book/<int:book_id>/delete/', views.delete_book, name='delete_book'),
    path('book/<int:book_id>/edit/', views.edit_book, name='edit_book'),
    path('book/add/', views.add_book, name='add_book'),
    path('author/add/', views.add_author, name='add_author'),
    path('genre/add/', views.add_genre, name='add_genre'),
    path('reserve/<int:book_id>/', views.reserve_book, name='reserve_book'),
    path('cancel_reservation/<int:book_id>/', views.cancel_reservation, name='cancel_reservation'),
    path('reports/', views.reports, name='reports'),
    path('dbBackups/', views.db_backups, name='db_backups'),
    path('user_inquiries/', views.user_inquiries_and_book_reservations, name='user_inquiries'),
]