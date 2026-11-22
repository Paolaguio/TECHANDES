import re
import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from db import consultar, ejecutar, mensaje_error
from seguridad import login_requerido

bp = Blueprint("clientes", __name__, url_prefix="/clientes")

CIUDADES = [
    "Bogotá",
    "Medellín",
    "Cali",
    "Barranquilla",
    "Cartagena",
    "Bucaramanga",
    "Ibagué",
    "Pereira",
    "Manizales",
    "Cúcuta",
]

PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.route("/")
@login_requerido
def lista():
    buscar = request.args.get("buscar", "").strip()
    ciudad = request.args.get("ciudad", "").strip()

    sql = """SELECT c.id_cliente, c.documento, c.nombre, c.apellido,
                    c.correo, c.telefono, c.ciudad,
                    COUNT(p.id_pedido) AS pedidos
             FROM clientes c
             LEFT JOIN pedidos p ON p.id_cliente = c.id_cliente
             WHERE 1 = 1"""
    parametros = []

    if buscar:
        sql += " AND (c.nombre LIKE %s OR c.apellido LIKE %s OR c.documento LIKE %s)"
        like = f"%{buscar}%"
        parametros.extend([like, like, like])

    if ciudad:
        sql += " AND c.ciudad = %s"
        parametros.append(ciudad)

    sql += """ GROUP BY c.id_cliente, c.documento, c.nombre, c.apellido,
                        c.correo, c.telefono, c.ciudad
               ORDER BY c.nombre, c.apellido"""

    clientes = consultar(sql, parametros)
    ciudades_bd = consultar("SELECT DISTINCT ciudad FROM clientes WHERE ciudad IS NOT NULL ORDER BY ciudad")
    lista_ciudades = sorted({*CIUDADES, *(fila["ciudad"] for fila in ciudades_bd)})

    return render_template(
        "clientes/lista.html",
        clientes=clientes,
        ciudades=lista_ciudades,
        buscar=buscar,
        ciudad=ciudad,
    )


def leer_formulario():
    datos = {
        "documento": request.form.get("documento", "").strip(),
        "nombre": request.form.get("nombre", "").strip(),
        "apellido": request.form.get("apellido", "").strip(),
        "correo": request.form.get("correo", "").strip().lower(),
        "telefono": request.form.get("telefono", "").strip(),
        "ciudad": request.form.get("ciudad", "").strip(),
    }
    errores = []

    if not datos["documento"].isdigit():
        errores.append("El documento debe contener solo números.")
    if not datos["nombre"]:
        errores.append("Los nombre son obligatorios.")
    if not datos["apellido"]:
        errores.append("Los apellido son obligatorios.")
    if not PATRON_CORREO.match(datos["correo"]):
        errores.append("Ingrese un correo electrónico válido.")
    if datos["ciudad"] not in CIUDADES:
        errores.append("Seleccione una ciudad válida de la lista.")

    return datos, errores


@bp.route("/nuevo", methods=["GET", "POST"])
@login_requerido
def nuevo():
    datos = {
        "documento": "",
        "nombre": "",
        "apellido": "",
        "correo": "",
        "telefono": "",
        "ciudad": "",
    }
    if request.method == "POST":
        datos, errores = leer_formulario()
        if not errores:
            try:
                ejecutar(
                    """INSERT INTO clientes (documento, nombre, apellido, correo, telefono, ciudad)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        datos["documento"],
                        datos["nombre"],
                        datos["apellido"],
                        datos["correo"],
                        datos["telefono"] or None,
                        datos["ciudad"],
                    ),
                )
                flash(f"Cliente {datos['nombre']} {datos['apellido']} registrado.", "exito")
                return redirect(url_for("clientes.lista"))
            except pymysql.MySQLError as error:
                if error.args and error.args[0] == 1062:
                    errores.append("Ya existe un cliente con ese documento o correo.")
                else:
                    errores.append(mensaje_error(error))

        for e in errores:
            flash(e, "error")

    return render_template(
        "clientes/formulario.html",
        datos=datos,
        ciudades=CIUDADES,
        titulo="Nuevo cliente",
    )


@bp.route("/<int:id_cliente>")
@login_requerido
def detalle(id_cliente):
    cliente = consultar(
        """SELECT id_cliente, documento, nombre, apellido, correo, telefono, ciudad
           FROM clientes
           WHERE id_cliente = %s""",
        (id_cliente,),
        uno=True,
    )
    if cliente is None:
        abort(404)

    resumen = consultar(
        """SELECT COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total_comprado
           FROM pedidos p
           JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
           WHERE p.id_cliente = %s AND p.estado <> 'CANCELADO'""",
        (id_cliente,),
        uno=True,
    )

    pedidos = consultar(
        """SELECT p.id_pedido, p.fecha_pedido, p.estado, p.metodo_pago,
                  CONCAT(e.nombres, ' ', e.apellidos) AS vendedor,
                  COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
           FROM pedidos p
           JOIN empleados e ON e.id_empleado = p.id_empleado
           LEFT JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
           WHERE p.id_cliente = %s
           GROUP BY p.id_pedido, p.fecha_pedido, p.estado, p.metodo_pago, e.nombres, e.apellidos
           ORDER BY p.fecha_pedido DESC, p.id_pedido DESC""",
        (id_cliente,),
    )

    return render_template(
        "clientes/detalle.html",
        cliente=cliente,
        total_comprado=resumen["total_comprado"],
        pedidos=pedidos,
    )