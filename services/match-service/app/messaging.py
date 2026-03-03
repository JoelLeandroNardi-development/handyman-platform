from __future__ import annotations

import os

from shared.shared.mq import RabbitConfig, rabbit_connect

cfg = RabbitConfig(url=os.getenv("RABBIT_URL"), exchange_name=os.getenv("EXCHANGE_NAME", "domain_events"))

RABBIT_URL = cfg.url
EXCHANGE_NAME = cfg.exchange_name

connect = lambda: rabbit_connect(cfg)  # noqa: E731