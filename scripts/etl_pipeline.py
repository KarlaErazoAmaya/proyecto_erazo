"""
=============================================================
ETL — Violencia contra las Mujeres en México (SESNSP 2015-2025)
Proyecto Final · Módulo 4: Inteligencia de negocios y SQL avanzado
Diplomado IIMAS, UNAM
=============================================================

Extract  -> lee el CSV crudo del SESNSP (formato ancho, un mes por columna)
Transform-> filtra subtipos de interés, convierte a formato largo,
            agrupa por (entidad, subtipo, año, mes), construye las
            3 dimensiones y genera las surrogate keys
Load     -> inserta dimensiones y tabla de hechos en Aurora PostgreSQL
            usando SQLAlchemy + pandas.to_sql()

Uso:
    export AURORA_HOST=tu-host.rds.amazonaws.com
    export AURORA_PASSWORD=tu_password
    python etl_pipeline.py
"""

import os
import sys
import logging

import pandas as pd
from sqlalchemy import create_engine, text

# -------------------------------------------------------------
# Configuración y logging
# -------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("etl_violencia")

CSV_PATH = os.path.join("datasets", "Estatal-Delitos-2015-2025_abr2026.csv")

AURORA_HOST = os.environ.get("AURORA_HOST")
AURORA_USER = os.environ.get("AURORA_USER", "postgres")
AURORA_PASSWORD = os.environ.get("AURORA_PASSWORD")
AURORA_DB = os.environ.get("AURORA_DB", "northwind")
AURORA_PORT = os.environ.get("AURORA_PORT", "5432")

SCHEMA = "violencia_dwh"

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

# Catálogo de subtipos relevantes para violencia contra las mujeres,
# con su categoría analítica y si son delitos letales o no.
DELITOS_INTERES = {
    "Feminicidio":          {"categoria": "Violencia letal intencional",     "es_letal": True},
    "Homicidio doloso":     {"categoria": "Violencia letal intencional",     "es_letal": True},
    "Homicidio culposo":    {"categoria": "Violencia letal no intencional",  "es_letal": True},
    "Lesiones dolosas":     {"categoria": "Violencia no letal",              "es_letal": False},
    "Lesiones culposas":    {"categoria": "Violencia no letal",              "es_letal": False},
    "Trata de personas":    {"categoria": "Violencia no letal",              "es_letal": False},
    "Violencia familiar":   {"categoria": "Violencia no letal",              "es_letal": False},
    "Violencia de género en todas sus modalidades distinta a la violencia familiar":
                            {"categoria": "Violencia no letal",              "es_letal": False},
    "Acoso sexual":         {"categoria": "Violencia no letal",              "es_letal": False},
    "Hostigamiento sexual": {"categoria": "Violencia no letal",              "es_letal": False},
    "Abuso sexual":         {"categoria": "Violencia no letal",              "es_letal": False},
    "Violación simple":     {"categoria": "Violencia no letal",              "es_letal": False},
    "Violación equiparada": {"categoria": "Violencia no letal",              "es_letal": False},
}

# Regiones geográficas por entidad (para dim_entidad.region)
REGIONES = {
    "Aguascalientes": "Centro", "Baja California": "Norte", "Baja California Sur": "Norte",
    "Campeche": "Sur", "Coahuila de Zaragoza": "Norte", "Colima": "Centro",
    "Chiapas": "Sur", "Chihuahua": "Norte", "Ciudad de México": "CDMX",
    "Durango": "Norte", "Guanajuato": "Centro", "Guerrero": "Sur",
    "Hidalgo": "Centro", "Jalisco": "Centro", "México": "Centro",
    "Michoacán de Ocampo": "Centro", "Morelos": "Centro", "Nayarit": "Centro",
    "Nuevo León": "Norte", "Oaxaca": "Sur", "Puebla": "Centro",
    "Querétaro": "Centro", "Quintana Roo": "Sur", "San Luis Potosí": "Centro",
    "Sinaloa": "Norte", "Sonora": "Norte", "Tabasco": "Sur",
    "Tamaulipas": "Norte", "Tlaxcala": "Centro",
    "Veracruz de Ignacio de la Llave": "Sur", "Yucatán": "Sur", "Zacatecas": "Centro",
}

# Años afectados por la pandemia de COVID-19
ANIOS_PANDEMIA = {2020, 2021}


# -------------------------------------------------------------
# EXTRACT
# -------------------------------------------------------------
def extract(csv_path: str) -> pd.DataFrame:
    """Lee el CSV crudo del SESNSP."""
    log.info("Extract: leyendo %s", csv_path)
    df = pd.read_csv(csv_path, encoding="latin-1")
    log.info("Extract: %d filas, %d columnas leídas", *df.shape)
    return df


