# Tablero para dirección y líderes de proceso

Las trece vistas originales se agrupan en cinco espacios. Se conservan las
fórmulas, los filtros, los niveles de detalle y los enlaces directos.

| Espacio | Modos de análisis |
|---|---|
| Visión ejecutiva | Resumen institucional y cobertura histórica |
| Desempeño | Áreas; Procesos |
| Gestión operativa | Plan de trabajo; Ejecución de tareas; Volumen de gestión |
| Seguimiento | Por calificar; Procesos pendientes; Factores limitantes |
| Estrategia | Objetivos; Estrategias; Contribución por área; Sin relación |

Cada espacio recuerda el último modo abierto. Explorar datos permanece como
herramienta secundaria y Actualizar información conserva su acceso administrativo.

## Lectura de resultados

Los filtros frecuentes aparecen sobre los resultados. **Ajustes** contiene los
filtros adicionales y las acciones de restablecer o limpiar. Las etiquetas muestran
el contexto efectivo, incluidos los filtros propios: no se impone un trimestre
global a informes con reglas distintas. Las tarjetas indican sus filtros propios.

- Áreas y ejecución: comparación con etiquetas numéricas y referencia de meta
  cuando el contexto tiene una meta definida.
- Procesos: matriz expandible con **+ / −** por proceso, actividades subordinadas,
  dos medidas, clasificación original y total con su propio estado. Seleccione
  un padre o actividad para relacionar los indicadores; puede abrir varios
  procesos sin perder el resto. **Gráfico y tabla** conserva la comparación
  alternativa con puntos y el desglose por nivel.
- Estrategia: comparación de puntos con la medida original. Los
  resultados estratégicos ponderados conservan sus reglas propias.
- Volumen: actividades y tareas como cantidades enteras.
- Pendientes y limitantes: registros de revisión y detalle textual, sin indicadores
  de riesgo inventados a partir de descripciones.

Calificación promedio y avance frente a la meta son conceptos distintos. El panel
lateral informa el resultado del contexto comparado, los extremos y la distribución
de estados disponible. Los estados relativos conservan sus umbrales originales.

**Opciones de la comparación** permite cambiar orden y cantidad visible y, cuando
corresponde, la medida. El gráfico indica cuántos elementos representa; la tabla
conserva el listado completo paginado. Seleccione una barra o punto para relacionar
el detalle; **Quitar selección** recupera el contexto anterior.

## Tablas y fichas

En el plan se priorizan actividad, tarea, responsable y fecha final. En limitantes
se prioriza el factor junto a la tarea y actividad. **Columnas del detalle** permite
recuperar las demás columnas. La calificación incluye barra de progreso y valor;
los estados se muestran como texto y color.

Seleccione una fila para abrir, debajo de la tabla, su ficha con toda la información
original, incluidos problema, estrategia, meta, recursos e indicador cuando existen.
**Desglose del detalle** conserva la jerarquía de las matrices originales.

**Preparar CSV de la selección completa** calcula el archivo solo cuando se solicita.
Incluye todas las filas y columnas del nivel elegido, no únicamente las 100 visibles.
El CSV usa punto y coma y UTF-8; los porcentajes conservan el valor numérico de origen.
Los textos interpretables como fórmulas por hojas de cálculo se protegen con un
apóstrofo al exportar, sin alterar el modelo.

## Rendimiento y entrega

Se calcula solo el modo activo. Se reutilizan Parquet, agregados y cachés acotadas,
incluida la construcción de gráficos. Navegar no consulta IBM i ni el Excel. La
exportación se calcula bajo demanda. Los gráficos visibles añaden trabajo de
presentación; las mediciones locales no garantizan tiempos en Streamlit Cloud.

No cambian actualización incremental, modelo, Excel, exclusión de 2027, «Tareas
2024» literal, «prueba» bloqueada ni configuración de red.

La entrega es el contenido de `repo_streamlit` y su ZIP equivalente. La versión de
nube conserva el ingreso obligatorio ya preparado para Google Workspace. Su
configuración y la publicación remota quedan para la siguiente fase.
