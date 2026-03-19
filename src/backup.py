#!/usr/bin/env python3
"""
AXIS Backup Script
Создание и восстановление резервных копий базы данных
"""

import os
import sys
import subprocess
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "workday_db")
DB_HOST = os.getenv("DB_HOST", "localhost")
BACKUP_DIR = "backups"

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME
    )

def create_backup():
    """Создание резервной копии"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"axis_backup_{timestamp}.sql"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASS
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            subprocess.run(
                [
                    'pg_dump',
                    '-h', DB_HOST,
                    '-U', DB_USER,
                    '-d', DB_NAME,
                    '--clean',
                    '--create'
                ],
                env=env,
                stdout=f,
                check=True
            )
        
        size = os.path.getsize(filepath)
        print(f"✅ Backup created: {filename} ({size / 1024:.1f} KB)")
        return filepath
    
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None

def list_backups():
    """Список доступных бэкапов"""
    if not os.path.exists(BACKUP_DIR):
        return []
    
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith('.sql'):
            path = os.path.join(BACKUP_DIR, f)
            size = os.path.getsize(path)
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            backups.append({
                'name': f,
                'path': path,
                'size': size,
                'date': mtime
            })
    
    return sorted(backups, key=lambda x: x['date'], reverse=True)

def restore_backup(filepath):
    """Восстановление из бэкапа"""
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASS
    
    db_name_main = DB_NAME
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            subprocess.run(
                [
                    'psql',
                    '-h', DB_HOST,
                    '-U', DB_USER,
                    '-d', 'postgres',
                    '-f', filepath
                ],
                env=env,
                check=True
            )
        
        print(f"✅ Restore completed: {filepath}")
        return True
    
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False

def delete_old_backups(keep=10):
    """Удаление старых бэкапов (оставляет последние keep штук)"""
    backups = list_backups()
    
    if len(backups) <= keep:
        return 0
    
    deleted = 0
    for backup in backups[keep:]:
        try:
            os.remove(backup['path'])
            deleted += 1
            print(f"🗑️ Deleted: {backup['name']}")
        except Exception as e:
            print(f"❌ Failed to delete {backup['name']}: {e}")
    
    return deleted

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backup.py [create|list|restore|clean]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "create":
        create_backup()
    elif command == "list":
        for b in list_backups():
            print(f"{b['date'].strftime('%Y-%m-%d %H:%M')} - {b['name']} ({b['size']/1024:.1f} KB)")
    elif command == "restore":
        if len(sys.argv) < 3:
            print("Usage: python backup.py restore <filename>")
            sys.exit(1)
        restore_backup(sys.argv[2])
    elif command == "clean":
        deleted = delete_old_backups(5)
        print(f"Cleaned {deleted} old backups")
    else:
        print(f"Unknown command: {command}")
