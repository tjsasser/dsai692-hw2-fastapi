FROM python:3.13-slim
WORKDIR /app
COPY * ./
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["fastapi", "run", “extract_save_data.py”, "--port=8501"]