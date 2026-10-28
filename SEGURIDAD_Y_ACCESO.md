# Google Workspace y acceso al tablero

Aplicación: https://tablero-mando.streamlit.app/
Repositorio indicado por el propietario como privado:
https://github.com/sebasllano26-oss/tablero-mando

## Comportamiento del paquete para nube

El `app.py` generado en `repo_streamlit` exige ingreso corporativo **antes de leer
la definición del reporte o sus datos**. Si faltan los Secrets, muestra una
pantalla de acceso pendiente y bloquea el tablero. No hay contraseñas propias.

Google valida la identidad mediante OIDC (`st.login`). La app exige simultáneamente:

- Emisor oficial de Google.
- Correo verificado y perteneciente exactamente a `comfamiliar.com`.
- Atributo firmado `hd = comfamiliar.com`, que identifica una cuenta de Google
  Workspace administrada por ese dominio. Un correo con ese texto, sin `hd`, no basta.
- Identidad no vencida, cuando el proveedor entrega `exp`.

El parámetro de ingreso `hd` solo orienta la pantalla de Google: la autorización
usa los atributos firmados de la identidad. No se admiten Gmail personales,
dominios parecidos ni otro proveedor. La aplicación revisa la autorización en cada
ejecución; esto no retira datos que un usuario autorizado ya haya descargado.

El proyecto original en esta PC mantiene una vista previa local sin ingreso si
no hay Secrets, bajo el servidor existente en `127.0.0.1`. **Publique el contenido
generado de `repo_streamlit`, que activa la exigencia de ingreso**, no el `app.py`
de vista previa de la raíz.

## Activar Google: pasos del administrador

1. En Google Cloud Console cree o elija un proyecto de la organización. Configure
   Google Auth Platform y la audiencia interna de Google Workspace si su
   organización lo permite. Solo se necesitan identidad, perfil y correo.
2. Cree un cliente OAuth de tipo **Aplicación web**. Registre exactamente como URI
   de redirección autorizada:
   `https://tablero-mando.streamlit.app/oauth2callback`.
3. En Streamlit, **Manage app → Settings → Secrets**, escriba la configuración que
   sigue. Los valores reales se ingresan allí, nunca en GitHub ni en el chat.

```toml
[acceso]
modo = "oidc"
proveedor = "google"
dominio_google = "comfamiliar.com"
administradores = []

[auth]
redirect_uri = "https://tablero-mando.streamlit.app/oauth2callback"
cookie_secret = "GENERAR_UN_SECRETO_ALEATORIO_LARGO"

[auth.google]
client_id = "COPIAR_DEL_CLIENTE_OAUTH_EN_GOOGLE"
client_secret = "CONFIGURAR_SOLO_EN_STREAMLIT_SECRETS"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
client_kwargs = { hd = "comfamiliar.com", prompt = "select_account" }
```

4. Guarde y reinicie el despliegue si Streamlit lo solicita. El paquete incluye
   `streamlit[auth]==1.58.0`; no se han reinstalado dependencias en esta PC.
5. Pruebe en ventana privada: primero sin sesión, luego con Gmail personal y con
   una cuenta corporativa. Solo la última debe abrir los datos. Compruebe también
   `Cerrar sesión` y un enlace directo como `?vista=areas`.

La sesión de la app es distinta de la sesión global de Google. `Cerrar sesión`
no desconecta la cuenta de otros servicios de Google.

No se ha probado el ingreso real al proveedor: falta crear/configurar ese cliente
y sus Secrets. Las pruebas locales simulan identidades para verificar permisos y
rechazos. No se ha modificado la app remota ni el repositorio remoto desde esta PC.

## Repositorio privado y permisos

El paquete contiene Parquet reales. Mantenga privado el repositorio: un login no
protege archivos de un repositorio público. Quien tenga permiso de escritura en
GitHub puede reemplazar código y datos aunque no tenga acceso a IBM i. Limite esos
permisos. El visor no necesita contraseñas de IBM i.

La privacidad de la app en Streamlit es un ajuste adicional. Puede mantener las
invitaciones privadas como segunda barrera; entonces el visitante necesita tanto
invitación en Streamlit como cuenta corporativa en el login. No se cambian esos
ajustes remotos desde el paquete.

## Panel de actualización

Se conserva separado de la consulta y solo aparece a correos expresamente incluidos
en `administradores`, por ejemplo `["su-cuenta@comfamiliar.com"]`. No se ha supuesto
qué cuentas deben tener ese permiso: la lista inicial está vacía.

El panel pide al servicio corporativo una actualización incremental. **El usuario
eligió ingresar las credenciales en una ventana local del servicio corporativo.**
El tablero de nube nunca recibe usuario ni contraseña de IBM i. El operador debe
estar presente en la PC corporativa; este flujo no es desatendido.

El servicio está preparado y probado localmente con operaciones simuladas. Falta
que Sistemas le proporcione un acceso HTTPS corporativo y que se configuren sus
claves. No se ha desplegado ni abierto ningún puerto de la red. Sin configuración,
el panel informa que está pendiente y no simula una actualización exitosa.

Consulte **SERVICIO_CORPORATIVO.md** para configurar el servicio, la publicación
en un commit y el panel. Mientras tanto sigue funcionando el flujo local:
`ACTUALIZAR_DATOS.bat` → `PREPARAR_REPO.bat` → publicar el paquete completo en GitHub.

Referencias oficiales:
- https://docs.streamlit.io/develop/concepts/connections/authentication
- https://developers.google.com/identity/openid-connect/openid-connect
- https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
