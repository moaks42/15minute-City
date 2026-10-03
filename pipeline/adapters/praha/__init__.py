"""Praha adapters: same `<criterion>.<indicator>` columns as Kraków, different sources."""
from .admin import addresses, districts, neighborhoods  # noqa: F401
from .indicators import features  # noqa: F401
from .registers import extra_pois, parks  # noqa: F401
