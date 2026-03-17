from __future__ import annotations

import os


RABBIT_URL = os.getenv("RABBIT_URL", "")
EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "domain_events")
