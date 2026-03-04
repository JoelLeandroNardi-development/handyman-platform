from __future__ import annotations

from shared.shared.mq import RabbitConfig, RabbitPublisher

cfg = RabbitConfig.from_env(required=False)
publisher = RabbitPublisher(cfg)

RABBIT_URL = cfg.url
EXCHANGE_NAME = cfg.exchange_name