import sys
sys.path.insert(0, '.')

from models import init_db

if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    print("✓ Done")