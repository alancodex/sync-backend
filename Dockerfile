# 1. Usando a versão exata do seu Python (Debian Bookworm)
FROM python:3.11-slim-bookworm

# 2. Define o diretório de trabalho dentro do container
WORKDIR /app

# 3. Instala dependências do sistema e o ODBC Driver 17 para SQL Server (Método Atualizado)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    apt-utils \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/config/debian/12/prod.list main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. Copia o requirements e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia todo o resto do conteúdo da pasta backend para o container
COPY . .

# 6. Expõe a porta padrão que o Render usa
EXPOSE 10000

# 7. Comando para rodar o app.py
CMD ["python", "app.py"]