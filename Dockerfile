# 使用 Python 3.11 官方镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量：防止生成 .pyc 文件，确保日志实时输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 更换 pip 源为阿里云（加速下载，可选）
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 安装系统依赖（Manim 渲染必需：ffmpeg + LaTeX 完整环境）
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

# 复制整个项目（注意：如果你有 .dockerignore，建议排除 __pycache__ 等）
COPY . .

# 直接通过 pip 安装项目本身及其所有依赖（pip 会自动解析 pyproject.toml）
# 这完全绕过了脆弱的 poetry export
RUN pip install --no-cache-dir .

# 暴露端口（根据 Manimator 实际监听端口调整，常见为 8000）
EXPOSE 8000

# 启动命令（根据项目实际入口文件调整，这里假设是 main.py）
CMD ["python", "main.py"]