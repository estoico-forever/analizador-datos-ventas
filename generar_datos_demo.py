"""Genera un CSV desordenado y realista, para demostrar la limpieza."""
import numpy as np, pandas as pd
rng = np.random.default_rng(7)
n = 900
prod = ["Router WiFi 6","Switch 24p","Antena sectorial","Cable UTP Cat6","ONT Fibra","Repetidor mesh"]
vend = ["Ana Torres","Luis Gomez","Marta Ruiz","Carlos Pena"]
ciu  = ["Medellin","Bogota","Cali","Barranquilla","Bucaramanga"]
fechas = pd.date_range("2025-01-05","2026-08-25",periods=n)
base = rng.lognormal(12.6,0.75,n)*(1+0.35*np.arange(n)/n)   # tendencia creciente
df = pd.DataFrame({
    " Fecha ": fechas.strftime("%d/%m/%Y"),
    "Producto": rng.choice(prod,n),
    "Vendedor": rng.choice(vend,n),
    "Ciudad": rng.choice(ciu,n,p=[.38,.25,.16,.12,.09]),
    "Cantidad": rng.integers(1,9,n),
    "MONTO": base.round(0),
})
# ensuciar como un archivo real
df["MONTO"] = df["MONTO"].map(lambda v: f"$ {v:,.0f}".replace(",","."))
idx = rng.choice(n,40,replace=False)
df.loc[idx[:12],"MONTO"] = ""                      # vacios
df.loc[idx[12:20]," Fecha "] = "31/02/2025"        # fechas invalidas
df.loc[idx[20:28],"MONTO"] = "-50.000"             # negativos
df.loc[idx[28:],"Vendedor"] = df.loc[idx[28:],"Vendedor"].str.upper()  # inconsistencia
df = pd.concat([df, df.sample(25, random_state=1)])  # duplicados
df.sample(frac=1, random_state=3).to_csv("ventas_demo.csv", index=False)
print("ventas_demo.csv generado:", len(df), "filas")
