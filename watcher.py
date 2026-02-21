"""Watcher Service - Monitors trader wallets and detects new trades"""
import time
from datetime import datetime, timedelta
from models import get_db, Follow, Trade
from polymarket_client import PolymarketClient
import config

print("🔍 Watcher Service Starting...")

def get_traders_to_monitor():
    """Get list of unique trader addresses being followed"""
    db = get_db()
    try:
        traders = db.query(Follow.trader_address).filter(
            Follow.active == True
        ).distinct().all()
        return [t[0] for t in traders]
    finally:
        db.close()

def check_trader_trades(trader_address, client):
    """Check for new trades from a trader and save to DB"""
    db = get_db()
    try:
        last_trade = db.query(Trade).filter(
            Trade.trader_address == trader_address
        ).order_by(Trade.timestamp.desc()).first()
        
        after_timestamp = None
        if last_trade:
            after_timestamp = last_trade.timestamp.timestamp()
        else:
            after_timestamp = (datetime.utcnow() - timedelta(hours=1)).timestamp()
        
        trades = client.get_trades(trader_address, after_timestamp)
        
        if not trades:
            return 0
        
        new_count = 0
        for trade_data in trades:
            trade_id = trade_data.get('id') or trade_data.get('transaction_hash') or trade_data.get('transactionHash')
            
            existing = db.query(Trade).filter(Trade.id == trade_id).first()
            if existing:
                continue
            
            market_id = trade_data.get('asset_id') or trade_data.get('market') or trade_data.get('asset')
            side = trade_data.get('side', '').upper()
            size = float(trade_data.get('size', 0))
            price = float(trade_data.get('price', 0))
            timestamp_val = trade_data.get('timestamp')
            
            # Convert various timestamp formats to datetime
            if isinstance(timestamp_val, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_val)
            elif isinstance(timestamp_val, str):
                timestamp = datetime.fromisoformat(timestamp_val.replace('Z', '+00:00'))
            else:
                timestamp = datetime.utcnow()
            
            market_question = trade_data.get('title') or "Unknown"
            
            trade = Trade(
                id=trade_id,
                trader_address=trader_address.lower(),
                market_id=market_id,
                market_question=market_question,
                side=side,
                size=size,
                price=price,
                timestamp=timestamp
            )
            db.add(trade)
            db.commit()
            
            trade_time_str = timestamp.strftime('%H:%M:%S')
            print(f"✓ New trade detected [{trade_time_str}]: {trader_address[:8]}... {side} {size}@{price} - {market_question[:50]}")
            new_count += 1
        
        return new_count
        
    except Exception as e:
        print(f"Error checking trader {trader_address[:8]}: {e}")
        db.rollback()
        return 0
    finally:
        db.close()

def main():
    """Main watcher loop"""
    client = PolymarketClient()
    
    while True:
        try:
            traders = get_traders_to_monitor()
            
            if not traders:
                print("No traders to monitor. Waiting...")
                time.sleep(60)
                continue
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Monitoring {len(traders)} traders...")
            
            total_new = 0
            for trader in traders:
                new_trades = check_trader_trades(trader, client)
                total_new += new_trades
            
            if total_new > 0:
                print(f"✓ Found {total_new} new trades")
            
            time.sleep(config.WATCHER_POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\nWatcher stopped by user")
            break
        except Exception as e:
            print(f"Watcher error: {e}")
            time.sleep(config.WATCHER_POLL_INTERVAL)

if __name__ == '__main__':
    main()