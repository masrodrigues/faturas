from django.urls import path
from . import views

urlpatterns = [
    path("", views.faturas_pesquisa, name="faturas_pesquisa"),
]
