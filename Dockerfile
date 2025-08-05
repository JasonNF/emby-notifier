# Dockerfile (已修改为使用清华镜像源)

# 使用一个轻量的 Python 官方镜像作为基础
FROM python:3.9-slim-buster

# 在容器内设置一个工作目录
WORKDIR /app

# 复制依-赖文件并安装
COPY requirements.txt .
# ↓↓↓ 这是唯一的修改之处：增加了 -i 参数来指定使用清华大学的镜像源 ↓↓↓
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制我们的应用程序代码
COPY app.py .

# 声明容器将对外暴露的端口
EXPOSE 8080

# 设置容器启动时要执行的命令
CMD ["python", "-u", "app.py"]