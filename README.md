# Planeación institucional · Comfamiliar Risaralda

Paquete de consulta para Streamlit Community Cloud. Contiene datos corporativos reales del último corte; utilice un repositorio privado y configure el ingreso de Google Workspace para `comfamiliar.com`.

## Qué subir

Suba **todo el contenido de esta carpeta** a la raíz del repositorio. Incluya `.streamlit/`, `assets/` y `modelo_powerbi/`. No suba solamente el ZIP ni agregue una carpeta intermedia si va a seleccionar `app.py` como archivo principal.

El paquete contiene el código, el diseño HTML/CSS y exclusivamente los 15 Parquet del corte publicado. Los Parquet ya contienen el histórico cerrado y las tres tablas que vienen del Excel. No necesita subir el Excel original.

## Desplegar

1. Conecte su cuenta de GitHub en https://share.streamlit.io/.
2. Cree una aplicación, seleccione este repositorio y su rama.
3. Archivo principal: `app.py`. En opciones avanzadas, seleccione **Python 3.12**, que es la versión con la que se verificó este proyecto.
4. Configure el cliente Google y sus Secrets siguiendo **SEGURIDAD_Y_ACCESO.md**. Sin esa configuración el paquete bloquea la consulta. Opcionalmente mantenga las invitaciones privadas de Streamlit como segunda barrera.
5. Comparta el enlace `https://nombre.streamlit.app`, que entrega Streamlit. El enlace del repositorio muestra archivos; no ejecuta el tablero.

La configuración incluida conserva el diseño y deja la dirección de escucha bajo control de la plataforma. No agrega credenciales de IBM i a Streamlit Secrets. El proceso web lee Parquet y no importa ODBC ni solicita credenciales de IBM i.

## Ingreso integrado y diseño ejecutivo

La portada permite seleccionar año y trimestre y presenta el avance frente a la meta, la calificación promedio y el desempeño por área. Utiliza las medidas y reglas del informe original; no cambia sus filtros ni fórmulas. Los conteos históricos abarcan todo el corte publicado.

El paquete exige ingreso OIDC de Google Workspace para `comfamiliar.com` mediante `acceso_tablero.py`. Sin configurar el cliente y sus Secrets, bloquea los datos. Consulte **SEGURIDAD_Y_ACCESO.md** para activar el ingreso en `https://tablero-mando.streamlit.app/`.

El panel **Actualizar información** se conserva para administradores autorizados. Solicita la extracción a un servicio corporativo preparado para recibirla; las credenciales de IBM i se escriben en una ventana local de ese servicio. Su despliegue HTTPS y sus claves todavía requieren configuración externa. Consulte **SERVICIO_CORPORATIVO.md**. No tiene credenciales IBM i en el visor ni simula una actualización sin servicio.

## Espacios de dirección

Las 13 vistas se agrupan en **Visión ejecutiva, Desempeño, Gestión operativa, Seguimiento y Estrategia**, con modos internos que conservan enlaces y filtros originales. Solo se calcula el modo activo. Los gráficos, tablas, fichas y exportación bajo demanda se describen en **DISENO_DIRECCION.md**. El rediseño se aplica a todas las secciones.

La vista de procesos incluye una matriz con **+ / −** para abrir actividades sin perder los demás procesos y sus totales. **CONCILIACION_POWERBI.md** documenta el cotejo con el motor DAX original y la diferencia entre las fechas de carga del PBIX y el corte publicado.

## Quién puede consultar, actualizar y publicar

- **Consultar:** las cuentas de Google Workspace autorizadas del dominio corporativo. Si mantiene además la app privada en Streamlit, deben figurar también como invitadas. No necesitan usuario ni contraseña de IBM i.
- **Extraer datos nuevos de IBM i:** una persona con acceso a la red corporativa, Python, ODBC, el DSN `salud`, credenciales válidas de lectura y el Excel original. Este proceso se ejecuta localmente.
- **Publicar una copia nueva:** una persona con permisos de escritura en GitHub. Estos permisos son distintos de los de IBM i: un editor del repositorio puede modificar o reemplazar archivos publicados aunque no tenga acceso a la base. Limite quién puede escribir en el repositorio.

El botón **Recargar datos** abre el último corte ya publicado y conserva los filtros. No consulta IBM i y no publica cambios a GitHub.

## Cómo actualizar desde la PC corporativa

En el proyecto original que conserva el DSN y `Despliegue 2022.xlsx`:

```powershell
python actualizar_planes.py
python preparar_repo_streamlit.py
```

También puede utilizar `ACTUALIZAR_DATOS.bat` y después `PREPARAR_REPO.bat`.

Tras la actualización, suba el contenido regenerado de `repo_streamlit` al repositorio en un único commit. La copia en la nube cambia cuando se publican los nuevos archivos en GitHub; actualizar solamente la PC no modifica la copia desplegada.

Si clonó este repositorio a otra PC corporativa, instale `requirements-local.txt`, reutilice el DSN y el controlador ya configurados y proporcione el Excel original localmente. La reconstrucción completa sigue disponible mediante `python actualizar_planes.py --reconstruir`.

## Separación técnica

- `modelo_consulta.py` se genera de las constantes, relaciones, funciones y clase de lectura del actualizador. Las fórmulas se conservan sin reinterpretación. No contiene funciones de extracción ni importa `pyodbc`.
- `actualizar_planes.py` conserva el proceso local completo. El servidor de consulta no lo importa.
- `requirements.txt` instala únicamente las dependencias de consulta.
- `requirements-local.txt` agrega ODBC y lectura de Excel para la PC que actualiza.
- `preparar_repo_streamlit.py` reconstruye el paquete desde un corte completo y verifica la coherencia antes de generar el ZIP. No consulta la base ni solicita credenciales.

No se incluyen el Excel, notebooks, credenciales, registros de diagnóstico, perfiles del navegador, entornos Python ni versiones anteriores. Los originales permanecen en el proyecto de la PC corporativa.
