from django.contrib import admin
from django.urls import path
from faturas.views import faturas_pesquisa

urlpatterns = [
    path('admin/', admin.site.urls),
    path('faturas/', faturas_pesquisa, name='faturas_pesquisa'),
    path('', faturas_pesquisa),  # opcional: homepage já abre faturas
]
