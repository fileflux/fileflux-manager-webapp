from db import get_db  

def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nodes (
        node_name VARCHAR(255) PRIMARY KEY,
        zpool_name VARCHAR(255),
        total_space BIGINT,
        available_space BIGINT,
        last_heartbeat TIMESTAMP DEFAULT current_timestamp
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS buckets (
        bucket_name VARCHAR(255) PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS objects (
        id SERIAL PRIMARY KEY,
        bucket VARCHAR(255),
        node_name VARCHAR(255),
        path VARCHAR(255),
        key VARCHAR(255),         
        size BIGINT,
        created_at TIMESTAMP DEFAULT current_timestamp,
        FOREIGN KEY (node_name) REFERENCES nodes(node_name),
        FOREIGN KEY (bucket) REFERENCES buckets(bucket_name) ON DELETE CASCADE
    );
    """)

    db.commit()
    cursor.close()
    db.close()
