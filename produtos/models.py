from django.db import models

# Create your models here.
class Produto(models.Model):
    codigo_do_produto = models.CharField(max_length=50)
    descricao = models.TextField()
    preco_liquido = models.DecimalField(max_digits=10, decimal_places=2)
    venda = models.DecimalField(max_digits=10, decimal_places=2)
    revenda = models.DecimalField(max_digits=10, decimal_places=2)
    atacado = models.DecimalField(max_digits=10, decimal_places=2)
    base_12 = models.DecimalField(max_digits=10, decimal_places=2)
    ipi = models.DecimalField(max_digits=10, decimal_places=2)
    apoi01 = models.DecimalField(max_digits=10, decimal_places=2)
    apoio02 = models.DecimalField(max_digits=10, decimal_places=2)
    bruto = models.DecimalField(max_digits=10, decimal_places=2)
    preco_base = models.DecimalField(max_digits=10, decimal_places=2)
   