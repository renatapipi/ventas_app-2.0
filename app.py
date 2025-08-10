import os
from flask import Flask, flash, jsonify, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal
import psycopg2  # Cambiamos mysql.connector por psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
from flask import jsonify
# Cargar variables de entorno
load_dotenv()

# Configuración de la app Flask
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.getenv('SECRET_KEY')

# Función para conectar a PostgreSQL
def conectar():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=os.getenv('DB_PORT', '5432')
    )

# Decorador para verificar acceso de administrador
def requiere_admin(f):
    def decorador(*args, **kwargs):
        if 'usuario' not in session or session.get('rol') != 'admin':
            flash('Acceso no autorizado', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorador.__name__ = f.__name__
    return decorador

# --------------------------- AUTENTICACIÓN ---------------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    error = ''

    if request.method == 'POST':
        user = request.form.get('username')
        password = request.form.get('password')

        if not user or not password:
            error = 'Debe ingresar usuario y contraseña'
        else:
            conn = conectar()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT usuario, password, rol FROM usuarios WHERE usuario = %s",
                    (user,)
                )
                usuario_data = cursor.fetchone()
                
                if usuario_data:
                    usuario, hashed_password, rol = usuario_data
                    if check_password_hash(hashed_password, password):
                        session['usuario'] = usuario
                        session['rol'] = rol
                        return redirect(url_for('menu'))
                
                error = 'Usuario o contraseña incorrectos'
            except Exception as e:
                error = f'Error al autenticar: {str(e)}'
            finally:
                cursor.close()
                conn.close()

    return render_template('login.html', error=error)




@app.route('/menu')
def menu():
    if 'usuario' in session:
        return render_template('menu.html', usuario=session['usuario'], rol=session['rol'])
    else:
        return redirect(url_for('login'))


# --------------------------- USUARIOS ---------------------------

@app.route('/usuarios')
@requiere_admin
def listar_usuarios():
    conn = conectar()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, usuario, rol FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/crear', methods=['POST'])
