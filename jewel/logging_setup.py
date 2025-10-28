import logging
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="%H:%M:%S",
    handlers=[RichHandler(markup=True, rich_tracebacks=True)],
)

logger = logging.getLogger("jewel")