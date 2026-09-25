"""Explicitly enabled, credential-protected browser login for one development account.

This issuer never claims SSO or human participation. A server-configured actor and
delegation reference follow the signed session into exact bundle confirmation.
"""
import html
import os
import secrets
import time
from urllib.parse import parse_qs, urlsplit

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .auth import (AuthError, AuthIdentity, SESSION_COOKIE_NAME, allowed_employee_check,
    auth_mode, create_session_token, dev_identity, session_secret)

STATE_COOKIE = 'boi_dev_login_state'


def enabled():
    return auth_mode() == 'dev' and os.getenv('BOI_DEV_BROWSER_ENABLED') == 'true'


def configured_identity():
    if not enabled():
        raise AuthError(403, 'development browser login is disabled')
    employee = os.getenv('BOI_DEV_BROWSER_EMPLOYEE_ID', '')
    credential = os.getenv('BOI_DEV_BROWSER_KEY', '')
    actor = os.getenv('BOI_DEV_BROWSER_ACTOR', '')
    delegation = os.getenv('BOI_DEV_BROWSER_DELEGATION_REF', '')
    if (not employee or len(employee) > 128 or len(credential) < 32
            or bool(actor) != bool(delegation) or len(actor) > 160 or len(delegation) > 240):
        raise AuthError(503, 'development browser login is not configured')
    base = dev_identity(employee)
    allowed_roles = {'boi.viewer', 'boi.editor'}
    # Execution requires both a current role binding and an explicit server-side
    # opt-in for this development issuer. Never inherit admin or other roles.
    if os.getenv('BOI_DEV_BROWSER_ACTION_EXECUTION_ENABLED') == 'true':
        allowed_roles.add('boi.action_invoker')
    identity = AuthIdentity(employee_id=employee, display_name=base.display_name,
        email=base.email, roles=sorted(set(base.roles) & allowed_roles),
        teams=[], auth_source='dev_session', session_actor=actor, delegation_ref=delegation)
    allowed_employee_check(identity)
    return identity


def safe_destination(value):
    return value if (value.startswith('/') and not value.startswith('//')
        and '\\' not in value and not any(ord(c) < 32 for c in value)) else '/knowledge'


def _origin(request):
    try:
        actual, supplied = urlsplit(str(request.url)), urlsplit(request.headers.get('origin', ''))
        def key(url):
            return url.scheme, url.hostname, url.port or (443 if url.scheme == 'https' else 80)
        if (key(actual) == key(supplied) and not any((supplied.path, supplied.query,
                supplied.fragment, supplied.username, supplied.password))
                and request.headers.get('sec-fetch-site') != 'cross-site'):
            return
    except ValueError:
        pass
    raise AuthError(403, 'development login origin denied')


def register_dev_browser_login(app, *, remember_identity=lambda identity: identity):
    @app.get('/auth/dev/login', response_class=HTMLResponse)
    async def login_form(next: str = '/knowledge'):
        try:
            identity = configured_identity()
            nonce = secrets.token_urlsafe(32)
            state = jwt.encode({'aud':'boi-dev-login', 'nonce':nonce, 'next':safe_destination(next),
                'iat':int(time.time()), 'exp':int(time.time())+600}, session_secret(), algorithm='HS256')
        except AuthError as exc:
            raise HTTPException(exc.status_code, exc.detail) from None
        esc = html.escape
        actor = (f'<p>수행 주체: {esc(identity.session_actor)} · 사용자 위임에 따른 대리 수행</p>'
            if identity.delegation_ref else '<p>개발 계정으로 수행한 작업으로 기록됩니다.</p>')
        response = HTMLResponse('<!doctype html><html lang="ko"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>개발 계정 로그인 · BoI Wiki</title>'
            '<body><main><h1>개발 계정 로그인</h1><p>이 인스턴스에 설정된 개발 계정 전용입니다. 운영 SSO 인증이 아닙니다.</p>'
            f'<p>계정: {esc(identity.display_name)} ({esc(identity.employee_id)})</p>{actor}'
            '<form method="post" action="/auth/dev/login">'
            f'<input type="hidden" name="state" value="{esc(nonce)}">'
            '<label>개발 접속 키 <input name="key" type="password" autocomplete="current-password" required maxlength="256"></label>'
            '<button type="submit">개발 계정으로 로그인</button></form></main></body></html>',
            headers={'Cache-Control':'no-store', 'Referrer-Policy':'same-origin',
                'Content-Security-Policy':"default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        response.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True,
            secure=os.getenv('BOI_COOKIE_SECURE', 'false').lower() in {'true','1','yes'}, samesite='strict')
        return response

    @app.post('/auth/dev/login')
    async def login(request: Request):
        try:
            identity = configured_identity()
            _origin(request)
            if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                raise AuthError(415, 'development login form required')
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 4096:
                    raise AuthError(413, 'development login form too large')
                raw.extend(chunk)
            form = parse_qs(raw.decode('utf-8'), max_num_fields=3)
            claims = jwt.decode(request.cookies.get(STATE_COOKIE, ''), session_secret(),
                algorithms=['HS256'], audience='boi-dev-login', options={'require':['exp','iat','nonce','next']})
            if (len(form.get('state', [])) != 1 or len(form.get('key', [])) != 1
                    or not secrets.compare_digest(form['state'][0].encode(), claims['nonce'].encode())
                    or not secrets.compare_digest(form['key'][0].encode(), os.environ['BOI_DEV_BROWSER_KEY'].encode())):
                raise AuthError(401, 'development login credentials or state invalid')
            response = RedirectResponse(safe_destination(claims['next']), status_code=303,
                headers={'Cache-Control':'no-store'})
            response.set_cookie(SESSION_COOKIE_NAME, create_session_token(identity),
                max_age=int(os.getenv('BOI_SESSION_TTL_SECONDS', '28800')), httponly=True,
                secure=os.getenv('BOI_COOKIE_SECURE', 'false').lower() in {'true','1','yes'}, samesite='lax')
            response.delete_cookie(STATE_COOKIE)
            remember_identity(identity)
            return response
        except AuthError as exc:
            raise HTTPException(exc.status_code, exc.detail) from None
        except (jwt.PyJWTError, ValueError, UnicodeError):
            raise HTTPException(401, 'development login credentials or state invalid') from None
