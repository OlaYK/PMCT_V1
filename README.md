# PMCT (Polymarket Copy Trading) System

PMCT is an automated system designed to monitor and copy trades from top traders on Polymarket. It features a modular architecture, secure credential management, and a robust admin CLI for easy configuration.

## 🚀 Overview

The system operates by watching specified trader wallets for activity on the Polymarket Data API. Once a trade is detected, the system calculates a corresponding trade for the "follower" based on their custom settings (copy percentage, maximum trade amount) and executes it using the Polymarket CLOB (Central Limit Order Book) API.

## 🛠 Features

- **Automated Monitoring**: `watcher.py` continuously scans for new trades.
- **Precision Execution**: `executor.py` handles order signing (EIP-712) and submission.
- **Secure Credentials**: Private keys and API secrets are encrypted using Fernet (AES-128) before being stored in the database.
- **L2 Auth Derivation**: Automatic derivation of Polymarket L2 API keys (Key, Secret, Passphrase) from private keys.
- **Admin CLI**: A comprehensive tool to manage followers, follow relationships, and view P&L reports.
- **Slippage Protection**: Configurable slippage limits to prevent execution during high volatility.

## 🏗 Architecture

1.  **Watcher Service (`watcher.py`)**:
    - Queries monitored trader addresses.
    - Tracks trade history to avoid duplicates.
    - Saves new trades into the database.
2.  **Executor Service (`executor.py`)**:
    - Monitors the database for pending copy orders.
    - Calculates order size and checks slippage against the current market.
    - Signs orders using the follower's private key.
    - Submits authenticated orders to the CLOB API.
3.  **Polymarket Client (`polymarket_client.py`)**:
    - Wrapper for Gamma (Markets), Data (History), and CLOB (Trading) APIs.
    - Implements HMAC-SHA256 authentication for L1/L2 requests.
4.  **Admin Tool (`admin`)**:
    - CLI interface for system management.

## 📋 Prerequisites

- Python 3.9+
- A Polymarket account with an existing wallet.
- A PostgreSQL database (or SQLite for local testing).

## ⚙️ Setup & Installation

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Environment**:
    Create a `.env` file in the root directory:
    ```env
    DATABASE_URL=postgresql://user:password@localhost/pmct
    ENCRYPTION_KEY=your_32_byte_base64_key
    POLYGON_RPC=https://polygon-rpc.com
    WATCHER_POLL_INTERVAL=10
    EXECUTOR_POLL_INTERVAL=5
    ```

3.  **Initialize Database**:
    ```bash
    python -c "from models import init_db; init_db()"
    ```

## 🎮 Usage (Admin CLI)

### 1. Add a Follower
Add a user who wants to copy trades. Their private key will be encrypted immediately.
```bash
python admin add-follower --name "Alice" --email "alice@example.com" --private-key "0x..."
```

### 2. Authenticate Follower (L2 Derivation)
Derive the necessary L2 API keys required for trading.
```bash
python admin auth-follower --wallet "0xAliceWalletAddress"
```

### 3. Add a Follow Relationship
Link the follower to a trader they want to copy.
```bash
python admin add-follow --wallet "0xAliceWallet" --follow "0xTraderWallet" --copy-pct 10 --max-trade 50
```

### 4. System Status
```bash
python admin list-followers
python admin stats
```

## 🚦 Running the System

For the system to operate, both the Watcher and Executor must be running:

**Start the Watcher**:
```bash
python watcher.py
```

**Start the Executor**:
```bash
python executor.py
```

## 🔒 Security Note

The system handles sensitive private keys. 
- **Encryption**: All keys are encrypted at rest using a system-wide `ENCRYPTION_KEY`.
- **Isolation**: The private key is only decrypted in memory during the signing portion of the execution flow.
- **Environment**: Ensure your `.env` file is never committed to version control.

## 📊 Reporting

Generate a CSV P&L report for a specific follower:
```bash
python admin report --wallet "0xAliceWallet" --start 2024-01-01
```

---
*Disclaimer: This software is for educational purposes. Trading involves risk.*