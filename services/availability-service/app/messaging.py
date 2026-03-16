from shared.shared.mq import create_publisher

publisher, cfg = create_publisher(required=False)
RABBIT_URL = cfg.url
EXCHANGE_NAME = cfg.exchange_name
