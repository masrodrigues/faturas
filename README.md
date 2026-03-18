# Faturas

Aplicação Django para pesquisa de faturas. Agora é possível abastecer a base local tanto por arquivo texto quanto por uma conexão direta a um banco fonte (por exemplo, MySQL) usando variáveis de ambiente.

## Configuração do ambiente

1. **Python**: o projeto utiliza Python 3.12.
2. **Dependências**:

   ```pwsh
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Variáveis de ambiente opcionais para o banco Django** (caso queira usar MySQL diretamente em vez do SQLite padrão):

   | Variável | Descrição |
   | --- | --- |
   | `DB_ENGINE` | Engine Django, ex.: `django.db.backends.mysql`. O padrão é `django.db.backends.sqlite3`. |
   | `DB_NAME` | Nome do banco. Para SQLite pode ser um caminho relativo/absoluto para o arquivo. |
   | `DB_USER` | Usuário (obrigatório para bancos SQL quando `DB_ENGINE` não for SQLite). |
   | `DB_PASSWORD` | Senha do usuário. |
   | `DB_HOST` | Host (padrão `127.0.0.1`). |
   | `DB_PORT` | Porta (padrão `3306`). |
   | `DB_CHARSET` | Charset opcional para MySQL (padrão `utf8mb4`). |
   | `DB_SSL_CA` | Caminho para certificado CA se a conexão exigir TLS. |

   Exemplo de `.env` para MySQL:

   ```env
   DB_ENGINE=django.db.backends.mysql
   DB_NAME=api_invoice_mgr
   DB_USER=usuario
   DB_PASSWORD=segredo
   DB_HOST=10.73.136.33
   DB_PORT=3306
   DB_SSL_CA=/caminho/para/ca.pem
   ```

4. **Migrar o schema local** (caso continue usando o SQLite padrão ou queira manter uma base local para cache):

   ```pwsh
   python manage.py migrate
   ```

## Importação das faturas

### 1. Via arquivo texto (fluxo existente)

```pwsh
python manage.py import_faturas caminho/para/faturasClassificadas.txt --chunk 1000
```

### 2. Via banco de dados origem (novo)

Configure as variáveis de ambiente abaixo antes de executar o comando. Todas elas já estão ignoradas pelo `.gitignore`, então você pode guardá-las em um arquivo `.env` local.

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `FATURAS_SRC_DB_ENGINE` | Não (padrão `mysql`) | Tipo de banco fonte. Atualmente suportamos MySQL. |
| `FATURAS_SRC_DB_HOST` | Não | Host do banco (padrão `127.0.0.1`). |
| `FATURAS_SRC_DB_PORT` | Não | Porta do banco (padrão `3306`). |
| `FATURAS_SRC_DB_NAME` | Sim | Nome do banco fonte. |
| `FATURAS_SRC_DB_USER` | Sim | Usuário com permissão de leitura. |
| `FATURAS_SRC_DB_PASSWORD` | Sim | Senha do usuário. |
| `FATURAS_SRC_DB_CHARSET` | Não | Charset (padrão `utf8mb4`). |
| `FATURAS_SRC_DB_SSL_CA` | Não | Caminho para certificado CA se necessário. |
| `FATURAS_SRC_DB_AUTH_PLUGIN` | Não | Plugin de autenticação personalizado quando exigido. |
| `FATURAS_SRC_DB_TIMEOUT` | Não | Timeout de conexão em segundos. |
| `FATURAS_SRC_DB_QUERY` | **Sim** | `SELECT` que retorna as colunas do modelo `Fatura`. Use aliases para alinhar os nomes. |

Com as variáveis configuradas, execute:

```pwsh
python manage.py import_faturas --from-db --chunk 2000
```

A consulta definida em `FATURAS_SRC_DB_QUERY` precisa retornar as colunas abaixo (ou aliases com esses nomes). Os campos obrigatórios são marcados com `*`:

- `account_id`*
- `statement_id`*
- `status`*
- `cycle`*
- `cycle_closing_at`* (formato `YYYY-MM-DD` ou tipo DATE)
- `due_at`* (formato `YYYY-MM-DD` ou tipo DATE)
- `previous_balance`
- `debits`
- `credits`
- `current_balance`
- `amount_due`
- `amount_paid_until_due`
- `amount_paid_after_due`
- `other_credits_until_due`
- `other_credits_after_due`
- `evolve_to_delinquency`

Exemplo de query:

```sql
SELECT
    invoice.account_id AS account_id,
    invoice.statement_id AS statement_id,
    invoice.status AS status,
    invoice.cycle AS cycle,
    invoice.cycle_closing_at AS cycle_closing_at,
    invoice.due_at AS due_at,
    invoice.previous_balance AS previous_balance,
    invoice.debits AS debits,
    invoice.credits AS credits,
    invoice.current_balance AS current_balance,
    invoice.amount_due AS amount_due,
    invoice.amount_paid_until_due AS amount_paid_until_due,
    invoice.amount_paid_after_due AS amount_paid_after_due,
    invoice.other_credits_until_due AS other_credits_until_due,
    invoice.other_credits_after_due AS other_credits_after_due,
    invoice.evolve_to_delinquency AS evolve_to_delinquency
FROM api_invoice_mgr.invoice invoice;
```

O comando realiza *upsert* baseado em `statement_id`, garantindo que registros existentes sejam atualizados sem criar duplicatas. O chunk padrão é 1000 registros, podendo ser ajustado pelo parâmetro `--chunk`.

## Executando a aplicação

Após importar ou configurar a base, execute o servidor de desenvolvimento:

```pwsh
python manage.py runserver
```

A interface de pesquisa continuará funcionando normalmente, agora refletindo as informações atualizadas diretamente do banco.
