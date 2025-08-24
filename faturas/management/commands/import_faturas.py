from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import datetime
from faturas.models import Fatura
import re

BR_DECIMAL_RE = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$|^-?\d+,\d{2}$")

def parse_brl_decimal(value: str) -> Decimal:
    """
    Converte '1.373,20' ou '1373,20' para Decimal('1373.20').
    Aceita também '0,00' e valores negativos.
    """
    s = value.strip()
    if BR_DECIMAL_RE.match(s):
        s = s.replace(".", "").replace(",", ".")
    return Decimal(s)

def parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "y")

def parse_date(value: str):
    # Linhas do arquivo usam 'YYYY-MM-DD'
    # Ex.: dueAt: 2025-09-15 / cycleClosingAt: 2025-08-23
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()

KEY_MAP = {
    "accountId": ("account_id", str),
    "statementId": ("statement_id", str),
    "status": ("status", str),
    "cycle": ("cycle", int),
    "cycleClosingAt": ("cycle_closing_at", parse_date),
    "dueAt": ("due_at", parse_date),
    "previousBalance": ("previous_balance", parse_brl_decimal),
    "debits": ("debits", parse_brl_decimal),
    "credits": ("credits", parse_brl_decimal),
    "currentBalance": ("current_balance", parse_brl_decimal),
    "amountDue": ("amount_due", parse_brl_decimal),
    "amountPaidUntilDue": ("amount_paid_until_due", parse_brl_decimal),
    "amountPaidAfterDue": ("amount_paid_after_due", parse_brl_decimal),
    "otherCreditsUntilDue": ("other_credits_until_due", parse_brl_decimal),
    "otherCreditsAfterDue": ("other_credits_after_due", parse_brl_decimal),
    "evolveToDelinquency": ("evolve_to_delinquency", parse_bool),
}

class Command(BaseCommand):
    help = "Importa faturas de um arquivo .txt no formato 'chave: valor | chave: valor ...' (uma fatura por linha)."

    def add_arguments(self, parser):
        parser.add_argument("arquivo_txt", type=str, help="Caminho para o faturasClassificadas.txt")
        parser.add_argument("--chunk", type=int, default=1000, help="Tamanho do lote para bulk_create")

    def handle(self, *args, **kwargs):
        caminho = kwargs["arquivo_txt"]
        chunk_size = kwargs["chunk"]
        registros = []

        # Linhas válidas começam com 'accountId:'
        def linha_e_de_fatura(l):
            return l.strip().startswith("accountId:")

        with open(caminho, "r", encoding="utf-8") as f:
            for num, linha in enumerate(f, start=1):
                if not linha_e_de_fatura(linha):
                    # ignora linhas-resumo tipo "00 | debits: ..." que aparecem antes dos blocos de contas
                    continue

                # Divide em partes "chave: valor"
                partes = [p.strip() for p in linha.split("|")]
                dados = {}
                for p in partes:
                    if ":" not in p:
                        continue
                    k, v = p.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if k in KEY_MAP:
                        dest_field, caster = KEY_MAP[k]
                        try:
                            dados[dest_field] = caster(v)
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"[linha {num}] Falha ao converter '{k}: {v}' -> {e}"))

                # Checagem mínima
                obrigatorios = ("account_id","statement_id","status","cycle","cycle_closing_at","due_at")
                if not all(field in dados for field in obrigatorios):
                    self.stdout.write(self.style.WARNING(f"[linha {num}] Campos obrigatórios ausentes; pulando. Dados: {dados}"))
                    continue

                registros.append(Fatura(**dados))

                # Despeja em lotes para economizar memória
                if len(registros) >= chunk_size:
                    self._persist(registros)
                    registros.clear()

        # final
        if registros:
            self._persist(registros)

    @transaction.atomic
    def _persist(self, objetos):
        # evita duplicatas por statement_id (unique)
        Fatura.objects.bulk_create(objetos, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"Gravou {len(objetos)} fatura(s) (lote)."))
