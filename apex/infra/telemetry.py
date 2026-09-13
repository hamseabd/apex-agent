from aws_lambda_powertools import Logger, Metrics, Tracer

logger = Logger(service="apex")
tracer = Tracer(service="apex")
metrics = Metrics(namespace="Apex", service="apex")
