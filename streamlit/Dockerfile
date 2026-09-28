FROM python:3.13-slim
WORKDIR /app
COPY * ./
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ['streamlit', 'run', 'hw3.py', '--port=8501']