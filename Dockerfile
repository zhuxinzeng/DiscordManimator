FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    ffmpeg \
    texlive \
    texlive-latex-extra \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# 先复制依赖文件，利用缓存
COPY pyproject.toml poetry.lock ./

# 导出 requirements 并安装依赖
RUN poetry export -f requirements.txt --without-hashes -o requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# 再复制源码
COPY . .

# 如果你的项目需要安装自身为包，取消注释
# RUN pip install --no-cache-dir .

EXPOSE 8000

# 按你的实际入口修改
CMD ["python", "main.py"]
