import sqlite3

db_path = 'bebcare.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE scheduled_tasks ADD COLUMN mode TEXT DEFAULT "auto"')
    print("Added mode column")
except sqlite3.OperationalError:
    print("mode column already exists")

try:
    cursor.execute('ALTER TABLE scheduled_tasks ADD COLUMN generate_image_count INTEGER DEFAULT 1')
    print("Added generate_image_count column")
except sqlite3.OperationalError:
    print("generate_image_count column already exists")

try:
    cursor.execute('ALTER TABLE scheduled_tasks ADD COLUMN generate_copy_count INTEGER DEFAULT 1')
    print("Added generate_copy_count column")
except sqlite3.OperationalError:
    print("generate_copy_count column already exists")

try:
    cursor.execute('''
        CREATE TABLE manual_task_drafts (
            draft_id TEXT PRIMARY KEY,
            task_id TEXT,
            product_id TEXT,
            images TEXT,
            copywritings TEXT,
            status TEXT DEFAULT "pending",
            selected_image TEXT,
            selected_copy TEXT,
            published_platforms TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES scheduled_tasks(task_id)
        )
    ''')
    print("Created manual_task_drafts table")
except sqlite3.OperationalError:
    print("manual_task_drafts table already exists")

conn.commit()
conn.close()
print("Migration completed successfully")
