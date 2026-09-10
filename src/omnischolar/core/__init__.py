"""Host-neutral safety primitives."""

from .context import ToolExecutionContext
from .errors import OmniScholarError, normalize_error
from .filesystem import (
    Artifact,
    atomic_write,
    confined_input,
    confined_path,
    read_file_bounded,
    temporary_path,
    validate_zip,
)
from .limits import jsonable, truncate_output
from .network import BoundedHttpClient
from .redaction import redact, redact_text

__all__ = [
    "Artifact",
    "BoundedHttpClient",
    "OmniScholarError",
    "ToolExecutionContext",
    "atomic_write",
    "confined_input",
    "confined_path",
    "jsonable",
    "normalize_error",
    "read_file_bounded",
    "redact",
    "redact_text",
    "temporary_path",
    "truncate_output",
    "validate_zip",
]
