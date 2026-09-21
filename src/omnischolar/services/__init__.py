"""Host-neutral scholarly services."""

from .ai4scholar import Ai4ScholarService
from .application import ApplicationServices, OmniScholarApplication
from .chemistry import ChemistryService
from .materials import MaterialsProjectService
from .mineru import MinerUResult, MinerUService
from .sync import SyncPlan, SyncService
from .transport import CoreServiceTransport, ServiceTransport
from .zotero import ZoteroService, validate_zotero_key

__all__ = [
    "Ai4ScholarService",
    "ApplicationServices",
    "ChemistryService",
    "CoreServiceTransport",
    "MaterialsProjectService",
    "MinerUResult",
    "MinerUService",
    "OmniScholarApplication",
    "ServiceTransport",
    "SyncPlan",
    "SyncService",
    "ZoteroService",
    "validate_zotero_key",
]
