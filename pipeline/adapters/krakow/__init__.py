"""Kraków adapters: same `<criterion>.<indicator>` columns as Praha, different sources."""
from .indicators import features  # noqa: F401
from .msip import addresses, districts  # noqa: F401
from .registers import extra_pois  # noqa: F401

# In Poland paediatric primary care is delivered by POZ (GP) clinics → count both
WALK_OVERRIDES = {"family.paediatrician_walk_min": ["paediatrician", "gp_clinic"]}


def fetch_extra() -> None:
    from . import gios
    gios.fetch()  # annual PM statistics, paced for the 2 req/min limit
