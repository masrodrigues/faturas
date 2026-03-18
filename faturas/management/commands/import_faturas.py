import os
import re
from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import NotSupportedError

from faturas.models import Fatura

BR_DECIMAL_RE = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$|^-?\d+,\d{2}$")

REQUIRED_FIELDS = (
    "account_id",
    "statement_id",
    "status",
    "cycle",
    "cycle_closing_at",
    "due_at",
)

DECIMAL_FIELDS = (
    "previous_balance",
    "debits",
    "credits",
    "current_balance",
    "amount_due",
    "amount_paid_until_due",
    "amount_paid_after_due",
    "other_credits_until_due",
    "other_credits_after_due",
)

BOOL_FIELDS = ("evolve_to_delinquency",)

UPSERT_FIELDS = [
    "account_id",
    "status",
    "cycle",
    "cycle_closing_at",
    "due_at",
    "previous_balance",
    "debits",
    "credits",
    "current_balance",
    "amount_due",
    "amount_paid_until_due",
    "amount_paid_after_due",
    "other_credits_until_due",
    "other_credits_after_due",
    "evolve_to_delinquency",
]

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
    help = (
        "Importa faturas de um arquivo .txt no formato 'chave: valor | chave: valor ...'"
        " (uma fatura por linha) ou diretamente de um banco de dados origem."
    )

    def __init__(self):
        super().__init__()
        self._decimal_limits = None

    def add_arguments(self, parser):
        parser.add_argument(
            "arquivo_txt",
            nargs="?",
            type=str,
            help="Caminho para o faturasClassificadas.txt (obrigatório sem --from-db)",
        )
        parser.add_argument("--chunk", type=int, default=1000, help="Tamanho do lote para gravação")
        parser.add_argument(
            "--from-db",
            action="store_true",
            help="Busca os dados a partir do banco origem configurado via variáveis de ambiente",
        )

    def handle(self, *args, **kwargs):
        chunk_size = kwargs["chunk"]
        if kwargs["from_db"]:
            self.stdout.write(self.style.NOTICE("Iniciando importação direta do banco origem..."))
            self._import_from_db(chunk_size=chunk_size)
            return

        caminho = kwargs.get("arquivo_txt")
        if not caminho:
            raise CommandError("Informe o caminho do arquivo ou utilize --from-db para importar do banco de dados.")

        self.stdout.write(self.style.NOTICE(f"Lendo arquivo {caminho}..."))
        self._import_from_txt(caminho=caminho, chunk_size=chunk_size)

    def _import_from_txt(self, caminho: str, chunk_size: int) -> None:
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
                            self.stdout.write(
                                self.style.WARNING(f"[linha {num}] Falha ao converter '{k}: {v}' -> {e}")
                            )

                if not self._has_required_fields(dados):
                    self.stdout.write(
                        self.style.WARNING(f"[linha {num}] Campos obrigatórios ausentes; pulando. Dados: {dados}")
                    )
                    continue

                if not self._validate_decimal_limits(dados, context_label=f"linha {num}"):
                    continue

                registros.append(Fatura(**dados))

                # Despeja em lotes para economizar memória
                if len(registros) >= chunk_size:
                    self._persist(registros)
                    registros.clear()

        if registros:
            self._persist(registros)

    def _import_from_db(self, chunk_size: int) -> None:
        query = os.getenv("FATURAS_SRC_DB_QUERY")
        if not query:
            raise CommandError(
                "Defina FATURAS_SRC_DB_QUERY com o SELECT que retorna as colunas necessárias."
                " Utilize aliases para casar com os campos do modelo (ex.: SELECT account_id AS account_id, ...)."
            )

        db_config = self._build_db_config()
        driver = db_config.pop("driver")
        connect_kwargs = db_config.pop("connect_kwargs")

        self.stdout.write(
            self.style.NOTICE(
                "Conectando ao banco origem {user}@{host}:{port}/{database}...".format(**db_config)
            )
        )

        try:
            conn = driver.connect(**connect_kwargs)
        except Exception as exc:
            raise CommandError(f"Não foi possível conectar ao banco origem: {exc}") from exc

        cursor = None
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            total_processadas = 0

            while True:
                linhas = cursor.fetchmany(chunk_size)
                if not linhas:
                    break

                objetos = []
                for row in linhas:
                    dados = self._transform_db_row(row)
                    if not dados:
                        continue
                    objetos.append(Fatura(**dados))

                if objetos:
                    self._persist(objetos)
                    total_processadas += len(objetos)

            self.stdout.write(self.style.SUCCESS(f"Importação do banco concluída ({total_processadas} registros válidos)."))
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            conn.close()

    def _build_db_config(self):
        engine = (os.getenv("FATURAS_SRC_DB_ENGINE") or "mysql").lower()
        if engine != "mysql":
            raise CommandError("Apenas origem MySQL é suportada no momento (FATURAS_SRC_DB_ENGINE=mysql).")

        try:
            import mysql.connector as mysql_driver
        except ModuleNotFoundError as exc:
            raise CommandError(
                "Dependência 'mysql-connector-python' não encontrada. Execute 'pip install mysql-connector-python'."
            ) from exc

        database = os.getenv("FATURAS_SRC_DB_NAME")
        user = os.getenv("FATURAS_SRC_DB_USER")
        password = os.getenv("FATURAS_SRC_DB_PASSWORD")
        host = os.getenv("FATURAS_SRC_DB_HOST", "127.0.0.1")
        port = int(os.getenv("FATURAS_SRC_DB_PORT", "3306"))

        missing = [
            name
            for name, value in [
                ("FATURAS_SRC_DB_NAME", database),
                ("FATURAS_SRC_DB_USER", user),
                ("FATURAS_SRC_DB_PASSWORD", password),
            ]
            if not value
        ]
        if missing:
            raise CommandError(
                "Variáveis obrigatórias ausentes para conexão: " + ", ".join(missing)
            )

        connect_kwargs = {
            "database": database,
            "user": user,
            "password": password,
            "host": host,
            "port": port,
            "charset": os.getenv("FATURAS_SRC_DB_CHARSET", "utf8mb4"),
            "use_pure": True,
        }

        ssl_ca = os.getenv("FATURAS_SRC_DB_SSL_CA")
        if ssl_ca:
            connect_kwargs.setdefault("ssl_ca", ssl_ca)

        timeout = os.getenv("FATURAS_SRC_DB_TIMEOUT")
        if timeout:
            connect_kwargs.setdefault("connection_timeout", int(timeout))

        auth_plugin = os.getenv("FATURAS_SRC_DB_AUTH_PLUGIN")
        if auth_plugin:
            connect_kwargs.setdefault("auth_plugin", auth_plugin)

        return {
            "driver": mysql_driver,
            "host": host,
            "port": port,
            "user": user,
            "database": database,
            "connect_kwargs": connect_kwargs,
        }

    def _get_decimal_limits(self):
        if self._decimal_limits is None:
            limits = {}
            for field_name in DECIMAL_FIELDS:
                field = Fatura._meta.get_field(field_name)
                integer_digits = max((field.max_digits or 0) - (field.decimal_places or 0), 0)
                integer_part = "9" * integer_digits or "0"
                fractional_part = "9" * (field.decimal_places or 0)
                literal = f"{integer_part}.{fractional_part}" if fractional_part else integer_part
                limits[field_name] = Decimal(literal)
            self._decimal_limits = limits
        return self._decimal_limits

    def _validate_decimal_limits(self, dados: dict, context_label: str) -> bool:
        limits = self._get_decimal_limits()
        for field_name, max_value in limits.items():
            value = dados.get(field_name)
            if value is None:
                continue
            if abs(value) > max_value:
                statement = dados.get("statement_id")
                stmt_info = f" (statement_id={statement})" if statement else ""
                self.stdout.write(
                    self.style.WARNING(
                        f"[{context_label}{stmt_info}] Valor {value} excede o limite permitido para '{field_name}' ({max_value})."
                        " Registro ignorado."
                    )
                )
                return False
        return True

    def _transform_db_row(self, row: dict):
        dados = {}
        for field in REQUIRED_FIELDS + DECIMAL_FIELDS + BOOL_FIELDS:
            value = row.get(field)
            if value is None:
                continue

            try:
                if field in DECIMAL_FIELDS:
                    dados[field] = self._cast_decimal(value)
                elif field in BOOL_FIELDS:
                    dados[field] = self._cast_bool(value)
                elif field in ("cycle_closing_at", "due_at"):
                    dados[field] = self._cast_date(value)
                elif field == "cycle":
                    dados[field] = int(value)
                elif field == "status":
                    dados[field] = str(value).strip().upper()
                else:
                    dados[field] = str(value).strip()
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(f"Falha ao converter coluna '{field}' com valor '{value}': {exc}")
                )
                return None

        if not self._has_required_fields(dados):
            self.stdout.write(
                self.style.WARNING(f"Registro do banco com campos obrigatórios ausentes; ignorando. Dados: {dados}")
            )
            return None

        if not self._validate_decimal_limits(
            dados, context_label=f"registro banco statement_id={dados.get('statement_id')}"
        ):
            return None

        return dados

    def _has_required_fields(self, dados: dict) -> bool:
        return all(field in dados and dados[field] not in (None, "") for field in REQUIRED_FIELDS)

    def _cast_decimal(self, value):
        if isinstance(value, Decimal):
            return value
        if value in ("", None):
            return Decimal("0.00")
        return Decimal(str(value))

    def _cast_bool(self, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "sim"}

    def _cast_date(self, value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value in (None, ""):
            raise ValueError("Data obrigatória ausente")
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    @transaction.atomic
    def _persist(self, objetos):
        try:
            Fatura.objects.bulk_create(
                objetos,
                update_conflicts=True,
                unique_fields=["statement_id"],
                update_fields=UPSERT_FIELDS,
            )
        except NotSupportedError:
            # fallback para bases que não suportam upsert
            Fatura.objects.bulk_create(objetos, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f"Gravou {len(objetos)} fatura(s) (lote)."))
