#!/usr/bin/env python3
"""Simple database viewer for MegaBook"""
import sqlite3
import json
from pathlib import Path

def view_database():
    db_path = Path(".meta/embeddings.sqlite")
    
    if not db_path.exists():
        print("❌ Database not found at .meta/embeddings.sqlite")
        print("   The database is created when you first process notes.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("🗄️  MegaBook Database Viewer")
    print("=" * 60)
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print(f"\n📊 Found {len(tables)} tables:")
    for i, (table_name,) in enumerate(tables, 1):
        print(f"   {i}. {table_name}")
    
    # Show data from each table
    for table_name, in tables:
        print(f"\n{'='*60}")
        print(f"📋 Table: {table_name}")
        print('='*60)
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"   Total rows: {count}")
        
        if count > 0:
            # Show first 3 rows
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            
            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"\n   Columns: {', '.join(columns)}")
            print(f"\n   Sample data (first 3 rows):")
            
            for row in rows:
                print(f"   - {row}")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ Done!")

if __name__ == "__main__":
    view_database()
