FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY apex/ ./apex/
COPY lambda_webhook.py .
COPY lambda_scheduler.py .
