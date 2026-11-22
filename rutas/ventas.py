from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from db import consultar, obtener_conexion
from seguridad import login_requerido

bp = Blueprint("ventas", __name__, url_prefix="/ventas")

METODOS_PAGO = ["EFECTIVO", "TARJETA", "TRANSFERENCIA", "PSE"]
NUM_FILAS = 5


class ErrorVenta(Exception):
    """Error de negocio: aborta la transacción con un mensaje claro."""


def leer_lineas():
    """Lee las filas de producto y cantidad y acumula cantidades por producto."""
    items = {}
    errores = []

    for i in range(1, NUM_FILAS + 1):
        id_prod_raw = request.form.get(f"producto_{i}", "").strip()
        cant_raw = request.form.get(f"cantidad_{i}", "").strip()

        if not id_prod_raw and not cant_raw:
            continue

        if not id_prod_raw.isdigit():
            errores.append(f"Fila {i}: seleccione un producto válido.")
            continue

        if not cant_raw.isdigit() or int(cant_raw) <= 0:
            errores.append(f"Fila {i}: la cantidad debe ser un número entero mayor que 0.")
            continue

        id_producto = int(id_prod_raw)
        cantidad = int(cant_raw)
        items[id_producto] = items.get(id_producto, 0) + cantidad

    if not items and not errores:
        errores.append("Debe agregar al menos un producto a la venta.")

    return items, errores


def registrar_pedido(id_cliente, metodo_pago, items):
    """Inserta pedido + detalle y descuenta stock. Todo o nada."""
    conexion = obtener_conexion()
    conexion.begin()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """INSERT INTO pedidos (id_cliente, id_empleado, estado, metodo_pago)
                   VALUES (%s, %s, 'PENDIENTE', %s)""",
                (id_cliente, session["usuario"]["id_empleado"], metodo_pago),
            )
            id_pedido = cursor.lastrowid

            for id_producto, cantidad in items.items():
                cursor.execute(
                    """SELECT nombre, precio, stock, activo
                       FROM productos
                       WHERE id_producto = %s FOR UPDATE""",
                    (id_producto,),
                )
                producto = cursor.fetchone()

                if producto is None or not producto["activo"]:
                    raise ErrorVenta(f"El producto {id_producto} no está disponible.")

                if producto["stock"] < cantidad:
                    raise ErrorVenta(
                        f"Stock insuficiente de {producto['nombre']}: "
                        f"hay {producto['stock']}, se piden {cantidad}."
                    )

                cursor.execute(
                    """INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario)
                       VALUES (%s, %s, %s, %s)""",
                    (id_pedido, id_producto, cantidad, producto["precio"]),
                )

                cursor.execute(
                    """UPDATE productos
                       SET stock = stock - %s
                       WHERE id_producto = %s""",
                    (cantidad, id_producto),
                )

        conexion.commit()
        return id_pedido
    except Exception:
        conexion.rollback()
        raise


@bp.route("/nueva", methods=["GET", "POST"])
@login_requerido
def nueva():
    clientes = consultar(
        """SELECT id_cliente, documento, CONCAT(nombre, ' ', apellido) AS nombre
           FROM clientes
           ORDER BY nombre, apellido"""
    )
    productos = consultar(
        """SELECT id_producto, nombre, precio, stock
           FROM productos
           WHERE activo = 1
           ORDER BY nombre"""
    )

    id_cliente_sel = request.form.get("id_cliente", "") if request.method == "POST" else ""
    metodo_pago_sel = request.form.get("metodo_pago", "EFECTIVO") if request.method == "POST" else "EFECTIVO"

    if request.method == "POST":
        errores = []
        if not id_cliente_sel.isdigit():
            errores.append("Seleccione un cliente.")

        if metodo_pago_sel not in METODOS_PAGO:
            errores.append("Seleccione un método de pago válido.")

        items, errores_lineas = leer_lineas()
        errores.extend(errores_lineas)

        if not errores:
            try:
                id_pedido = registrar_pedido(int(id_cliente_sel), metodo_pago_sel, items)
                flash(f"Venta registrada: pedido #{id_pedido}", "exito")
                return redirect(url_for("pedidos.detalle", id_pedido=id_pedido))
            except ErrorVenta as err:
                errores.append(str(err))
            except Exception as err:
                errores.append(f"No se pudo registrar la venta: {err}")

        for e in errores:
            flash(e, "error")

    return render_template(
        "ventas/nueva.html",
        clientes=clientes,
        productos=productos,
        metodos_pago=METODOS_PAGO,
        num_filas=NUM_FILAS,
        id_cliente_sel=id_cliente_sel,
        metodo_pago_sel=metodo_pago_sel,
    )