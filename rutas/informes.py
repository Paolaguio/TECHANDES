from flask import Blueprint, render_template
from db import consultar
from seguridad import rol_requerido

bp = Blueprint("informes", __name__, url_prefix="/informes")


@bp.route("/")
@rol_requerido("ADMIN")
def index():
    # 1. Ventas por categoría (sin cancelados)
    por_categoria = consultar(
        """SELECT c.nombre AS categoria,
                  COALESCE(SUM(d.cantidad), 0) AS unidades,
                  COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
           FROM categorias c
           LEFT JOIN productos pr ON pr.id_categoria = c.id_categoria
           LEFT JOIN detalle_pedido d ON d.id_producto = pr.id_producto
           LEFT JOIN pedidos p ON p.id_pedido = d.id_pedido AND p.estado <> 'CANCELADO'
           GROUP BY c.id_categoria, c.nombre
           ORDER BY total DESC, c.nombre ASC"""
    )

    gran_total = sum(float(fila["total"] or 0) for fila in por_categoria)
    for fila in por_categoria:
        total_cat = float(fila["total"] or 0)
        fila["porcentaje"] = round((total_cat / gran_total * 100), 1) if gran_total > 0 else 0.0

    # 2. Ranking de vendedores con RANK() OVER
    ranking_vendedores = consultar(
        """SELECT RANK() OVER (ORDER BY COALESCE(SUM(d.cantidad * d.precio_unitario), 0) DESC) AS puesto,
                  CONCAT(e.nombres, ' ', e.apellidos) AS vendedor,
                  e.cargo,
                  COUNT(DISTINCT p.id_pedido) AS pedidos,
                  COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
           FROM empleados e
           LEFT JOIN pedidos p ON p.id_empleado = e.id_empleado AND p.estado <> 'CANCELADO'
           LEFT JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
           GROUP BY e.id_empleado, e.nombres, e.apellidos, e.cargo
           ORDER BY puesto ASC, vendedor ASC"""
    )

    # 3. Top 5 productos por unidades vendidas
    top_productos = consultar(
        """SELECT pr.id_producto, pr.nombre AS producto, c.nombre AS categoria,
                  SUM(d.cantidad) AS unidades,
                  SUM(d.cantidad * d.precio_unitario) AS total
           FROM detalle_pedido d
           JOIN pedidos p ON p.id_pedido = d.id_pedido
           JOIN productos pr ON pr.id_producto = d.id_producto
           JOIN categorias c ON c.id_categoria = pr.id_categoria
           WHERE p.estado <> 'CANCELADO'
           GROUP BY pr.id_producto, pr.nombre, c.nombre
           ORDER BY unidades DESC, total DESC
           LIMIT 5"""
    )

    # 4. Clientes sin compras con NOT EXISTS
    clientes_sin_compras = consultar(
        """SELECT c.id_cliente, c.documento,
                  CONCAT(c.nombre, ' ', c.apellido) AS cliente,
                  c.correo, c.telefono, c.ciudad
           FROM clientes c
           WHERE NOT EXISTS (
               SELECT 1
               FROM pedidos p
               WHERE p.id_cliente = c.id_cliente
                 AND p.estado <> 'CANCELADO'
           )
           ORDER BY c.nombre, c.apellido"""
    )

    return render_template(
        "informes/index.html",
        por_categoria=por_categoria,
        gran_total=gran_total,
        ranking_vendedores=ranking_vendedores,
        top_productos=top_productos,
        clientes_sin_compras=clientes_sin_compras,
    )