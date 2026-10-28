# Preparación del servicio de actualización

## Qué está implementado y qué falta

`servicio_actualizacion.py` recibe solicitudes autenticadas, admite un trabajo a
la vez, evita repetir una misma solicitud, abre el ingreso local de credenciales
y reutiliza el incremental existente. No acepta credenciales IBM i por HTTP ni
ofrece reconstrucción completa. Exige una carga base válida.

El operador debe estar presente en una sesión Windows con escritorio para ver
la ventana local. Este servicio no está preparado para ejecutarse sin escritorio
como un servicio Windows desatendido. Las credenciales se usan temporalmente en
memoria; eliminar referencias no garantiza su borrado físico inmediato en Python.

No se ha arrancado una extracción real ni publicado cambios remotos como parte
de estas pruebas. El servicio no está desplegado. Falta configurar administradores,
proxy HTTPS, clave del servicio y permiso de publicación en el repositorio privado.

## Preparar en la PC corporativa

Use el proyecto original con el Excel, los Parquet y el DSN `salud` ya instalados.
Desde una terminal en esta carpeta:

```powershell
python servicio_actualizacion.py --administrador SU-CUENTA@comfamiliar.com --repo sebasllano26-oss/tablero-mando --rama main
```

Repita `--administrador` para otras cuentas aprobadas. La clave del servicio y el
token de GitHub se ingresan interactivamente, sin eco ni guardado en archivos o
argumentos. Use una clave aleatoria de al menos 32 caracteres para el servicio.
En GitHub prefiera un token de acceso limitado a ese repositorio con permiso de
escritura en **Contents**, vencimiento y el mínimo alcance permitido.

La rama `main` es un ejemplo: confirme que sea la misma rama desplegada antes de
iniciar el servicio. El repositorio debe existir y contener el nuevo paquete.

El proceso escucha solo en **127.0.0.1:8765**. No lo exponga directamente a Internet.
Sistemas debe preparar un proxy HTTPS corporativo que permita a la app acceder a
ese backend, conserve el encabezado Authorization, limite el tamaño de solicitud,
las conexiones y la frecuencia, y no registre encabezados de autorización. Esta
configuración externa no se ha creado ni se ha cambiado la red de la PC.

Sin `--repo`, el proceso prepara el paquete pero no publica: el estado es
`preparado`. No equivale a que el tablero de nube se haya actualizado.

## Configurar el panel de nube

En los Secrets de Streamlit, además del ingreso de Google:

```toml
[servicio_actualizacion]
url = "https://URL-CORPORATIVA-PROVISTA-POR-SISTEMAS"
token = "MISMA_CLAVE_DEL_SERVICIO_CONFIGURADA_SOLO_EN_SECRETS"
```

En `[acceso]`, complete `administradores = ["SU-CUENTA@comfamiliar.com"]`.
La misma cuenta debe figurar en los argumentos del servicio. Estas claves son
del servicio y de publicación; **no son credenciales de IBM i**. No van en GitHub.
El cliente rechaza HTTP y redirecciones para no reenviar la clave a otro servidor.

Abra el panel «Actualizar información» con la cuenta administradora:

1. Pulse **Solicitar actualización**. El servicio abre la ventana de credenciales
   en la PC corporativa; sin respuesta del operador no realiza la extracción.
2. El incremental consulta solo la ventana abierta y publica localmente las 15 tablas.
3. Se prepara un paquete coherente. El publicador verifica que GitHub sea privado
   y publica únicamente las 15 tablas y `modelo_powerbi/actual.json` en un commit.
4. **Consultar estado** informa si fue preparado, publicado o si falló.
   `publicado` significa que GitHub recibió el commit; Streamlit aún debe desplegarlo.

El publicador mantiene el código remoto y los archivos de versiones anteriores.
Solo cambia el árbol de datos y el puntero en conjunto, con avance de rama sin
`force`. Un conflicto concurrente o error anterior al cambio de referencia deja
visible el corte remoto anterior. Una actualización local exitosa seguida de un
fallo de publicación puede dejar una versión nueva local mientras la nube conserva
la anterior; no se presenta ese caso como una publicación exitosa.

El historial de GitHub contiene versiones anteriores de los datos. El repositorio
debe seguir privado. `.paquete.json` describe el ZIP generado localmente; el
publicador de datos no reescribe ese inventario de código remoto.

## Contrato y límites

- `POST /actualizaciones`: JSON con `id` hexadecimal de 32 caracteres y `actor`.
- `GET /actualizaciones/{id}`: estado y métricas, sin excepciones privadas.
- Ambas rutas exigen `Authorization: Bearer ...`. No admiten parámetros SQL.
- La clave autentica al servidor Streamlit; el backend confía en que ese servidor
  comprobó la identidad Google. También valida el correo contra su lista local.
- La lista de trabajos es temporal: reiniciar el proceso borra sus estados y las
  claves en memoria. Antes de reintentar tras un reinicio, revise el corte y el
  último commit. Los resultados no constituyen un registro de auditoría permanente.
- El candado del incremental impide dos extracciones simultáneas, incluso si se
  ejecuta también el actualizador por consola.

Los permisos de lectura en IBM i, de administración del panel y de publicación
en GitHub son independientes. La reconstrucción histórica excepcional conserva
su comando local explícito `python actualizar_planes.py --reconstruir`.
