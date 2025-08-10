import os
import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

def init_db():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=os.getenv('DB_PORT', '5432')
    )
    
    cursor = conn.cursor()
    
    # Crear tablas
    with open('schema.sql', 'r') as f:
        cursor.execute(f.read())
    
    # Crear usuario admin si no existe
    cursor.execute("SELECT * FROM usuarios WHERE usuario = 'admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
            ('admin', hashed_pw, 'admin')
        )
    
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Base de datos inicializada correctamente")