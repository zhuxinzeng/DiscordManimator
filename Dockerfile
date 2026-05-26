# 使用更常用的 Python 3.11 官方镜像作为基础
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，避免Python生成__pycache__文件，并确保输出不被缓存
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装 Manim 渲染所需的系统依赖
# 注意：这部分内容我们暂时保留了，以免遗漏关键的系统级工具。
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    texlive \
    texlive-latex-extra \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制我们在上一步生成的 requirements.txt 文件
COPY requirements.txt .

# （核心修改）使用阿里云镜像加速，安装所有依赖
# --no-cache-dir 防止 pip 缓存膨胀，-i 指定国内镜像源加速下载
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 最后，复制项目源代码
COPY . .

# 暴露端口（根据你的实际 Web 端口号调整）
EXPOSE 8000

# 启动命令（同样根据项目的实际入口文件来修改）
CMD ["python", "app.py"]