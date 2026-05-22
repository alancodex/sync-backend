# 1. Usando a imagem oficial do Python baseada em Ubuntu (focal)
# Isso resolve 100% dos problemas de compatibilidade de repositório do Debian
FROM python:3.11-slim-buster

# 2. Define o diretório de trabalho
WORKDIR /app

# 3. Instala o driver ODBC 17 usando o repositório oficial de forma direta
RUN apt-get update && apt-get install -y unixodbc-dev g++ curl gnupg2 apt-transport-https \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. Copia o requirements e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia todo o resto do conteúdo da pasta backend para o container
COPY . .

# 6. Expõe a porta padrão do Render
EXPOSE 10000

# 7. Comando para rodar o seu app
CMD ["python", "app.py"]