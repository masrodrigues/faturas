## Use a imagem oficial do Python como base
FROM python:3.12.0

# Defina o diretório de trabalho no contêiner
WORKDIR /app

# Copie o arquivo requirements.txt para o contêiner
COPY requirements.txt /tmp/requirements.txt

# Instale os pacotes necessários usando pip
RUN set -ex && \
    pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    rm -rf /root/.cache/

# Copie o resto dos arquivos do seu projeto para o contêiner
COPY . .

# Comando para executar a aplicação
CMD ["gunicorn", "your_project_name.wsgi:application", "--bind", "0.0.0.0:8080"]