@requiere_admin
def crear_usuario():
    usuario = request.form['usuario']
    password = generate_password_hash(request.form['password'])
    rol = request.form['rol']

    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
            (usuario, password, rol)
        )
        conn.commit()
        flash('Usuario creado exitosamente', 'success')
    except Exception as err:  # Cambiamos mysql.connector.Error por Exception genérico
        conn.rollback()
        flash(f'Error al crear usuario: {err}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('listar_usuarios'))

@app.route('/usuarios/editar/<int:id>', methods=['POST'])
@requiere_admin
def editar_usuario(id):
    usuario = request.form['usuario']
    rol = request.form['rol']
    password = request.form.get('password')

    conn = conectar()
    cursor = conn.cursor()
    try:
        if password:
            hashed_pw = generate_password_hash(password)
            cursor.execute(
                "UPDATE usuarios SET usuario = %s, rol = %s, password = %s WHERE id = %s",
                (usuario, rol, hashed_pw, id)
            )
        else:
            cursor.execute(
                "UPDATE usuarios SET usuario = %s, rol = %s WHERE id = %s",
                (usuario, rol, id)
            )
        conn.commit()
        flash('Usuario actualizado exitosamente', 'success')
    except psycopg2.Error as err:  # Cambio clave aquí
        conn.rollback()
        flash(f'Error al actualizar usuario: {err.pgerror}', 'error')
    except Exception as err:  # Para otros errores inesperados
        conn.rollback()
        flash(f'Error inesperado: {str(err)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('listar_usuarios'))

@app.route('/usuarios/eliminar/<int:id>')
@requiere_admin
def eliminar_usuario(id):
    try:
        with conectar() as conn:  # Usamos el context manager para la conexión
            with conn.cursor() as cursor:  # Context manager para el cursor
                # Verificamos si el usuario existe primero
                cursor.execute("SELECT 1 FROM usuarios WHERE id = %s", (id,))
                if not cursor.fetchone():
                    flash('El usuario no existe', 'error')
                    return redirect(url_for('listar_usuarios'))
                
                # Eliminamos el usuario
                cursor.execute("DELETE FROM usuarios WHERE id = %s", (id,))
                conn.commit()
                flash('Usuario eliminado exitosamente', 'success')
                
    except psycopg2.Error as err:  # Excepción específica de PostgreSQL
        flash(f'Error al eliminar usuario: {err.pgerror}', 'error')
    except Exception as err:  # Para otros errores inesperados
        flash(f'Error inesperado: {str(err)}', 'error')
    
    return redirect(url_for('listar_usuarios'))

# --------------------------- PRODUCTOS ---------------------------

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    if 'usuario' not in session or session['rol'] != 'admin':
        return redirect('/')

    mensaje = ''
    editar_id = request.args.get('editar')

    conn = conectar()
    cursor = conn.cursor()

    if request.method == 'POST':
        nombre = request.form['nombre']
        costo = float(request.form['costo'])
        precio = float(request.form['precio'])
        stock = int(request.form['stock'])
        marca = request.form.get('marca', '')
        rubro = request.form.get('rubro', '')

        try:
            if editar_id:
                cursor.execute(
                    """UPDATE productos SET nombre=%s, costo=%s, precio=%s, 
                    stock=%s, marca=%s, rubro=%s WHERE id=%s""",
                    (nombre, costo, precio, stock, marca, rubro, editar_id)
                )
                mensaje = "Producto actualizado con éxito."
            else:
                cursor.execute(
                    """INSERT INTO productos (nombre, costo, precio, stock, marca, rubro)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                    (nombre, costo, precio, stock, marca, rubro)
                )
                mensaje = f'¡Producto registrado con éxito! Precio de venta: ${precio:.2f}'
            conn.commit()
        except Exception as e:
            conn.rollback()
            mensaje = f'Error: {str(e)}'
        
    # Obtener productos
    cursor.execute("SELECT * FROM productos ORDER BY id")
    productos = cursor.fetchall()

    producto_a_editar = None
    if editar_id:
        cursor.execute("SELECT * FROM productos WHERE id=%s", (editar_id,))
        producto_a_editar = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('productos.html', 
                         productos=productos, 
                         mensaje=mensaje, 
                         producto=producto_a_editar)

# --------------------------- VENTAS ---------------------------

@app.route('/ventas', methods=['GET'])
def ver_ventas():
    if 'usuario' not in session:
        return redirect('/')

    # --- Parámetros de filtrado ---
    vendedor = request.args.get('vendedor')
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    # --- Parámetros de paginación ---
    page = request.args.get('page', 1, type=int)  # Página actual
    per_page = 10  # Registros por página
    offset = (page - 1) * per_page

    conn = conectar()
    cursor = conn.cursor(dictionary=True)

    # --- Consulta principal con filtros ---
    sql_base = """
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        WHERE 1=1
    """
    params = []
    if vendedor:
        sql_base += " AND v.usuario = %s"
        params.append(vendedor)
    if desde:
        sql_base += " AND DATE(v.fecha) >= %s"
        params.append(desde)
    if hasta:
        sql_base += " AND DATE(v.fecha) <= %s"
        params.append(hasta)

    # --- Contar total de registros ---
    cursor.execute(f"SELECT COUNT(*) AS total {sql_base}", params)
    total_rows = cursor.fetchone()['total']

    # --- Obtener registros paginados ---
    cursor.execute(f"""
        SELECT p.nombre AS producto, v.cantidad, v.usuario AS vendedor, 
               v.ganancia, v.total, v.fecha, v.forma_pago, v.cliente
        {sql_base}
        ORDER BY v.fecha DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    ventas = cursor.fetchall()

    # --- Calcular totales (para la página actual) ---
    total_ventas = sum(v['total'] for v in ventas)
    ganancia_total = sum((v['ganancia'] or 0) * v['cantidad'] for v in ventas)

    # --- Top 5 productos ---
    cursor.execute("""
        SELECT p.nombre, SUM(v.cantidad) as total_vendidos
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        GROUP BY p.nombre ORDER BY total_vendidos DESC LIMIT 5
    """)
    top5 = cursor.fetchall()

    # --- Lista de vendedores ---
    cursor.execute("SELECT DISTINCT usuario FROM ventas")
    vendedores = [r['usuario'] for r in cursor.fetchall()]

    # --- Deudas ---
    cursor.execute("""
        SELECT cliente AS nombre, 
               SUM(total) AS total, 
               SUM(saldo_pendiente) AS saldo_pendiente, 
               MAX(fecha) AS fecha
        FROM ventas
        WHERE forma_pago = 'Cuenta Corriente' AND saldo_pendiente > 0
        GROUP BY cliente
    """)
    deudas = cursor.fetchall()

    cursor.close()
    conn.close()

    # --- Calcular total de páginas ---
    total_pages = (total_rows + per_page - 1) // per_page

    return render_template(
        'ventas.html',
        ventas=ventas,
        total=round(total_ventas, 2),
        ganancia=round(ganancia_total, 2),
        top5=top5,
        vendedores=vendedores,
        deudas=deudas,
        page=page,
        total_pages=total_pages
    )

# --------------------------- CLIENTES ---------------------------

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'usuario' not in session:
        return redirect('/')

    conn = conectar()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        telefono = request.form.get('telefono')
        if nombre and telefono:
            cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (%s, %s)", (nombre, telefono))
            conn.commit()
            return redirect('/clientes')

    cursor.execute("SELECT * FROM clientes")
    lista = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('clientes.html', clientes=lista)

# --------------------------- VENTA ---------------------------

@app.route('/venta', methods=['GET', 'POST'])
def venta():
    if 'usuario' not in session:
        return redirect('/')

    try:
        with conectar() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Obtener productos con stock
                cursor.execute("SELECT * FROM productos WHERE stock > 0")
                productos = cursor.fetchall()

                # Obtener clientes
                cursor.execute("SELECT * FROM clientes ORDER BY nombre")
                clientes = cursor.fetchall()

                # Paginación
                pagina = request.args.get('page', 1, type=int)
                por_pagina = 10
                offset = (pagina - 1) * por_pagina

                cursor.execute("SELECT COUNT(*) AS total FROM ventas")
                total_ventas = cursor.fetchone()['total']

                cursor.execute("""
                    SELECT p.nombre AS producto, v.cantidad, v.cliente, v.forma_pago,
                           v.usuario AS vendedor, v.ganancia, v.total, v.fecha
                    FROM ventas v
                    JOIN productos p ON v.producto_id = p.id
                    ORDER BY v.fecha DESC
                    LIMIT %s OFFSET %s
                """, (por_pagina, offset))
                ventas = cursor.fetchall()

                total_paginas = (total_ventas + por_pagina - 1) // por_pagina

                # Lógica para POST
                if request.method == 'POST':
                    return handle_venta_post(conn, cursor, session['usuario'], productos)

    except psycopg2.Error as err:
        flash(f'Error de base de datos: {err.pgerror}', 'error')
        return redirect(url_for('venta'))

    return render_template(
        'venta.html',
        productos=productos,
        clientes=clientes,
        ventas=ventas,
        pagina=pagina,
        total_paginas=total_paginas
    )

def handle_venta_post(conn, cursor, usuario, productos):
    producto_id = request.form.get('producto')
    cantidad = request.form.get('cantidad')
    forma_pago = request.form.get('forma_pago')
    cliente = request.form.get('cliente', 'Consumidor Final')
    descuento = float(request.form.get('descuento', 0)) or 0

    # Validaciones
    if not producto_id:
        return jsonify({'success': False, 'message': "Debe seleccionar un producto"})
    
    if not cantidad or int(cantidad) <= 0:
        return jsonify({'success': False, 'message': "La cantidad debe ser mayor a cero"})
    
    cantidad = int(cantidad)
    
    # Validación para cuentas corrientes
    if forma_pago.lower() == 'cuenta corriente':
        if not cliente or cliente == 'Consumidor Final':
            return jsonify({'success': False, 'message': "Debe seleccionar un cliente registrado para ventas a cuenta corriente"})
        
        cursor.execute("SELECT id FROM clientes WHERE nombre = %s", (cliente,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': "El cliente no existe en la base de datos"})

    # Obtener producto
    cursor.execute("SELECT * FROM productos WHERE id = %s FOR UPDATE", (producto_id,))
    producto = cursor.fetchone()

    if not producto:
        return jsonify({'success': False, 'message': "Producto no encontrado."})
    
    if cantidad > producto['stock']:
        return jsonify({'success': False, 'message': f"No hay stock suficiente. Stock actual: {producto['stock']}"})

    # Cálculos
    precio_venta = float(producto['precio'])
    costo = float(producto['costo'])
    ganancia_unitaria = precio_venta - costo
    subtotal = precio_venta * cantidad
    total = subtotal - descuento

    if total < 0:
        return jsonify({'success': False, 'message': "El descuento no puede ser mayor que el total."})

    saldo_pendiente = total if forma_pago.lower() == 'cuenta corriente' else 0

    try:
        # Registrar venta
        cursor.execute("""
            INSERT INTO ventas 
            (producto_id, cantidad, usuario, ganancia, fecha, total, 
             forma_pago, cliente, descuento, saldo_pendiente)
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            producto_id, cantidad, usuario, ganancia_unitaria, 
            total, forma_pago, cliente, descuento, saldo_pendiente
        ))
        venta_id = cursor.fetchone()['id']

        # Actualizar stock
        nuevo_stock = producto['stock'] - cantidad
        cursor.execute("""
            UPDATE productos SET stock = %s WHERE id = %s
        """, (nuevo_stock, producto_id))

        # Registrar deuda si es cuenta corriente
        if forma_pago.lower() == 'cuenta corriente':
            cursor.execute("""
                INSERT INTO deudas_clientes 
                (cliente, venta_id, monto_original, saldo_pendiente, fecha)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (venta_id) DO UPDATE 
                SET saldo_pendiente = EXCLUDED.saldo_pendiente
            """, (cliente, venta_id, total, total))

        conn.commit()

        # Actualizar lista de productos
        cursor.execute("SELECT * FROM productos WHERE stock > 0")
        productos_actualizados = cursor.fetchall()

        return jsonify({
            'success': True,
            'message': "Venta registrada correctamente",
            'total': f"{total:.2f}",
            'forma_pago': forma_pago,
            'producto': producto['nombre'],
            'cantidad': cantidad,
            'venta_id': venta_id,
            'saldo_pendiente': f"{saldo_pendiente:.2f}" if saldo_pendiente > 0 else None,
            'es_cuenta_corriente': forma_pago.lower() == 'cuenta corriente',
            'stock_actualizado': nuevo_stock,
            'productos': [dict(p) for p in productos_actualizados]
        })

    except psycopg2.Error as err:
        conn.rollback()
        return jsonify({
            'success': False,
            'message': f"Error al registrar la venta: {err.pgerror}"
        })

    
    pass
@app.route('/recibo/<int:venta_id>')
def recibo(venta_id):
    conn = conectar()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT v.*, p.nombre AS producto_nombre
        FROM ventas v
        LEFT JOIN productos p ON v.producto_id = p.id
        WHERE v.id = %s
    """, (venta_id,))
    venta = cursor.fetchone()

    cursor.close()
    conn.close()

    if not venta:
        return "Venta no encontrada", 404

    return render_template('recibo.html', venta=venta)


# --------------------------- PAGOS CUENTA CORRIENTE ---------------------------

@app.route('/registrar_pago_cc', methods=['POST'])
def registrar_pago_cc():
    if 'usuario' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401

    venta_id = request.form.get('venta_id')
    cliente = request.form.get('cliente')
    monto = float(request.form.get('monto'))
    metodo_pago = request.form.get('metodo_pago')
    observaciones = request.form.get('observaciones', '')

    conn = conectar()
    cursor = conn.cursor()

    try:
        # Registrar el pago
        cursor.execute("""
            INSERT INTO pagos_corrientes 
            (venta_id, cliente, monto, metodo_pago, fecha, usuario, observaciones)
            VALUES (%s, %s, %s, %s, NOW(), %s, %s)
        """, (venta_id, cliente, monto, metodo_pago, session['usuario'], observaciones))

        # Actualizar saldo
        cursor.execute("""
            UPDATE ventas 
            SET saldo_pendiente = saldo_pendiente - %s
            WHERE id = %s
        """, (monto, venta_id))

        conn.commit()
        return jsonify({'success': True, 'message': 'Pago registrado correctamente'})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route('/cuentas_corrientes')
def cuentas_corrientes():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    conn = conectar()
    cursor = conn.cursor(dictionary=True)
    
    # Obtener deudas pendientes
    cursor.execute("""
        SELECT v.id as venta_id, v.cliente, v.total, v.saldo_pendiente, 
               v.fecha, p.nombre as producto, v.cantidad
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        WHERE v.forma_pago = 'Cuenta Corriente' AND v.saldo_pendiente > 0
        ORDER BY v.fecha DESC
    """)
    deudas = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('cuentas_corrientes.html', deudas=deudas)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))



    

# --------------------------- INICIO APP ---------------------------

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)











