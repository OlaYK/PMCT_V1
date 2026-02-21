import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
CLOB_API_URL = os.getenv('CLOB_API_URL', 'https://clob.polymarket.com')
GAMMA_API_URL = os.getenv('GAMMA_API_URL', 'https://gamma-api.polymarket.com')
DATA_API_URL = os.getenv('DATA_API_URL', 'https://data-api.polymarket.com')

WS_URL = os.getenv('WS_URL', 'wss://ws-subscriptions-clob.polymarket.com/ws')
POLYGON_RPC = os.getenv('POLYGON_RPC', 'https://polygon-rpc.com')
WATCHER_POLL_INTERVAL = int(os.getenv('WATCHER_POLL_INTERVAL', '10'))
EXECUTOR_POLL_INTERVAL = int(os.getenv('EXECUTOR_POLL_INTERVAL', '5'))