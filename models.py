from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

Base = declarative_base()

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  


class Follower(Base):
    """User who copies trades"""
    __tablename__ = 'followers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    wallet_address = Column(String, unique=True, nullable=False)
    encrypted_private_key = Column(String, nullable=False)
    encrypted_api_key = Column(String)
    encrypted_api_secret = Column(String)
    encrypted_api_passphrase = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    follows = relationship('Follow', back_populates='follower', cascade='all, delete-orphan')


class Follow(Base):
    """Copy trading relationship"""
    __tablename__ = 'follows'
    
    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey('followers.id', ondelete='CASCADE'))
    trader_address = Column(String, nullable=False, index=True)
    
    # Settings
    copy_percentage = Column(Float, default=10.0)
    max_trade_usd = Column(Float, default=100.0)
    max_slippage_pct = Column(Float, default=2.0)
    active = Column(Boolean, default=True)
    
    # Stats
    total_copies = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    follower = relationship('Follower', back_populates='follows')


class Trade(Base):
    """Detected trades from followed traders"""
    __tablename__ = 'trades'
    
    id = Column(String, primary_key=True)  # tx hash
    trader_address = Column(String, nullable=False, index=True)
    market_id = Column(String, nullable=False)
    market_question = Column(String, nullable=False)
    side = Column(String, nullable=False)  # BUY/SELL
    size = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CopyOrder(Base):
    """Copy trade execution records"""
    __tablename__ = 'copy_orders'
    
    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey('followers.id', ondelete='CASCADE'))
    original_trade_id = Column(String, ForeignKey('trades.id'))
    
    size = Column(Float, nullable=False)
    target_price = Column(Float, nullable=False)
    filled_price = Column(Float)
    slippage = Column(Float)
    
    status = Column(String, default='pending', index=True)  
    error_message = Column(Text)
    tx_hash = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    filled_at = Column(DateTime)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)
    print("✓ Database initialized")