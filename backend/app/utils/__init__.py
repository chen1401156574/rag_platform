# set global timezone
try:
    from time import tzset
    tzset()
except ImportError:
    pass

from .get_logger import get_logger
logger = get_logger()

from .response import success_result, error_result