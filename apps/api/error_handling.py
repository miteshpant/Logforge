"""
Sanitized error responses (LF-020).

Raw exception text from the database layer reaches API clients through the
pervasive `raise HTTPException(500, detail=f"...: {str(e)}")` pattern. A single
failed query then discloses the database name, table names, the ClickHouse
version and internal error codes to any unprivileged caller -- reconnaissance
material and an automatic finding in a SOC 2 / pen-test report.

The rule:
* 4xx validation messages are actionable and safe -- keep them verbatim.
* 5xx bodies must be generic. The full exception (with traceback) is logged
  server-side under a correlation ID, and only that ID is returned so support
  can tie a user report to the log line.

Usage in a router:

    from error_handling import internal_error

    except Exception as e:
        raise internal_error(e, "Failed to get anomaly history",
                             customer_id=customer_id)

`internal_error` RETURNS the HTTPException (it does not raise), so the call
site keeps the explicit `raise` and static analysis can see the control flow.
"""

import uuid

import structlog
from fastapi import HTTPException

logger = structlog.get_logger()

GENERIC_ERROR_MESSAGE = "Internal server error"


def internal_error(exc: BaseException, log_message: str, **log_context) -> HTTPException:
    """
    Log the full exception server-side and build a sanitized 500.

    Args:
        exc: the exception that caused the failure. Logged with traceback,
             never echoed to the client.
        log_message: operator-facing description of what failed (safe to be
             specific here -- it goes to the server log only).
        **log_context: extra structured fields for the log line
             (customer_id, endpoint, ...).

    Returns:
        HTTPException(500) with a generic body and the correlation ID, also
        emitted as the X-Request-ID response header so support can correlate.
    """
    correlation_id = str(uuid.uuid4())
    logger.error(
        log_message,
        correlation_id=correlation_id,
        error=str(exc),
        exc_info=exc,
        **log_context,
    )
    return HTTPException(
        status_code=500,
        detail={
            "error": GENERIC_ERROR_MESSAGE,
            "correlation_id": correlation_id,
        },
        headers={"X-Request-ID": correlation_id},
    )
