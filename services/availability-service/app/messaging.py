from __future__ import annotations

import os

from shared.shared.mq import RabbitConfig, RabbitPublisher

# Availability is allowed to run without RabbitMQ (dev mode).
cfg = RabbitConfig(url=os.getenv("RABBIT_URL"), exchange_name=os.getenv("EXCHANGE_NAME", "domain_events"))
publisher = RabbitPublisher(cfg)

RABBIT_URL = cfg.url
EXCHANGE_NAME = cfg.exchange_name