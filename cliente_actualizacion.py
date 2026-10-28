"""Solicitud administrativa HTTPS; las credenciales ODBC nunca pasan por aquí."""
import json
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Evitar reenviar Authorization a otro servidor.


def pedir_servicio(config, ruta, payload=None):
    base = str(config.get('url', '')).rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Configure una URL HTTPS corporativa sin credenciales en la dirección.')
    identifier = ruta.rsplit('/', 1)[-1]
    if ruta != '/actualizaciones' and not (ruta.startswith('/actualizaciones/') and
            len(identifier) == 32 and all(c in '0123456789abcdef' for c in identifier)):
        raise ValueError('Ruta inválida.')
    token = config.get('token', '')
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError('Falta configurar la clave del servicio en Secrets.')
    request = Request(base + ruta, method='POST' if payload is not None else 'GET',
        data=json.dumps(payload).encode('utf-8') if payload is not None else None,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with build_opener(SinRedireccion).open(request, timeout=12) as response:
            body = response.read(65537)
            if len(body) > 65536:
                raise ValueError()
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError()
            return result
    except Exception:
        raise RuntimeError('El servicio corporativo no respondió correctamente. Revisa su estado con Sistemas.') from None


def puede_administrar(claims, acceso):
    from acceso_tablero import identidad_autorizada
    email, admins = claims.get('email'), acceso.get('administradores', [])
    return (identidad_autorizada(claims, acceso) and isinstance(email, str) and isinstance(admins, list)
            and email.casefold() in {v.strip().casefold() for v in admins if isinstance(v, str)})


def panel_administrativo():
    import uuid
    import streamlit as st
    if not st.user.is_logged_in or not puede_administrar(dict(st.user), dict(st.secrets.get('acceso', {}))):
        st.error('Esta sección requiere una cuenta administradora autorizada.')
        st.stop()
    st.title('Actualizar información')
    st.write('Solicita el nuevo corte al servicio corporativo y consulta el resultado de la publicación.')
    st.info('Las credenciales de IBM i se escriben en una ventana local del operador corporativo. '
            'No se solicitan ni almacenan en este tablero.', icon=':material/verified_user:')
    config = dict(st.secrets.get('servicio_actualizacion', {}))
    configured = bool(config.get('url') and config.get('token'))
    if not configured:
        st.warning('El servicio corporativo está pendiente de configuración. La consulta conserva el último corte publicado.')
    if st.button('Solicitar actualización', icon=':material/sync:', type='primary', disabled=not configured):
        identifier = st.session_state.setdefault('solicitud_actualizacion', uuid.uuid4().hex)
        try:
            result = pedir_servicio(config, '/actualizaciones', {'id': identifier, 'actor': st.user['email']})
            st.session_state.trabajo_actualizacion = result['id']
            st.session_state.pop('solicitud_actualizacion', None)
            st.success('Solicitud recibida. El operador debe ingresar las credenciales en su ventana local.')
        except (RuntimeError, ValueError, KeyError):
            st.error('No se confirmó la solicitud. Comprueba el servicio con Sistemas antes de reintentar.')
    identifier = st.session_state.get('trabajo_actualizacion')
    if configured and identifier:
        st.button('Consultar estado', icon=':material/refresh:')
        try:
            result = pedir_servicio(config, '/actualizaciones/' + identifier)
            labels = {'ejecutando': 'En curso; puede estar esperando al operador local', 'publicado': 'Corte publicado en GitHub',
                      'preparado': 'Corte preparado; pendiente de publicación', 'fallido': 'La actualización no se completó'}
            st.subheader(labels.get(result.get('estado'), 'Estado pendiente'))
            if result.get('estado') == 'publicado':
                st.success('GitHub recibió las 15 tablas. Streamlit debe terminar el despliegue antes de mostrar el corte nuevo.')
            elif result.get('estado') == 'fallido':
                st.warning('No se confirmó la publicación. El operador debe revisar el corte local y el último commit antes de reintentar.')
            if result.get('version'):
                st.text('Versión: ' + str(result['version']))
            if result.get('metricas'):
                st.json(result['metricas'])
        except (RuntimeError, ValueError):
            st.error('No se pudo consultar el estado. Revisa el servicio con Sistemas.')
