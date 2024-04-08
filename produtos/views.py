from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Produto
from django.db.models import Q

def pesquisa_produto(request):
    query = request.GET.get('q', '')
    query_words = query.split()
    search_query = Q()

    for word in query_words:
        search_query &= (Q(descricao__icontains=word) | Q(codigo_do_produto__icontains=word))
    
    produtos = Produto.objects.filter(search_query)
    
     # Contando o número de produtos encontrados
    quantidade_produtos = produtos.count()
    return render(request, 'produtos/pesquisa.html', {'produtos': produtos, 'query': query, 'quantidade_produtos': quantidade_produtos})

def produto_update(request):
    print("Função produto_update chamada")
    if request.method == 'POST':
        produto_id = request.POST.get('produto_id')
        codigo = request.POST.get('codigo')
        descricao = request.POST.get('descricao')
        venda = request.POST.get('venda', '').strip()
        revenda = request.POST.get('revenda', '').strip()
        atacado = request.POST.get('atacado', '').strip()

        if not produto_id:
            messages.error(request, 'ID do produto não fornecido.')
            return redirect('pesquisa_produto')
        
        produto = get_object_or_404(Produto, pk=produto_id)
        produto.codigo_do_produto = codigo
        produto.descricao = descricao

        # Verifica se os campos não estão vazios antes de tentar converter
        if venda:
            try:
                produto.venda = float(venda)
                print("Venda atualizada para:", venda)
            except ValueError:
                messages.error(request, 'Formato inválido para o campo de venda.')
        
        if revenda:
            try:
                produto.revenda = float(revenda)
            except ValueError:
                messages.error(request, 'Formato inválido para o campo de revenda.')

        if atacado:
            try:
                produto.atacado = float(atacado)
            except ValueError:
                messages.error(request, 'Formato inválido para o campo de atacado.')

        produto.save()
        messages.success(request, 'Produto atualizado com sucesso.')
        return redirect('pesquisa_produto')
