# 1. Usando a imagem oficial do Python baseada em Ubuntu 22.04 LTS (Jammy)
FROM ubuntu:22.04

# Evita perguntas interativas durante a instalação de pacotes
ENV DEBIAN_FRONTEND=noninteractive

# 2. Instala o Python 3.11, pip e dependências de compilação
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    curl \
    gnupg2 \
    unixodbc-dev \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Configura o python3.11 como o padrão
RUN ln -s /usr/bin/python3.11 /usr/local/bin/python

# 3. Instala o ODBC Driver 17 para SQL Server usando o repositório do Ubuntu 22.04
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. Define o diretório de trabalho
WORKDIR /app

# 5. Copia o requirements e instala as dependências do Python
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

# 6. Copia todo o resto do conteúdo da pasta backend
COPY . .

# 7. Expõe a porta padrão do Render
EXPOSE 10000

# 8. Comando para rodar o seu app usando o Python 3.11
CMD ["python3.11", "app.py"]