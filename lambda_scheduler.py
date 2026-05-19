from __future__ import annotations

from aws_lambda_powertools.utilities.typing import LambdaContext

from apex.infra.telemetry import logger, tracer, metrics


@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: dict, context: LambdaContext) -> None:
    job = event.get("job")
    if not job:
        logger.warning("Scheduler invoked with no job name")
        return

    from apex.scheduler.jobs import run
    run(job)
