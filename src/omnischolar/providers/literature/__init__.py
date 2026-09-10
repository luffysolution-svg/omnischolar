"""First-party literature providers."""

from .models import Author, LiteratureRecord, ProviderStatus, SearchRequest, SearchResult
from .providers import (
    ArxivProvider,
    CrossrefProvider,
    EasyScholarProvider,
    OpenAlexProvider,
    PubMedProvider,
    RateGate,
    SemanticScholarProvider,
    UnpaywallProvider,
)
from .router import LiteratureRouter
from .transport import CoreLiteratureTransport, LiteratureTransport

__all__ = [
    "ArxivProvider",
    "Author",
    "CoreLiteratureTransport",
    "CrossrefProvider",
    "EasyScholarProvider",
    "LiteratureRecord",
    "LiteratureRouter",
    "LiteratureTransport",
    "OpenAlexProvider",
    "ProviderStatus",
    "PubMedProvider",
    "RateGate",
    "SearchRequest",
    "SearchResult",
    "SemanticScholarProvider",
    "UnpaywallProvider",
]
