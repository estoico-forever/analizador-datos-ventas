#!/usr/bin/env python3
"""
Analizador automatico de datos de ventas
========================================
Toma un CSV crudo (con los errores tipicos de un archivo hecho a mano),
lo limpia, lo analiza y genera un informe con graficas.

Uso:
    python analizador_ventas.py datos.csv --salida informe/

Autor: Diego Barrionuevo - Ing. Telecomunicaciones, Universidad de Antioquia
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


COLORES = ["#2E6F95", "#E8833A", "#54A24B", "#B279A2", "#8C8C8C"]


# ----------------------------------------------------------------------
# 1. LIMPIEZA
# ----------------------------------------------------------------------
def limpiar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Limpia el dataset y devuelve (df_limpio, bitacora_de_cambios)."""
    bitacora = []
    n0 = len(df)

    # Normalizar nombres de columna
    df.columns = (df.columns.str.strip().str.lower()
                  .str.replace(" ", "_").str.replace(r"[^\w]", "", regex=True))
    bitacora.append(f"Columnas normalizadas: {list(df.columns)}")

    # Duplicados exactos
    dups = df.duplicated().sum()
    if dups:
        df = df.drop_duplicates()
        bitacora.append(f"Eliminadas {dups} filas duplicadas exactas")

    # Fechas
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
        malas = df["fecha"].isna().sum()
        if malas:
            bitacora.append(f"{malas} fechas ilegibles -> marcadas como nulas")

    # Numericos: quitar simbolos de moneda, separadores de miles, espacios
    for col in ("monto", "cantidad", "precio_unitario"):
        if col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = (df[col].astype(str)
                           .str.replace(r"[$\s]", "", regex=True)
                           .str.replace(".", "", regex=False)
                           .str.replace(",", ".", regex=False))
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Texto: unificar mayusculas/minusculas y espacios
    for col in ("producto", "vendedor", "ciudad", "categoria"):
        if col in df.columns:
            df[col] = df[col].astype("object").astype(str).str.strip().str.title()
            df[col] = df[col].replace({"Nan": np.nan, "": np.nan})

    # Negativos imposibles
    if "monto" in df.columns:
        neg = (df["monto"] < 0).sum()
        if neg:
            df = df[df["monto"] >= 0]
            bitacora.append(f"Eliminadas {neg} filas con monto negativo")

    # Filas sin dato clave
    claves = [c for c in ("fecha", "monto") if c in df.columns]
    if claves:
        antes = len(df)
        df = df.dropna(subset=claves)
        if antes - len(df):
            bitacora.append(f"Eliminadas {antes-len(df)} filas sin fecha o monto")

    bitacora.append(f"Registros: {n0} entraron -> {len(df)} quedaron utiles "
                    f"({len(df)/n0*100:.1f}%)")
    return df.reset_index(drop=True), bitacora


# ----------------------------------------------------------------------
# 2. ANALISIS
# ----------------------------------------------------------------------
def detectar_atipicos(s: pd.Series) -> pd.Series:
    """Metodo del rango intercuartilico (Tukey, k=1.5)."""
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    return (s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)


def analizar(df: pd.DataFrame) -> dict:
    r = {}
    m = df["monto"]

    r["n"] = len(df)
    r["total"] = m.sum()
    r["promedio"] = m.mean()
    r["mediana"] = m.median()
    r["desv"] = m.std()
    r["cv"] = m.std() / m.mean() if m.mean() else np.nan

    # Intervalo de confianza al 95% para la media (t de Student)
    from scipy import stats
    ic = stats.t.interval(0.95, len(m) - 1, loc=m.mean(),
                          scale=stats.sem(m))
    r["ic95"] = ic

    r["atipicos"] = int(detectar_atipicos(m).sum())

    if "fecha" in df.columns:
        serie = df.set_index("fecha")["monto"].resample("ME").sum()
        r["serie_mensual"] = serie
        if len(serie) >= 3:
            x = np.arange(len(serie))
            pend, inter, rval, pval, _ = stats.linregress(x, serie.values)
            r["tendencia_pendiente"] = pend
            r["tendencia_intercepto"] = inter
            r["tendencia_r2"] = rval ** 2
            r["tendencia_pval"] = pval

    for dim in ("producto", "vendedor", "ciudad", "categoria"):
        if dim in df.columns:
            r[f"por_{dim}"] = (df.groupby(dim)["monto"]
                               .agg(["sum", "count", "mean"])
                               .sort_values("sum", ascending=False))
    return r


# ----------------------------------------------------------------------
# 3. GRAFICAS
# ----------------------------------------------------------------------
def graficar(df, res, salida: Path):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 130})
    generadas = []

    if "serie_mensual" in res and len(res["serie_mensual"]) > 1:
        fig, ax = plt.subplots(figsize=(9, 4))
        s = res["serie_mensual"]
        ax.plot(s.index, s.values, marker="o", color=COLORES[0], lw=2)
        if "tendencia_pendiente" in res:
            x = np.arange(len(s))
            ax.plot(s.index,
                    res["tendencia_pendiente"] * x + res["tendencia_intercepto"],
                    "--", color=COLORES[1], lw=1.5, label="tendencia lineal")
            ax.legend(frameon=False)
        ax.set_title("Ventas por mes", fontweight="bold", loc="left")
        ax.set_ylabel("Monto")
        ax.grid(axis="y", alpha=0.25)
        fig.autofmt_xdate()
        fig.tight_layout()
        p = salida / "01_evolucion_mensual.png"
        fig.savefig(p); plt.close(fig); generadas.append(p)

    for dim in ("producto", "vendedor", "ciudad", "categoria"):
        k = f"por_{dim}"
        if k in res:
            top = res[k].head(8)
            fig, ax = plt.subplots(figsize=(8, max(3, 0.45 * len(top) + 1.2)))
            ax.barh(top.index[::-1], top["sum"][::-1], color=COLORES[0])
            ax.set_title(f"Ventas totales por {dim}", fontweight="bold", loc="left")
            ax.set_xlabel("Monto total")
            ax.grid(axis="x", alpha=0.25)
            fig.tight_layout()
            p = salida / f"02_por_{dim}.png"
            fig.savefig(p); plt.close(fig); generadas.append(p)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(df["monto"], bins=30, color=COLORES[0], edgecolor="white")
    ax.axvline(res["promedio"], color=COLORES[1], ls="--", lw=2, label="promedio")
    ax.axvline(res["mediana"], color=COLORES[2], ls="--", lw=2, label="mediana")
    ax.set_title("Distribucion del monto por venta", fontweight="bold", loc="left")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    p = salida / "03_distribucion.png"
    fig.savefig(p); plt.close(fig); generadas.append(p)
    return generadas