# -------------------------------------------------------------
# TRANSFORM
# -------------------------------------------------------------
def transform(df: pd.DataFrame) -> dict:
    """
    Transforma el DataFrame crudo (formato ancho) en las tablas
    del modelo dimensional (formato largo + dimensiones).

    Devuelve un diccionario con 4 DataFrames listos para cargar:
        - dim_tiempo
        - dim_entidad
        - dim_delito
        - fact_victimas (con las FK ya resueltas)
    """
    log.info("Transform: filtrando subtipos de interés")
    subtipos = list(DELITOS_INTERES.keys())
    df_filtrado = df[df["Subtipo de delito"].isin(subtipos)].copy()
    log.info("Transform: %d filas tras filtrar subtipos", len(df_filtrado))

    # -----------------------------------------------------------
    # 1. Formato ancho -> largo (un mes por fila)
    # -----------------------------------------------------------
    id_cols = ["Año", "Clave_Ent", "Entidad", "Bien jurídico afectado",
               "Tipo de delito", "Subtipo de delito"]

    df_largo = df_filtrado.melt(
        id_vars=id_cols,
        value_vars=MESES,
        var_name="nombre_mes",
        value_name="num_victimas"
    )

    # Mapear nombre de mes -> número de mes
    mes_a_numero = {mes: i + 1 for i, mes in enumerate(MESES)}
    df_largo["mes"] = df_largo["nombre_mes"].map(mes_a_numero)

    # -----------------------------------------------------------
    # 2. Agrupar para llegar al grano (entidad x subtipo x año x mes)
    #    Algunos subtipos vienen desagregados por "Modalidad"
    #    (ej. Homicidio doloso con arma de fuego / arma blanca / etc.)
    #    Se suman para obtener el total mensual por subtipo.
    # -----------------------------------------------------------
    log.info("Transform: agrupando por entidad x subtipo x año x mes")
    df_agrupado = (
        df_largo
        .groupby(
            ["Año", "Clave_Ent", "Entidad", "Bien jurídico afectado",
             "Tipo de delito", "Subtipo de delito", "mes", "nombre_mes"],
            as_index=False
        )["num_victimas"]
        .sum()
    )
    log.info("Transform: %d filas tras agrupar (grano final de la fact)", len(df_agrupado))

    # -----------------------------------------------------------
    # 3. dim_tiempo
    # -----------------------------------------------------------
    log.info("Transform: construyendo dim_tiempo")
    periodos = df_agrupado[["Año", "mes", "nombre_mes"]].drop_duplicates()
    periodos = periodos.sort_values(["Año", "mes"]).reset_index(drop=True)

    dim_tiempo = periodos.rename(columns={"Año": "anio"}).copy()
    dim_tiempo["trimestre"] = ((dim_tiempo["mes"] - 1) // 3) + 1
    dim_tiempo["semestre"] = ((dim_tiempo["mes"] - 1) // 6) + 1
    dim_tiempo["periodo_label"] = (
        dim_tiempo["anio"].astype(str) + "-" + dim_tiempo["mes"].astype(str).str.zfill(2)
    )
    dim_tiempo["es_anio_pandemia"] = dim_tiempo["anio"].isin(ANIOS_PANDEMIA)
    dim_tiempo["id_tiempo"] = range(1, len(dim_tiempo) + 1)

    dim_tiempo = dim_tiempo[[
        "id_tiempo", "anio", "mes", "nombre_mes",
        "trimestre", "semestre", "periodo_label", "es_anio_pandemia"
    ]]

    # -----------------------------------------------------------
    # 4. dim_entidad
    # -----------------------------------------------------------
    log.info("Transform: construyendo dim_entidad")
    entidades = df_agrupado[["Clave_Ent", "Entidad"]].drop_duplicates()
    entidades = entidades.sort_values("Clave_Ent").reset_index(drop=True)

    dim_entidad = entidades.rename(
        columns={"Clave_Ent": "clave_entidad", "Entidad": "nombre_entidad"}
    ).copy()
    dim_entidad["region"] = dim_entidad["nombre_entidad"].map(REGIONES)
    dim_entidad["id_entidad"] = range(1, len(dim_entidad) + 1)

    dim_entidad = dim_entidad[["id_entidad", "clave_entidad", "nombre_entidad", "region"]]

    # -----------------------------------------------------------
    # 5. dim_delito
    # -----------------------------------------------------------
    log.info("Transform: construyendo dim_delito")
    delitos = df_agrupado[
        ["Bien jurídico afectado", "Tipo de delito", "Subtipo de delito"]
    ].drop_duplicates().reset_index(drop=True)

    dim_delito = delitos.rename(columns={
        "Bien jurídico afectado": "bien_juridico",
        "Tipo de delito": "tipo_delito",
        "Subtipo de delito": "subtipo_delito"
    }).copy()

    dim_delito["categoria"] = dim_delito["subtipo_delito"].map(
        lambda s: DELITOS_INTERES[s]["categoria"]
    )
    dim_delito["es_letal"] = dim_delito["subtipo_delito"].map(
        lambda s: DELITOS_INTERES[s]["es_letal"]
    )
    dim_delito["descripcion"] = (
        dim_delito["tipo_delito"] + " - " + dim_delito["subtipo_delito"]
    )
    dim_delito["id_delito"] = range(1, len(dim_delito) + 1)

    dim_delito = dim_delito[[
        "id_delito", "bien_juridico", "tipo_delito",
        "subtipo_delito", "categoria", "es_letal", "descripcion"
    ]]

    # -----------------------------------------------------------
    # 6. fact_victimas — resolver surrogate keys (FK)
    # -----------------------------------------------------------
    log.info("Transform: resolviendo surrogate keys para fact_victimas")

    fact = df_agrupado.merge(
        dim_tiempo[["id_tiempo", "anio", "mes"]],
        left_on=["Año", "mes"], right_on=["anio", "mes"], how="left"
    )
    fact = fact.merge(
        dim_entidad[["id_entidad", "clave_entidad"]],
        left_on="Clave_Ent", right_on="clave_entidad", how="left"
    )
    fact = fact.merge(
        dim_delito[["id_delito", "subtipo_delito"]],
        left_on="Subtipo de delito", right_on="subtipo_delito", how="left"
    )

    fact_victimas = fact[["id_tiempo", "id_entidad", "id_delito", "num_victimas"]].copy()
    fact_victimas["fuente"] = "SESNSP - Incidencia delictiva estatal"

    log.info("Transform: fact_victimas lista con %d filas", len(fact_victimas))

    return {
        "dim_tiempo": dim_tiempo,
        "dim_entidad": dim_entidad,
        "dim_delito": dim_delito,
        "fact_victimas": fact_victimas,
    }


# -------------------------------------------------------------
# LOAD
# -------------------------------------------------------------
def load(tablas: dict, engine) -> None:
    """Carga las 4 tablas en Aurora dentro del schema violencia_dwh."""
    orden_carga = ["dim_tiempo", "dim_entidad", "dim_delito", "fact_victimas"]

    with engine.begin() as conn:
        for nombre in orden_carga:
            log.info("Load: vaciando tabla %s.%s", SCHEMA, nombre)
            conn.execute(text(f"TRUNCATE TABLE {SCHEMA}.{nombre} CASCADE"))

    for nombre in orden_carga:
        df = tablas[nombre]
        log.info("Load: insertando %d filas en %s.%s", len(df), SCHEMA, nombre)
        df.to_sql(
            nombre,
            engine,
            schema=SCHEMA,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )

    log.info("Load: carga completada")


# -------------------------------------------------------------
# VALIDATE
# -------------------------------------------------------------
def validate(tablas: dict, engine) -> None:
    """Valida que los conteos en Aurora coincidan con los DataFrames cargados."""
    log.info("Validate: comparando conteos contra origen")
    with engine.connect() as conn:
        for nombre, df in tablas.items():
            resultado = conn.execute(
                text(f"SELECT COUNT(*) FROM {SCHEMA}.{nombre}")
            ).scalar()
            esperado = len(df)
            estado = "OK" if resultado == esperado else "MISMATCH"
            log.info(
                "  %-15s esperado=%-6d cargado=%-6d [%s]",
                nombre, esperado, resultado, estado
            )

        # Validación adicional: integridad referencial (sin FKs huérfanas)
        huerfanas = conn.execute(text(f"""
            SELECT COUNT(*) FROM {SCHEMA}.fact_victimas f
            LEFT JOIN {SCHEMA}.dim_tiempo t ON f.id_tiempo = t.id_tiempo
            LEFT JOIN {SCHEMA}.dim_entidad e ON f.id_entidad = e.id_entidad
            LEFT JOIN {SCHEMA}.dim_delito d ON f.id_delito = d.id_delito
            WHERE t.id_tiempo IS NULL
               OR e.id_entidad IS NULL
               OR d.id_delito IS NULL
        """)).scalar()
        log.info("  filas con FK huérfanas en fact_victimas: %d", huerfanas)

        # Validación adicional: suma total de víctimas
        suma_df = sum(
            df["num_victimas"].sum()
            for nombre, df in tablas.items() if nombre == "fact_victimas"
        )
        suma_db = conn.execute(
            text(f"SELECT SUM(num_victimas) FROM {SCHEMA}.fact_victimas")
        ).scalar()
        log.info("  suma num_victimas -> origen=%d, Aurora=%d", suma_df, suma_db)


# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():
    if not AURORA_HOST or not AURORA_PASSWORD:
        log.error("Faltan variables de entorno AURORA_HOST / AURORA_PASSWORD")
        sys.exit(1)

    if not os.path.exists(CSV_PATH):
        log.error("No se encontró el archivo: %s", CSV_PATH)
        sys.exit(1)

    # Extract
    df_crudo = extract(CSV_PATH)

    # Transform
    tablas = transform(df_crudo)

    # Conexión a Aurora
    conn_str = (
        f"postgresql+psycopg2://{AURORA_USER}:{AURORA_PASSWORD}"
        f"@{AURORA_HOST}:{AURORA_PORT}/{AURORA_DB}"
    )
    engine = create_engine(conn_str)

    # Load
    load(tablas, engine)

    # Validate
    validate(tablas, engine)

    log.info("ETL finalizado correctamente")


if __name__ == "__main__":
    main()
