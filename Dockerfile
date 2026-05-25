# 使用官方 Python 3.11 镜像作为基础
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (Manim 渲染需要 ffmpeg 和 LaTeX 环境)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    texlive \
    texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir manim

# 复制项目所有文件
COPY . .

# 声明运行时容器监听的端口
EXPOSE 8000

# 启动命令 (根据项目实际入口文件调整)
CMD ["python", "main.py"]