# ----------------------------------------------------------------------
# 4. INFORME
# ----------------------------------------------------------------------
def informe(res, bitacora, graficas, salida: Path):
    f = lambda v: f"{v:,.0f}".replace(",", ".")
    L = ["# Informe de analisis de ventas", "",
         "Generado automaticamente.", "",
         "## 1. Calidad de los datos", ""]
    L += [f"- {b}" for b in bitacora]
    L += ["", "## 2. Resumen general", "",
          "| Indicador | Valor |", "|---|---|",
          f"| Registros analizados | {f(res['n'])} |",
          f"| Venta total | ${f(res['total'])} |",
          f"| Venta promedio | ${f(res['promedio'])} |",
          f"| Mediana | ${f(res['mediana'])} |",
          f"| Desviacion estandar | ${f(res['desv'])} |",
          f"| Coeficiente de variacion | {res['cv']:.1%} |",
          f"| IC 95% de la media | ${f(res['ic95'][0])} - ${f(res['ic95'][1])} |",
          f"| Ventas atipicas detectadas | {res['atipicos']} |", ""]

    L += ["### Como leer esto", ""]
    if res["promedio"] > res["mediana"] * 1.15:
        L.append("- El promedio esta bastante por encima de la mediana: unas pocas ventas "
                 "grandes estan inflando el promedio. **Para planear, usa la mediana**, "
                 "que representa mejor la venta tipica.")
    else:
        L.append("- Promedio y mediana son parecidos: la distribucion es razonablemente "
                 "simetrica y el promedio si representa bien la venta tipica.")
    if res["cv"] > 0.75:
        L.append(f"- La variabilidad es alta (CV {res['cv']:.0%}): las ventas son muy "
                 "irregulares entre si. Proyectar con el promedio va a fallar seguido.")
    L.append("")

    if "tendencia_pendiente" in res:
        p, r2, pv = res["tendencia_pendiente"], res["tendencia_r2"], res["tendencia_pval"]
        signo = "creciente" if p > 0 else "decreciente"
        sig = "estadisticamente significativa" if pv < 0.05 else "NO significativa (puede ser ruido)"
        L += ["## 3. Tendencia", "",
              f"- Tendencia **{signo}**: {f(abs(p))} por mes en promedio.",
              f"- R^2 = {r2:.2f} (la tendencia explica {r2:.0%} de la variacion mensual).",
              f"- p = {pv:.4f} -> la tendencia es {sig}.", ""]
        if pv >= 0.05:
            L.append("> Cuidado: no hay evidencia suficiente para afirmar que las ventas "
                     "esten realmente subiendo o bajando. Lo que se ve puede ser variacion normal.")
            L.append("")

    n = 4
    for dim in ("producto", "vendedor", "ciudad", "categoria"):
        k = f"por_{dim}"
        if k in res:
            t = res[k]
            L += [f"## {n}. Desempeno por {dim}", "",
                  f"| {dim.title()} | Total | Ventas | Promedio |", "|---|---|---|---|"]
            for i, row in t.head(10).iterrows():
                L.append(f"| {i} | ${f(row['sum'])} | {int(row['count'])} | ${f(row['mean'])} |")
            share = t['sum'].iloc[0] / t['sum'].sum()
            L += ["", f"- **{t.index[0]}** concentra el {share:.0%} del total.", ""]
            if share > 0.4:
                L.append(f"> Riesgo de concentracion: depender {share:.0%} de un solo "
                         f"{dim} es fragil. Vale la pena diversificar.")
                L.append("")
            n += 1

    if graficas:
        L += [f"## {n}. Graficas", ""]
        L += [f"![{g.stem}]({g.name})" for g in graficas]

    (salida / "informe.md").write_text("\n".join(L), encoding="utf-8")
    return salida / "informe.md"


def main():
    ap = argparse.ArgumentParser(description="Analiza un CSV de ventas y genera un informe.")
    ap.add_argument("csv")
    ap.add_argument("--salida", default="informe")
    a = ap.parse_args()

    salida = Path(a.salida); salida.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(a.csv)
    print(f"Leidos {len(df)} registros de {a.csv}")

    df, bit = limpiar(df)
    for b in bit:
        print("  ·", b)
    if df.empty:
        sys.exit("No quedaron datos utiles tras la limpieza.")

    df.to_csv(salida / "datos_limpios.csv", index=False)
    res = analizar(df)
    gr = graficar(df, res, salida)
    inf = informe(res, bit, gr, salida)
    print(f"\nListo -> {inf}  ({len(gr)} graficas)")


if __name__ == "__main__":
    main()
