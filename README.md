# Analizador automático de datos de ventas

Pieza de portafolio — Diego Barrionuevo, Ing. de Telecomunicaciones, Universidad de Antioquia.

Toma un CSV crudo (el archivo real que tiene una empresa pequeña: montos con "$" y puntos de
miles, fechas en formatos mezclados, duplicados, filas vacías, nombres escritos de tres maneras
distintas) y devuelve datos limpios, gráficas y un informe que se entiende sin ser técnico.

## Qué hace

**1. Limpieza auditada.** No limpia en silencio: cada cambio queda registrado en una bitácora
que va en el informe. El cliente puede ver exactamente qué se descartó y por qué.

- Normaliza nombres de columna
- Elimina duplicados exactos
- Convierte fechas en formatos mixtos y marca las imposibles (`31/02/2025`)
- Limpia montos con símbolo de moneda y separadores de miles latinos
- Unifica texto inconsistente (`CARLOS PENA` / `Carlos Peña ` → `Carlos Pena`)
- Descarta negativos imposibles y filas sin dato clave

**2. Análisis estadístico real, no solo sumas.**

- Descriptivos + coeficiente de variación
- Intervalo de confianza del 95% para la media (t de Student)
- Detección de atípicos por rango intercuartílico (Tukey)
- Regresión lineal sobre la serie mensual **con su p-valor** — si la tendencia no es
  significativa, el informe lo dice explícitamente en vez de vender humo

**3. Informe interpretado.** La parte que casi nadie entrega. El informe no dice solo
"el promedio es X"; dice *qué hacer con eso*:

> El promedio está bastante por encima de la mediana: unas pocas ventas grandes están
> inflando el promedio. **Para planear, usa la mediana.**

> Riesgo de concentración: depender 47% de una sola ciudad es frágil.

> Cuidado: no hay evidencia suficiente para afirmar que las ventas estén subiendo.
> Lo que se ve puede ser variación normal.

## Uso

```bash
pip install pandas numpy scipy matplotlib
python analizador_ventas.py ventas.csv --salida informe/
```

Genera `datos_limpios.csv`, `informe.md` y las gráficas en PNG.

## Demo incluida

`generar_datos_demo.py` crea un CSV deliberadamente sucio (925 filas con duplicados, fechas
inválidas, montos vacíos y negativos, mayúsculas inconsistentes). El analizador recupera
872 registros útiles — 94.3% — y reporta cada descarte.

```bash
python generar_datos_demo.py
python analizador_ventas.py ventas_demo.csv --salida informe_demo/
```

Resultado en `informe_demo/`.

## Adaptable

El script detecta qué columnas existen y ajusta el análisis. Sirve para ventas, inventario,
registros de producción o cualquier tabla con una fecha y un valor numérico.
