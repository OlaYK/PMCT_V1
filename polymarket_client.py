import httpx
import config


class PolymarketClient:
    """Simple Polymarket API client"""
    
    def __init__(self):
        self.clob_url = config.CLOB_API_URL
        self.gamma_url = config.GAMMA_API_URL
        self.data_url = config.DATA_API_URL
        self.ws_url = config.WS_URL
        self.client = httpx.Client(timeout=30)
        self.api_creds = None
    
    def set_auth(self, api_key, api_secret, api_passphrase):
        """Set L2 API credentials for authenticated requests"""
        self.api_creds = {
            'key': api_key,
            'secret': api_secret,
            'passphrase': api_passphrase
        }
    
    def _get_auth_headers(self, method, request_path, body=""):
        """Generate Polymarket L2 authentication headers using HMAC-SHA256 signature"""
        # Signature requires: timestamp + method + path + body
        if not self.api_creds:
            return {}
            
        import time
        import hmac
        import hashlib
        import base64
        
        timestamp = str(int(time.time()))
        message = timestamp + method.upper() + request_path + body
        
        signature = hmac.new(
            base64.b64decode(self.api_creds['secret']),
            message.encode(),
            hashlib.sha256
        ).digest()
        
        sig_b64 = base64.b64encode(signature).decode()
        
        return {
            'POLY-API-KEY': self.api_creds['key'],
            'POLY-API-SECRET': self.api_creds['secret'],
            'POLY-API-PASSPHRASE': self.api_creds['passphrase'],
            'POLY-API-TIMESTAMP': timestamp,
            'POLY-API-SIGNATURE': sig_b64
        }
    
    def get_trades(self, user_address, after_timestamp=None):
        """Get recent trades for a user address using the Data API"""
        try:
            params = {'user': user_address}
            if after_timestamp:
                params['after'] = int(after_timestamp)
            
            response = self.client.get(f"{self.data_url}/trades", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching trades: {e}")
            return []
    
    def get_market(self, market_id):
        """Get market details"""
        try:
            response = self.client.get(f"{self.gamma_url}/markets/{market_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching market: {e}")
            return None
    
    def get_order_book(self, token_id):
        """Get order book for a market"""
        try:
            response = self.client.get(f"{self.clob_url}/book", params={'token_id': token_id})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching order book: {e}")
            return None
    
    def get_midpoint(self, token_id):
        """Get midpoint price for a market"""
        try:
            response = self.client.get(f"{self.clob_url}/midpoint", params={'token_id': token_id})
            response.raise_for_status()
            data = response.json()
            return float(data.get('mid')) if data.get('mid') else None
        except Exception as e:
            print(f"Error fetching midpoint: {e}")
            return None
    
    def get_best_price(self, token_id, side):
        """Get best available price using midpoint as fallback"""
        mid = self.get_midpoint(token_id)
        if mid:
            return mid
            
        book = self.get_order_book(token_id)
        if not book:
            return None
        
        try:
            if side == 'BUY':
                asks = book.get('asks', [])
                if asks:
                    return float(asks[0]['price'])
            else:
                bids = book.get('bids', [])
                if bids:
                    return float(bids[0]['price'])
        except (KeyError, IndexError, ValueError):
            pass
        
        return None
    
    def create_order(self, token_id, price, size, side, signature, signer, nonce, expiration):
        """Place an order on the CLOB"""
        try:
            order_data = {
                'token_id': token_id,
                'price': str(price),
                'size': str(size),
                'side': side.upper(),
                'signature': signature,
                'signer': signer,
                'nonce': nonce,
                'expiration': expiration
            }
            
            response = self.client.post(f"{self.clob_url}/order", json=order_data)
            headers = self._get_auth_headers("POST", "/order", str(order_data).replace("'", '"'))
            
            response = self.client.post(f"{self.clob_url}/order", json=order_data, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error creating order: {e}")
            if hasattr(e, 'response'):
                print(f"Server response: {e.response.text}")
            return None
    
    def get_order(self, order_id):
        """Get order status with L2 auth"""
        try:
            path = f"/order/{order_id}"
            headers = self._get_auth_headers("GET", path)
            
            response = self.client.get(f"{self.clob_url}{path}", headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching order: {e}")
            return None
    
    def cancel_order(self, order_id):
        try:
            path = "/order"
            body = f'"{order_id}"' # orderId in body
            headers = self._get_auth_headers("DELETE", path, body)
            
            response = self.client.delete(f"{self.clob_url}{path}", params={'order_id': order_id}, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error cancelling order: {e}")
            return None