FROM python:3.11-slim

WORKDIR /workspace/lab
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "trainer.py", "--data-dir", "/workspace/data/fixtures", "--report", "/workspace/run/latest_training_report.json"]
