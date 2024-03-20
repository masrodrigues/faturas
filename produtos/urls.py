from django.urls import path
from . import views

urlpatterns = [
    # Página de pesquisa de produtos
    path('pesquisa/', views.pesquisa_produto, name='pesquisa_produto'),
    
    # Rota de atualização de produto, utilizada pelo formulário de edição
    path('produto/update/', views.produto_update, name='produto_update'),
]
