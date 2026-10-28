"""Ingreso OIDC; la autorización se comprueba antes de leer el corte.

Sin [acceso] ni [auth], el acceso lo controla el alojamiento (invitaciones de
Streamlit) en la vista previa local. El paquete de nube activa obligatorio=True.
"""
import time
import math

import streamlit as st


def identidad_autorizada(claims, config, now=None):
    """Autorizar Google Workspace por hd, o listas explícitas en el modo local."""
    expiry = claims.get('exp')
    if expiry is not None:
        try:
            if not math.isfinite(float(expiry)) or float(expiry) <= (time.time() if now is None else now):
                return False
        except (TypeError, ValueError):
            return False
    domain = config.get('dominio_google')
    if domain is not None:
        # hd es la pertenencia verificada por Google Workspace. El parámetro
        # hd de la pantalla de Google es solo una sugerencia, no autorización.
        email = claims.get('email')
        return (isinstance(domain, str) and bool(domain.strip())
                and claims.get('iss') in {'https://accounts.google.com', 'accounts.google.com'}
                and claims.get('email_verified') is True
                and isinstance(claims.get('hd'), str)
                and claims['hd'].casefold() == domain.strip().casefold()
                and isinstance(email, str) and email.count('@') == 1
                and email.rsplit('@', 1)[1].casefold() == domain.strip().casefold())
    subject = claims.get('sub')
    subjects = config.get('usuarios', [])
    if isinstance(subjects, list) and isinstance(subject, str) and subject and subject in subjects:
        return True
    email = claims.get('email')
    emails = config.get('correos_verificados', [])
    return (claims.get('email_verified') is True and isinstance(email, str) and bool(email.strip())
            and isinstance(emails, list) and email.strip().casefold() in
            {value.strip().casefold() for value in emails if isinstance(value, str)})


def exigir_acceso(obligatorio=False, dominio_requerido=None):
    try:
        config = dict(st.secrets.get('acceso', {}))
        auth = dict(st.secrets.get('auth', {}))
    except FileNotFoundError:
        config, auth = {}, {}
    if not config and not auth:
        if obligatorio:
            from ui_tablero import marca_acceso
            with st.container(key='ingreso_corporativo'):
                marca_acceso()
                st.title('Acceso corporativo')
                st.write('Una visión compartida. Información para nuestra organización.')
                st.info('El ingreso de Google Workspace está pendiente de configuración. El tablero permanece protegido.', icon=':material/lock:')
            st.stop()
        return False
    if config.get('modo') != 'oidc':
        st.error('El ingreso del tablero necesita configuración del administrador.')
        st.stop()
    if dominio_requerido and config.get('dominio_google') != dominio_requerido:
        st.error('Configure el dominio corporativo autorizado para habilitar este tablero.')
        st.stop()
    provider = config.get('proveedor')
    connection = auth.get(provider, {}) if provider else auth
    required = ('client_id', 'client_secret', 'server_metadata_url')
    if not all(connection.get(key) for key in required) or not all(auth.get(key) for key in ('cookie_secret', 'redirect_uri')):
        st.error('El ingreso corporativo todavía no está configurado. Contacta al administrador.')
        st.stop()
    if config.get('dominio_google') is not None and connection.get('server_metadata_url') != 'https://accounts.google.com/.well-known/openid-configuration':
        st.error('El dominio corporativo debe verificarse mediante el proveedor oficial de Google.')
        st.stop()
    if not st.user.is_logged_in:
        from ui_tablero import marca_acceso
        with st.container(key='ingreso_corporativo'):
            marca_acceso()
            st.title('Acceso corporativo')
            st.write('Una visión compartida. Información para nuestra organización.')
            st.info('Ingresa con una cuenta autorizada para consultar los resultados institucionales.', icon=':material/lock:')
            if st.button('Ingresar con Google' if config.get('dominio_google') else 'Ingresar con mi cuenta', icon=':material/login:', type='primary'):
                try:
                    st.login(provider)
                except Exception:
                    st.error('No se pudo iniciar el ingreso. Contacta al administrador para revisar la conexión de identidad.')
        st.stop()
    if not identidad_autorizada(dict(st.user), config):
        st.title('Acceso restringido')
        st.warning('Tu cuenta ha ingresado, pero no tiene autorización vigente para este tablero.')
        # sub identifica a esta cuenta en este cliente OIDC; no es una contraseña.
        if st.user.get('sub'):
            with st.expander('Mi identificador para solicitar acceso'):
                st.code(str(st.user['sub']), language=None)
        st.button('Salir de esta sesión', on_click=st.logout)
        st.stop()
    return True


def mostrar_sesion():
    st.caption('SESIÓN AUTORIZADA')
    st.text(st.user.get('name') or 'Usuario autorizado')
    st.button('Cerrar sesión', icon=':material/logout:', on_click=st.logout, width='stretch')
