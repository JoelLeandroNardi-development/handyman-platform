from shared.shared.mq import RabbitConfig, rabbit_connect

cfg = RabbitConfig.from_env(required=False)
RABBIT_URL = cfg.url
EXCHANGE_NAME = cfg.exchange_name

connect = lambda: rabbit_connect(cfg)
