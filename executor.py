"""Executor Service - Executes copy trades"""
import time
from datetime import datetime, timedelta
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
from cryptography.fernet import Fernet
from models import get_db, Follower, Follow, Trade, CopyOrder
from polymarket_client import PolymarketClient
import config

print("⚡ Executor Service Starting...")

cipher = Fernet(config.ENCRYPTION_KEY.encode())

def decrypt_key(encrypted_key):
    """Decrypt private key"""
    return cipher.decrypt(encrypted_key.encode()).decode()

def calculate_copy_size(original_size, copy_percentage, max_trade_usd, original_price):
    """Calculate the position size to copy, capped by the user's max USD limit"""
    percentage_size = original_size * (copy_percentage / 100.0)
    usd_value = percentage_size * original_price
    
    # Cap size if it exceeds the maximum USD trade amount allowed
    if usd_value > max_trade_usd:
        percentage_size = max_trade_usd / original_price
    
    return round(percentage_size, 2)

def check_slippage(original_price, current_price, max_slippage_pct):
    """Check if slippage is acceptable"""
    slippage = abs(current_price - original_price) / original_price * 100
    return slippage <= max_slippage_pct, slippage


def create_order_hash(token_id, maker, side, size, price, nonce, expiration):
    """Create order hash for signing (simplified)"""
    from eth_abi import encode
    
    encoded = encode(
        ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'uint256'],
        [
            Web3.to_checksum_address(maker),
            int(token_id, 16) if token_id.startswith('0x') else int(token_id),
            int(size * 1e6),
            int(price * 1e6),
            nonce,
            expiration
        ]
    )
    
    return Web3.keccak(encoded).hex()

def execute_copy_trade(copy_order_id, client):
    """Execute a single copy trade"""
    db = get_db()
    try:
        copy_order = db.query(CopyOrder).filter(CopyOrder.id == copy_order_id).first()
        if not copy_order or copy_order.status != 'pending':
            return
        
        follower = db.query(Follower).filter(Follower.id == copy_order.follower_id).first()
        trade = db.query(Trade).filter(Trade.id == copy_order.original_trade_id).first()
        follow = db.query(Follow).filter(
            Follow.follower_id == follower.id,
            Follow.trader_address == trade.trader_address
        ).first()
        
        print(f"Executing copy for {follower.name}: {trade.side} {copy_order.size} @ {trade.market_question[:40]}...")
        
        current_price = client.get_best_price(trade.market_id, trade.side)
        if not current_price:
            copy_order.status = 'failed'
            copy_order.error_message = 'Could not get current price'
            db.commit()
            print(f"  ✗ Failed: No price available")
            return
        
        acceptable, slippage = check_slippage(copy_order.target_price, current_price, follow.max_slippage_pct)
        if not acceptable:
            copy_order.status = 'skipped'
            copy_order.slippage = slippage
            copy_order.error_message = f'Slippage {slippage:.2f}% exceeds max {follow.max_slippage_pct}%'
            db.commit()
            print(f"  ⊘ Skipped: Slippage too high ({slippage:.2f}%)")
            return
        
        private_key = decrypt_key(follower.encrypted_private_key)
        account = Account.from_key(private_key)
        
        # Load L2 API credentials for order placement
        if follower.encrypted_api_key:
            api_key = decrypt_key(follower.encrypted_api_key)
            api_secret = decrypt_key(follower.encrypted_api_secret)
            api_passphrase = decrypt_key(follower.encrypted_api_passphrase)
            client.set_auth(api_key, api_secret, api_passphrase)
        else:
            print(f"  ⚠ Warning: No API keys for {follower.name}. Order placement will likely fail.")
        
        # Generate order parameters
        nonce = int(time.time() * 1000)
        expiration = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        
        order_hash = create_order_hash(
            token_id=trade.market_id,
            maker=follower.wallet_address,
            side=trade.side,
            size=copy_order.size,
            price=current_price,
            nonce=nonce,
            expiration=expiration
        )
        
        message = encode_defunct(hexstr=order_hash)
        signed = account.sign_message(message)
        signature = signed.signature.hex()
        
        # Submit the order to the CLOB
        result = client.create_order(
            token_id=trade.market_id,
            price=current_price,
            size=copy_order.size,
            side=trade.side,
            signature=signature,
            signer=follower.wallet_address,
            nonce=nonce,
            expiration=expiration
        )
        
        if not result:
            copy_order.status = 'failed'
            copy_order.error_message = 'Order placement failed'
            db.commit()
            print(f"  ✗ Failed: Could not place order")
            return
        
        order_id = result.get('order_id')
        
        # Wait for the order to be matched on the book
        time.sleep(5)
        
        order_status = client.get_order(order_id)
        if order_status and order_status.get('status', '').lower() == 'filled':
            copy_order.status = 'filled'
            copy_order.filled_price = current_price
            copy_order.filled_at = datetime.utcnow()
            copy_order.slippage = slippage
            copy_order.tx_hash = order_status.get('transaction_hash')
            
            follow.total_copies += 1
            db.commit()
            print(f"  ✓ Filled at {current_price}")
        else:
            # Cleanup: Cancel the order if it didn't fill immediately
            client.cancel_order(order_id)
            copy_order.status = 'failed'
            copy_order.error_message = 'Order not filled'
            db.commit()
            print(f"  ✗ Not filled, cancelled")
        
    except Exception as e:
        print(f"  ✗ Execution error: {e}")
        copy_order.status = 'failed'
        copy_order.error_message = str(e)[:500]
        db.commit()
    finally:
        db.close()

