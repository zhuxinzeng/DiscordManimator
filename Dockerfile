# 使用官方 Python 3.11 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (ffmpeg, latex 等，与之前相同)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    texlive \
    texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY pyproject.toml poetry.lock ./

# 👇 1. 通过阿里云镜像安装 Poetry
RUN pip install --no-cache-dir poetry -i https://mirrors.aliyun.com/pypi/simple/

# 👇 2. 先导出依赖并用阿里云镜像通过 pip 安装，利用 Docker 缓存
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes \
    && pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制剩余的项目代码
COPY . .

# 👇 3. 最后安装项目本身
RUN poetry install --no-root

# 声明端口和启动命令（需要根据项目实际入口调整）
EXPOSE 8000
# CMD ["python", "main.py"]