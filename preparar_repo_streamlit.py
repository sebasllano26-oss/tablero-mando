"""Preparar código y un corte coherente para GitHub/Streamlit, sin consultar IBM i."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parent
DIRECTORIO = 'repo_streamlit'
ZIP = 'tablero_streamlit_repo.zip'
DEFINICIONES = {'ErrorDatos', '_lazy', '_sum', '_count', '_divide', '_group', 'ModeloPowerBI'}
CONSTANTES = {'ESQUEMA', 'PLAN', 'ESTRATEGIAS', 'MATRIZ', 'CORPORATIVAS', 'ESQUEMAS',
             'TRIMESTRES', 'METAS', 'RELACIONES', 'CALENDARIOS', 'AREA_REPLACEMENTS',
             'PROCESS_REPLACEMENTS', 'FINAL_PROCESS'}

LEEME = '''# Planeación institucional · Comfamiliar Risaralda

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
'''

IGNORAR = '''__pycache__/
*.py[cod]
.venv/
venv/
.env
.env.*
.streamlit/secrets.toml
*.xlsx
*.ipynb
.revision*/
.paquetes_anteriores/
repo_streamlit/
tablero_streamlit_repo.zip
modelo_powerbi/.cargando-*/
modelo_powerbi/.actualizando-*/
modelo_powerbi/.actualizacion.lock
'''


def nombres_asignados(node):
    return {n.id for target in node.targets for n in ast.walk(target) if isinstance(n, ast.Name)}


def generar_modelo_consulta(source):
    tree = ast.parse(source)
    parts = []
    found = set()
    for node in tree.body:
        selected = isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in DEFINICIONES
        if isinstance(node, ast.Assign):
            selected = bool(nombres_asignados(node) & CONSTANTES)
        if selected:
            parts.append(ast.get_source_segment(source, node))
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                found.add(node.name)
    if found != DEFINICIONES:
        raise ValueError('El actualizador cambió: faltan definiciones necesarias para la consulta.')
    header = ('"""Modelo de consulta generado; fórmulas idénticas al actualizador local. No usa ODBC."""\n'
              'from datetime import date, datetime, timedelta\nimport json\nimport os\nfrom pathlib import Path\n'
              'os.environ.setdefault("POLARS_MAX_THREADS", "2")\nimport polars as pl\n\n')
    result = header + '\n\n\n'.join(parts) + '\n'
    compile(result, 'modelo_consulta.py', 'exec')
    return result


def configuracion_cloud(source):
    lines, section = [], ''
    for line in source.splitlines():
        if line.strip().startswith('['):
            section = line.strip()
        if section != '[server]':
            lines.append(line)
    return '# Configuración del visor en nube; la plataforma controla el servidor.\n' + '\n'.join(lines).lstrip() + '\n'


def crear_paquete():
    pointer = ROOT / 'modelo_powerbi/actual.json'
    original_pointer = pointer.read_bytes()
    manifest = json.loads(original_pointer)
    if len(manifest.get('tablas', {})) != 15:
        raise ValueError('El corte debe contener las 15 tablas publicadas.')
    destination = (ROOT / DIRECTORIO).resolve()
    if not destination.is_relative_to(ROOT) or destination.is_symlink():
        raise ValueError('Destino de paquete inválido.')
    if destination.exists() and not (destination / '.paquete.json').is_file():
        raise ValueError('La carpeta de salida ya existe y no es un paquete generado. No se modificó.')
    code_files = ('app.py', 'ui_tablero.py', 'consultas_tablero.py', 'actualizar_planes.py',
                  'reporte_powerbi.json', 'ACTUALIZAR_DATOS.bat', 'preparar_repo_streamlit.py', 'PREPARAR_REPO.bat')
    with tempfile.TemporaryDirectory(prefix='.empaquetando-', dir=ROOT) as temporary:
        stage = Path(temporary).resolve() / DIRECTORIO
        stage.mkdir()
        for name in code_files:
            shutil.copy2(ROOT / name, stage / name)
        (stage / 'assets').mkdir()
        for name in ('tablero.css', 'comfamiliar.jpg'):
            shutil.copy2(ROOT / 'assets' / name, stage / 'assets' / name)
        app = (stage / 'app.py').read_text(encoding='utf-8')
        app = app.replace('import actualizar_planes as fuente', 'import modelo_consulta as fuente')
        app = app.replace("st.code('python actualizar_planes.py', language='powershell')",
                          "st.caption('Contacta al administrador para revisar el corte publicado.')")
        (stage / 'app.py').write_text(app, encoding='utf-8')
        queries = (stage / 'consultas_tablero.py').read_text(encoding='utf-8')
        queries = queries.replace('from actualizar_planes import ', 'from modelo_consulta import ')
        queries = queries.replace('No hay una carga guardada. Ejecuta python actualizar_planes.py en esta carpeta para cargar los datos.',
                                  'El corte de datos no está disponible. Contacta al administrador del tablero.')
        (stage / 'consultas_tablero.py').write_text(queries, encoding='utf-8')
        model_source = generar_modelo_consulta((ROOT / 'actualizar_planes.py').read_text(encoding='utf-8'))
        (stage / 'modelo_consulta.py').write_text(model_source, encoding='utf-8')
        (stage / '.streamlit').mkdir()
        config = configuracion_cloud((ROOT / '.streamlit/config.toml').read_text(encoding='utf-8'))
        (stage / '.streamlit/config.toml').write_text(config, encoding='utf-8')
        requirements = (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
        viewer = [line for line in requirements if not line.lower().startswith(('pyodbc', 'openpyxl'))]
        local = ['-r requirements.txt'] + [line for line in requirements if line.lower().startswith(('pyodbc', 'openpyxl'))]
        (stage / 'requirements.txt').write_text('\n'.join(viewer) + '\n', encoding='utf-8')
        (stage / 'requirements-local.txt').write_text('\n'.join(local) + '\n', encoding='utf-8')
        (stage / 'README.md').write_text(LEEME, encoding='utf-8')
        (stage / '.gitignore').write_text(IGNORAR, encoding='utf-8')
        (stage / '.gitattributes').write_text('*.parquet -text\n*.py text eol=lf\n*.css text eol=lf\n*.bat text eol=crlf\n', encoding='utf-8')
        (stage / 'ABRIR_TABLERO.bat').write_text('@echo off\ncd /d "%~dp0"\npython -m streamlit run app.py --server.address=127.0.0.1\npause\n', encoding='ascii')
        for relative in manifest['tablas'].values():
            source = (ROOT / 'modelo_powerbi' / relative).resolve()
            if not source.is_relative_to((ROOT / 'modelo_powerbi').resolve()) or not source.is_file():
                raise ValueError('El corte contiene una ruta inválida o un archivo ausente.')
            target = (stage / 'modelo_powerbi' / relative).resolve()
            if not target.is_relative_to(stage):
                raise ValueError('Ruta de salida de tabla inválida.')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
                raise ValueError('La copia de una tabla no coincide con el original.')
        (stage / 'modelo_powerbi/actual.json').write_bytes(original_pointer)
        for name in ('app.py', 'ui_tablero.py', 'consultas_tablero.py'):
            compile((stage / name).read_text(encoding='utf-8'), name, 'exec')
        files = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in stage.rglob('*') if p.is_file()}
        metadata = {'version_datos': manifest['version'], 'corte_utc': manifest['actualizado_utc'],
                    'generado_utc': datetime.now(timezone.utc).isoformat(), 'tablas': 15,
                    'datos_corporativos_reales': True, 'archivos_sha256': files}
        (stage / '.paquete.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        ready_zip = Path(temporary) / ZIP
        with zipfile.ZipFile(ready_zip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(stage.rglob('*')):
                if file.is_file():
                    archive.write(file, file.relative_to(stage).as_posix())
        if pointer.read_bytes() != original_pointer:
            raise ValueError('El corte cambió durante la preparación. Se conserva el paquete anterior; vuelve a ejecutar.')
        if destination.exists():
            backup = (ROOT / '.paquetes_anteriores' / uuid.uuid4().hex).resolve()
            if not backup.is_relative_to(ROOT):
                raise ValueError('Ruta de respaldo inválida.')
            backup.parent.mkdir(exist_ok=True)
            os.replace(destination, backup)
            try:
                os.replace(stage, destination)
            except BaseException:
                os.replace(backup, destination)
                raise
        else:
            os.replace(stage, destination)
        os.replace(ready_zip, ROOT / ZIP)
    print(f'Paquete listo: {destination}')
    print(f'ZIP listo: {ROOT / ZIP}')
    print(f'Corte: {manifest["version"]}; 15 tablas; {len(files) + 1} archivos; {(ROOT / ZIP).stat().st_size / 1048576:.2f} MiB.')
    return destination


if __name__ == '__main__':
    crear_paquete()