def process_pending_trades():
    """Scan for new trader activity and queue copy orders for matching followers"""
    db = get_db()
    try:
        # Check trades from the last 10 minutes
        recent_trades = db.query(Trade).filter(
            Trade.created_at >= datetime.utcnow() - timedelta(minutes=10)
        ).all()
        
        for trade in recent_trades:
            follows = db.query(Follow, Follower).join(
                Follower, Follow.follower_id == Follower.id
            ).filter(
                Follow.trader_address == trade.trader_address,
                Follow.active == True
            ).all()
            
            for follow, follower in follows:
                # Avoid duplicate copying of the same trade
                existing = db.query(CopyOrder).filter(
                    CopyOrder.follower_id == follower.id,
                    CopyOrder.original_trade_id == trade.id
                ).first()
                
                if existing:
                    continue
                
                copy_size = calculate_copy_size(
                    trade.size,
                    follow.copy_percentage,
                    follow.max_trade_usd,
                    trade.price
                )
                
                if copy_size <= 0:
                    continue
                
                copy_order = CopyOrder(
                    follower_id=follower.id,
                    original_trade_id=trade.id,
                    size=copy_size,
                    target_price=trade.price,
                    status='pending'
                )
                
                db.add(copy_order)
                db.commit()
                print(f"→ New copy order created: {follower.name} copying {trade.trader_address[:8]}...")
        
    except Exception as e:
        print(f"Error processing trades: {e}")
        db.rollback()
    finally:
        db.close()

def execute_pending_orders(client):
    """Execute all pending copy orders"""
    db = get_db()
    try:
        pending = db.query(CopyOrder).filter(CopyOrder.status == 'pending').all()
        for order in pending:
            execute_copy_trade(order.id, client)
            time.sleep(1)
    except Exception as e:
        print(f"Error executing orders: {e}")
    finally:
        db.close()

def main():
    """Main executor loop"""
    client = PolymarketClient()
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking for trades to copy...")
            process_pending_trades()
            execute_pending_orders(client)
            time.sleep(config.EXECUTOR_POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\nExecutor stopped by user")
            break
        except Exception as e:
            print(f"Executor error: {e}")
            time.sleep(config.EXECUTOR_POLL_INTERVAL)

if __name__ == '__main__':
    main()