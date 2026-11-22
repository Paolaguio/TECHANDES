from pathlib import Path
from werkzeug.security import generate_password_hash

ADMINS = [
    ("mprieto", 1),
    ("hbustos", 2),
    ("crobayo", 3),
]

VENDEDORES = [
    ("klozada", 4),
    ("ytafur", 5),
    ("boviedo", 6),
    ("lmurcia", 7),
    ("fcuellar", 8),
]

CLAVE_ADMIN = "Admin2026*"
CLAVE_VENDEDOR = "Ventas2026*"


def main():
    carpeta_sql = Path("sql")
    carpeta_sql.mkdir(exist_ok=True)

    filas = []
    for usuario, id_empleado in ADMINS:
        hash_clave = generate_password_hash(CLAVE_ADMIN)
        filas.append(f"    ('{usuario}', '{hash_clave}', 'ADMIN', {id_empleado})")

    for usuario, id_empleado in VENDEDORES:
        hash_clave = generate_password_hash(CLAVE_VENDEDOR)
        filas.append(f"    ('{usuario}', '{hash_clave}', 'VENDEDOR', {id_empleado})")

    script_sql = (
        "USE techandes;\n\n"
        "INSERT INTO usuarios (usuario, clave_hash, rol, id_empleado) VALUES\n"
        + ",\n".join(filas)
        + ";\n"
    )

    salida = carpeta_sql / "01_usuarios.sql"
    salida.write_text(script_sql, encoding="utf-8")
    print(f"Listo: {salida} generado con {len(filas)} usuarios.")


if __name__ == "__main__":
    main()