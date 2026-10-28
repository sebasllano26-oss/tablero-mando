# Conciliación con el Power BI original — 27/10/2026

Se abrió `Seguimiento Planes Operativos Final.pbix` en Power BI Desktop y se
consultó su motor local de Analysis Services mediante DAX de solo lectura.
No se actualizaron sus datos ni se modificó el PBIX. Su SHA-256 coincide con
el archivo del que se extrajo originalmente el informe:
`0bd6f68d0b03b03c60f843c2feb5b127ac39ca20c3c5f373eacd5242ef1c35dd`.

## Diferencia de cortes

El PBIX contiene la actualización del **14/10/2026**. El corte publicado de
Python corresponde al **26/10/2026**, versión
`70ef9218c1474de7811efc29d52fe5a7`.

Ambas instantáneas tienen **14.292 filas y 14.292 llaves distintas**. Hay
**216 calificaciones de 2026** que estaban en blanco en el PBIX y ahora tienen
valor. No son correcciones de calificaciones previamente informadas en ese
conjunto: son calificaciones nuevas. Comparar cifras de estas dos fechas sin
igualar los datos produce diferencias reales de resultado.

En el contexto **2026 / SERVICIOS / 3er Trimestre**, usando exactamente las
tablas del PBIX, la migración reproduce la captura:

| Resultado | Power BI y Python con datos del PBIX | Python con el corte actual |
|---|---:|---:|
| Cumplimiento | 70,708567 % | 71,030093 % |
| Cumplimiento ponderado | 94,278090 % | 94,706790 % |
| Meta | 75 % | 75 % |

La consulta real a IBM i realizada el **27/10/2026** coincide con todas las
columnas del corte actual al ordenar por llave, con tolerancia numérica de
`1e-12`. Por eso se conservó ese corte; no se reemplazó con los datos antiguos
del PBIX ni se avanzó artificialmente su fecha de publicación.

## Consulta corporativa comprobada

Se reutilizaron Python, ODBC y el DSN `salud`. Las credenciales se ingresaron en
una ventana local y no se incluyeron en archivos, argumentos ni registros.
Se ejecutó exclusivamente la ventana incremental parametrizada:

```sql
SELECT * FROM JFM.VTPLANOPERATIVO
WHERE (ANO >= ? OR ANO IS NULL)
```

Parámetro: `2026`. El filtro forma parte de `cursor.execute(sql, parametros)`;
se envía al servidor antes de `fetchmany`, no se aplica después de descargar
toda la vista.

| Medición real ODBC | Resultado |
|---|---:|
| Conexión | 3,511 s |
| Ejecución de la consulta | 0,157 s |
| Descarga | 36,583 s |
| Filas descargadas | 2.432 |
| Filas históricas conservadas | 11.860 |
| Filas combinadas | 14.292 |

La consulta de contraste generó un candidato local fuera de `modelo_powerbi`;
no publicó las 15 tablas ni midió una actualización completa. La comprobación
local posterior de igualdad y hashes tomó 1,474 s. No se ejecutó una carga
completa corporativa para comparar tiempos.

## Defectos corregidos

También había defectos de la migración, independientes de la fecha del corte:

- El promedio de Polars podía diferir del promedio tabular en la última cifra
  binaria. En tres clasificaciones próximas al 95 % eso cambiaba el icono.
  Se corrigió la acumulación y se contrastó contra el DAX real, sin redondear
  los datos ni modificar los umbrales originales.
- Faltaba calcular la clasificación de quince totales. Ahora el total tiene
  su cálculo y estado propios; no es el promedio de los porcentajes de grupos.
- La vista de procesos no ofrecía el despliegue individual de la matriz
  original. Ahora cada proceso tiene **+ / −**, sus actividades aparecen debajo,
  las dos medidas conservan sus iconos y el total permanece visible.

La matriz permite abrir varios procesos, seleccionar un padre o una actividad
para relacionar los indicadores, quitar la selección, contraer todo y exportar
los procesos y actividades. Solo se consultan localmente las ramas abiertas,
con paginación; navegar no llama a IBM i. **Gráfico y tabla** conserva la
presentación alternativa y el desglose anterior.

## Alcance de la validación

Se compararon **36 contextos y 2.571 filas** de resultados contra consultas
reales al motor DAX del PBIX, usando las mismas 15 tablas. Se comprobaron
claves, medidas, clasificaciones, totales y clasificaciones de totales:
**cero diferencias** después de las correcciones. Esto valida esos contextos
y ese corte; no pretende verificar todas las combinaciones futuras de filtros.

La suite completa pasó **65 pruebas**, sin fallos, errores ni omisiones.
La ejecución del runner registró 51,027 s (56,635 s incluyendo descubrimiento e
importaciones). Incluye actualización incremental simulada, reglas originales,
regresiones de precisión y jerarquía, navegación, exportación, autorización,
servicio simulado e integridad/apertura del paquete sin ODBC ni Excel.

Edge comprobó apertura, selección, eliminación de la selección y cierre de la
matriz con datos actuales y de referencia, además de móvil de 390 px. Los padres
y el total permanecieron estables al desplegar; no hubo desbordamiento horizontal
global. La tabla conserva su propio desplazamiento horizontal en móvil.

De los 50 archivos originalmente protegidos, **49 conservan su hash**.
`consultas_tablero.py` es el único cambio deliberado para corregir estos defectos.
Permanecen intactos el actualizador, Excel, definición del informe, datos,
histórico y corte publicado. Se conservan relaciones, exclusión de 2027,
«Tareas 2024» literal y «prueba» bloqueada.

## Repetir la comprobación local

Las evidencias corporativas permanecen en `.revision_conciliacion` y no se
incluyen en el ZIP de publicación. Mientras estén los servicios locales:

- `http://127.0.0.1:8501/?vista=procesos`: corte publicado actual.
- `http://127.0.0.1:8503/?vista=procesos`: referencia del PBIX, identificada con
  una advertencia visible y preparada con los filtros de la captura.

La segunda dirección es una herramienta local de conciliación; el paquete para
GitHub usa el corte actual. Para comparar posteriormente, iguale **fecha de
carga, año, área, trimestre y filtros de página/visual** en ambos sistemas.

Evidencias: `consulta_ibmi.json`, `verificacion_datos.json`,
`resultado_cotejo_dax.json`, consultas y respuestas en `cotejo_dax/`,
`matriz_navegador.json`, `pruebas_completas.json`, `pruebas_completas.log`
y capturas en `.revision_conciliacion/`.

Archivos de implementación modificados: `app.py`, `consultas_tablero.py` y
`preparar_repo_streamlit.py`; nuevo componente `matriz_jerarquica.py`.
Se actualizaron documentación y pruebas y se regeneraron `repo_streamlit/`
y `tablero_streamlit_repo.zip`. No se publicó a GitHub ni se activó Google.
