#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Imprime un dato del cliente que el workflow necesita, y nada mas.

Existe para que el workflow no tenga python anidado adentro de un bucle de
shell: eso es justo donde se cuelan los errores de escapado que despues nadie
ve. Aca se puede probar suelto.

    python3 datos_cliente.py <cid> clave     la clave, del secreto ACCESOS_CLAVES
    python3 datos_cliente.py <cid> fuente    la ruta dentro del repo privado

LA CLAVE SALE DE UN MAPA Y NO DE UN SECRETO POR CLIENTE. Actions no puede armar
el nombre de un secreto en tiempo de ejecucion, asi que un secreto por cliente
obligaria a editar el workflow en cada alta. Con el mapa ACCESOS_CLAVES el
workflow no se vuelve a tocar nunca.

Si el mapa no tiene al cliente se prueba ACCESO_<CID>_CLAVE, que es como estaba
antes del 16/11. Eso deja a La Union de Colon andando aunque el mapa falte o
venga mal, que es lo que importa mientras se hace el cambio.
"""
import json, os, sys, pathlib

if len(sys.argv) < 3:
    sys.exit("uso: datos_cliente.py <cid> <clave|fuente>")
cid, campo = sys.argv[1], sys.argv[2]
AQUI = pathlib.Path(__file__).resolve().parent

if campo == "clave":
    crudo = os.environ.get("ACCESOS_CLAVES", "").strip()
    mapa = {}
    if crudo:
        try:
            mapa = json.loads(crudo)
        except Exception:
            print("AVISO: ACCESOS_CLAVES no es JSON valido", file=sys.stderr)
    k = (mapa.get(cid) or os.environ.get(f"ACCESO_{cid.upper()}_CLAVE", "")).strip()
    # Se imprime sin salto para que el shell no se coma nada raro; si no hay
    # clave se imprime vacio y el workflow lo trata como error de ese cliente.
    sys.stdout.write(k)
elif campo == "fuente":
    f = AQUI / "clientes" / f"{cid}.json"
    d = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    # index.html es el tablero de Liga Argentina en el repo privado: es el
    # valor que tenia el workflow clavado antes de que hubiera mas de una liga.
    sys.stdout.write(d.get("fuente_privada") or "index.html")
else:
    sys.exit(f"campo desconocido: {campo}")
