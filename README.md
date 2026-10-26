# Planeación institucional · Comfamiliar Risaralda

Paquete de consulta para Streamlit Community Cloud. Contiene datos corporativos reales del último corte; utilice un repositorio privado y configure la aplicación para personas invitadas.

## Qué subir

Suba **todo el contenido de esta carpeta** a la raíz del repositorio. Incluya `.streamlit/`, `assets/` y `modelo_powerbi/`. No suba solamente el ZIP ni agregue una carpeta intermedia si va a seleccionar `app.py` como archivo principal.

El paquete contiene el código, el diseño HTML/CSS y exclusivamente los 15 Parquet del corte publicado. Los Parquet ya contienen el histórico cerrado y las tres tablas que vienen del Excel. No necesita subir el Excel original.

## Desplegar

1. Conecte su cuenta de GitHub en https://share.streamlit.io/.
2. Cree una aplicación, seleccione este repositorio y su rama.
3. Archivo principal: `app.py`. En opciones avanzadas, seleccione **Python 3.12**, que es la versión con la que se verificó este proyecto.
4. Despliegue y, en **Settings → Sharing**, seleccione **Only specific people can view this app** para restringir la consulta e invite sus correos.
5. Comparta el enlace `https://nombre.streamlit.app`, que entrega Streamlit. El enlace del repositorio muestra archivos; no ejecuta el tablero.

La configuración incluida conserva el diseño y deja la dirección de escucha bajo control de la plataforma. No agrega credenciales de IBM i a Streamlit Secrets. El proceso web lee Parquet y no importa ODBC ni solicita credenciales corporativas.

## Quién puede consultar, actualizar y publicar

- **Consultar:** los visitantes autorizados en Streamlit. No necesitan usuario ni contraseña de IBM i. Si hace pública la aplicación, sus datos quedarán disponibles para sus visitantes.
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
