from django.core.management.base import BaseCommand
import pandas as pd
from produtos.models import Produto

class Command(BaseCommand):
    help = 'Importa produtos de um arquivo Excel para o banco de dados'

    def add_arguments(self, parser):
        parser.add_argument('arquivo_excel', type=str, help='O caminho para o arquivo Excel')

    def handle(self, *args, **kwargs):
        caminho_do_arquivo = kwargs['arquivo_excel']
        data_frame = pd.read_excel(caminho_do_arquivo, dtype={'codigo_do_produto': str, 'descricao': str})
        
        modelos_para_criar = []
        for _, row in data_frame.iterrows():
            # Verifica se a linha contém dados vazios para 'codigo_do_produto' ou 'descricao'
            if pd.isna(row['codigo_do_produto']) or pd.isna(row['descricao']):
                print(f"Linha ignorada devido a dados faltantes: {row}")
                continue  # Este continue deve estar dentro do if

            # Cria o objeto Produto e adiciona à lista de modelos para criação
            produto = Produto(
                codigo_do_produto=row['codigo_do_produto'],
                descricao=row['descricao'],
                preco_liquido=row['preco_liquido'],
                venda=row['venda'],
                revenda=row['revenda'],
                atacado=row['atacado'],
                base_12=row['base_12'],
                ipi=row['ipi'],
                apoi01=row['apoi01'],
                apoio02=row['apoio02'],
                bruto=row['bruto'],
                preco_base=row['preco_base'],
            )
            modelos_para_criar.append(produto)
        
        # Tenta criar todos os produtos em massa e trata possíveis exceções
        try:
            Produto.objects.bulk_create(modelos_para_criar)
            self.stdout.write(self.style.SUCCESS(f'Importados {len(modelos_para_criar)} produtos com sucesso!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao importar produtos: {e}'))
