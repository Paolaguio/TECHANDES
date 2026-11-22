from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from db import consultar, obtener_conexion
from seguridad import login_requerido

bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")

ESTADOS = ["PENDIENTE", "ENVIADO", "ENTREGADO", "CANCELADO"]


@bp.route("/")
@login_requerido
def lista():
    estado = request.args.get("estado", "").strip().upper()

    sql = """SELECT p.id_pedido, p.fecha_pedido, p.estado, p.metodo_pago,
                    CONCAT(c.nombre, ' ', c.apellido) AS cliente,
                    CONCAT(e.nombres, ' ', e.apellidos) AS vendedor,
                    COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
             FROM pedidos p
             JOIN clientes c ON c.id_cliente = p.id_cliente
             JOIN empleados e ON e.id_empleado = p.id_empleado
             LEFT JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
             WHERE 1 = 1"""
    parametros = []

    if estado in ESTADOS:
        sql += " AND p.estado = %s"
        parametros.append(estado)
    else:
        estado = ""

    sql += """ GROUP BY p.id_pedido, p.fecha_pedido, p.estado, p.metodo_pago,
                c.apellido, e.nombres, e.apellidos
               ORDER BY p.fecha_pedido DESC, p.id_pedido DESC"""

    pedidos = consultar(sql, parametros)
    return render_template(
        "pedidos/lista.html",
        pedidos=pedidos,
        estados=ESTADOS,
        estado_filtro=estado,
    )


@bp.route("/<int:id_pedido>", methods=["GET", "POST"])
@login_requerido
def detalle(id_pedido):
    if request.method == "POST":
        nuevo_estado = request.form.get("estado", "").strip().upper()
        if nuevo_estado not in ESTADOS:
            flash("Estado no válido.", "error")
            return redirect(url_for("pedidos.detalle", id_pedido=id_pedido))

        conexion = obtener_conexion()
        conexion.begin()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT estado FROM pedidos WHERE id_pedido = %s FOR UPDATE",
                    (id_pedido,),
                )
                pedido_actual = cursor.fetchone()
                if pedido_actual is None:
                    conexion.rollback()
                    abort(404)

                actual = pedido_actual["estado"]

                if actual == nuevo_estado:
                    conexion.rollback()
                    flash("El pedido ya tiene ese estado.", "aviso")
                elif actual == "CANCELADO":
                    conexion.rollback()
                    flash("Un pedido cancelado no se puede modificar.", "error")
                else:
                    if nuevo_estado == "CANCELADO":
                        cursor.execute(
                            """SELECT id_producto, cantidad
                               FROM detalle_pedido
                               WHERE id_pedido = %s""",
                            (id_pedido,),
                        )
                        for linea in cursor.fetchall():
                            cursor.execute(
                                """UPDATE productos
                                   SET stock = stock + %s
                                   WHERE id_producto = %s""",
                                (linea["cantidad"], linea["id_producto"]),
                            )

                    cursor.execute(
                        "UPDATE pedidos SET estado = %s WHERE id_pedido = %s",
                        (nuevo_estado, id_pedido),
                    )
                    conexion.commit()

                    if nuevo_estado == "CANCELADO":
                        flash("Pedido cancelado. Las unidades volvieron al inventario.", "exito")
                    else:
                        flash(f"Estado actualizado a {nuevo_estado}.", "exito")
        except Exception as err:
            conexion.rollback()
            flash(f"No se pudo actualizar el pedido: {err}", "error")

        return redirect(url_for("pedidos.detalle", id_pedido=id_pedido))

    pedido = consultar(
        """SELECT p.id_pedido, p.fecha_pedido, p.estado, p.metodo_pago,
                  CONCAT(c.nombre, ' ', c.apellido) AS cliente, c.documento, c.ciudad,
                  CONCAT(e.nombres, ' ', e.apellidos) AS vendedor, e.cargo
           FROM pedidos p
           JOIN clientes c ON c.id_cliente = p.id_cliente
           JOIN empleados e ON e.id_empleado = p.id_empleado
           WHERE p.id_pedido = %s""",
        (id_pedido,),
        uno=True,
    )
    if pedido is None:
        abort(404)

    items = consultar(
        """SELECT d.cantidad, d.precio_unitario,
                  (d.cantidad * d.precio_unitario) AS subtotal,
                  pr.nombre AS producto
           FROM detalle_pedido d
           JOIN productos pr ON pr.id_producto = d.id_producto
           WHERE d.id_pedido = %s
           ORDER BY pr.nombre""",
        (id_pedido,),
    )

    total = sum((item["subtotal"] or 0) for item in items)

    return render_template(
        "pedidos/detalle.html",
        pedido=pedido,
        items=items,
        total=total,
        estados=ESTADOS,
    )