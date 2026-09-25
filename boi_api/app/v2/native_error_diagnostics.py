"""Private operational failure locations without request values or exception text."""
import logging
from pathlib import Path
import traceback


def log_redacted_failure(error, operation):
    frames=[{'file':Path(frame.filename).name,'function':frame.name,'line':frame.lineno}
            for frame in traceback.extract_tb(error.__traceback__)[-8:]]
    # Do not stringify the exception: validation errors can contain source text,
    # tokens, prompts or arbitrary caller values. No locals/source lines logged.
    logging.getLogger(__name__).warning('native_operation_failure operation=%s type=%s frames=%s',
        operation,type(error).__name__,frames)
