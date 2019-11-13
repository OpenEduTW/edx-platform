# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from django.conf import settings
from django.contrib.auth import authenticate, login as django_login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from student.models import LoginFailures
from openedx.core.djangoapps.user_authn.cookies import set_logged_in_cookies
from openedx.core.djangoapps.user_authn.exceptions import AuthFailedError
import openedx.core.djangoapps.external_auth.views
from openedx.core.djangoapps.external_auth.models import ExternalAuthMap
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from student.views import send_reactivation_email_for_user
from track import segment
from util.json_request import JsonResponse

# guangyaw modify for nid
import json
import re
import requests
from school_id_login.models import Xschools
from school_id_login.models import Xsuser
from django.contrib import auth
from django.http import HttpResponse
from edxmako.shortcuts import render_to_response

log = logging.getLogger("edx.student")
AUDIT_LOG = logging.getLogger("audit")


def _check_shib_redirect(user):
    """
    See if the user has a linked shibboleth account, if so, redirect the user to shib-login.
    This behavior is pretty much like what gmail does for shibboleth.  Try entering some @stanford.edu
    address into the Gmail login.
    """
    if settings.FEATURES.get('AUTH_USE_SHIB') and user:
        try:
            eamap = ExternalAuthMap.objects.get(user=user)
            if eamap.external_domain.startswith(openedx.core.djangoapps.external_auth.views.SHIBBOLETH_DOMAIN_PREFIX):
                raise AuthFailedError('', redirect=reverse('shib-login'))
        except ExternalAuthMap.DoesNotExist:
            # This is actually the common case, logging in user without external linked login
            AUDIT_LOG.info(u"User %s w/o external auth attempting login", user)


def _check_excessive_login_attempts(user):
    """
    See if account has been locked out due to excessive login failures
    """
    if user and LoginFailures.is_feature_enabled():
        if LoginFailures.is_user_locked_out(user):
            raise AuthFailedError(_('This account has been temporarily locked due '
                                    'to excessive login failures. Try again later.'))


def _generate_not_activated_message(user):
    """
    Generates the message displayed on the sign-in screen when a learner attempts to access the
    system with an inactive account.
    """

    support_url = configuration_helpers.get_value(
        'SUPPORT_SITE_LINK',
        settings.SUPPORT_SITE_LINK
    )

    platform_name = configuration_helpers.get_value(
        'PLATFORM_NAME',
        settings.PLATFORM_NAME
    )

    not_activated_msg_template = _('In order to sign in, you need to activate your account.<br /><br />'
                                   'We just sent an activation link to <strong>{email}</strong>.  If '
                                   'you do not receive an email, check your spam folders or '
                                   '<a href="{support_url}">contact {platform} Support</a>.')

    not_activated_message = not_activated_msg_template.format(
        email=user.email,
        support_url=support_url,
        platform=platform_name
    )

    return not_activated_message


def _log_and_raise_inactive_user_auth_error(unauthenticated_user):
    """
    Depending on Django version we can get here a couple of ways, but this takes care of logging an auth attempt
    by an inactive user, re-sending the activation email, and raising an error with the correct message.
    """
    if settings.FEATURES['SQUELCH_PII_IN_LOGS']:
        AUDIT_LOG.warning(
            u"Login failed - Account not active for user.id: {0}, resending activation".format(
                unauthenticated_user.id)
        )
    else:
        AUDIT_LOG.warning(u"Login failed - Account not active for user {0}, resending activation".format(
            unauthenticated_user.username)
        )

    send_reactivation_email_for_user(unauthenticated_user)
    raise AuthFailedError(_generate_not_activated_message(unauthenticated_user))


def _handle_failed_authentication(user, authenticated_user):
    """
    Handles updating the failed login count, inactive user notifications, and logging failed authentications.
    """
    if user:
        if LoginFailures.is_feature_enabled():
            LoginFailures.increment_lockout_counter(user)

        if authenticated_user and not user.is_active:
            _log_and_raise_inactive_user_auth_error(user)

        # if we didn't find this username earlier, the account for this email
        # doesn't exist, and doesn't have a corresponding password
        if settings.FEATURES['SQUELCH_PII_IN_LOGS']:
            loggable_id = user.id if user else "<unknown>"
            AUDIT_LOG.warning(u"Login failed - password for user.id: {0} is invalid".format(loggable_id))
        else:
            AUDIT_LOG.warning(u"Login failed - password for {0} is invalid".format(user.email))

    raise AuthFailedError(_('Email or password is incorrect.'))


def _track_user_login(user, request):
    """
    Sends a tracking event for a successful login.
    """
    segment.identify(
        user.id,
        {
            'email': request.POST.get('email'),
            'username': user.username
        },
        {
            # Disable MailChimp because we don't want to update the user's email
            # and username in MailChimp on every page load. We only need to capture
            # this data on registration/activation.
            'MailChimp': False
        }
    )
    segment.track(
        user.id,
        "edx.bi.user.account.authenticated",
        {
            'category': "conversion",
            'label': request.POST.get('course_id'),
            'provider': None
        },
    )


# guangyaw modify for nid
def _handle_nid_authentication_and_login(user, request):
    """
    Handles clearing the failed login counter, login tracking, and setting session timeout.
    """
    if LoginFailures.is_feature_enabled():
        LoginFailures.clear_lockout_counter(user)

    _track_user_login(user, request)

    try:
        django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        request.session.set_expiry(604800 * 4)
        log.debug("Setting user session expiry to 4 weeks")
    except Exception as exc:  # pylint: disable=broad-except
        AUDIT_LOG.critical("Login failed - Could not create session. Is memcached running?")
        log.critical("Login failed - Could not create session. Is memcached running?")
        log.exception(exc)
        raise


@ensure_csrf_cookie
def unidlink(request):
    if request.user.is_authenticated:
        profile = Xsuser.objects.get(user=request.user, ask_nid_link='already_bind')
        if profile:
            profile.nid_linked = None
            profile.ask_nid_link = None
            profile.save()
            auth.logout(request)
        else:
            raise AuthFailedError(_('There is no FCU_NID bind'))

    redirect_url = "https://www.openedu.tw"
    return redirect(redirect_url)


@ensure_csrf_cookie
def signin_nid(request):
    xclient_id = Xschools.objects.get(xschool_id='FCU').xschool_client
    xclient_url = Xschools.objects.get(xschool_id='FCU').return_uri
    return redirect(
        'https://opendata.fcu.edu.tw/fcuOauth/Auth.aspx?client_id=' + xclient_id + '&client_url=' + xclient_url)


@csrf_exempt
def return_nid(request):
    if request.method == 'POST':
        if int(request.POST['status']) == 200:
            xclient_id = Xschools.objects.get(xschool_id='FCU').xschool_client
            getinfourl = 'https://opendata.fcu.edu.tw/fcuapi/api/GetUserInfo'
            sdata = {"client_id": xclient_id, "user_code": request.POST['user_code']}
            r = requests.get(getinfourl, params=sdata)
            if int(r.status_code) == 200:
                resp = json.loads(r.text)
                data = resp['UserInfo'][0]
                fresp = {
                    'id': data['id'].strip(),
                    'name': data['name'],
                    # 'type' : data['type']
                }
                if request.user.is_authenticated:
                    profile, created = Xsuser.objects.get_or_create(user=request.user)
                    if profile.ask_nid_link == 'already_bind':
                        AUDIT_LOG.info(
                            u"Link failed - The openedu account: {idname} is already linked with a ID  ".format(
                                idname=request.user.username)
                        )
                        context = {
                            'error_title': 'Error page !!',
                            'error_msg1': "此中華開放教育平台帳號已與其他帳號綁定"
                        }

                        response = render_to_response('school_id_login/xerror_auth.html', context)
                        return response
                    else:
                        profile.ask_nid_link = 'already_bind'
                        profile.nid_linked = "FCU_" + fresp['id']
                        profile.save()
                        redirect_url = reverse('account_settings')
                    return redirect(redirect_url)
                else:
                    try:
                        puser = Xsuser.objects.get(nid_linked="FCU_" + fresp['id'])
                    except Xsuser.DoesNotExist:
                        AUDIT_LOG.info(
                            u"Login failed - No user bind to the ID {idname} ".format(idname=fresp['id'])
                        )
                        context = {
                            'error_title': 'Error page !!',
                            'error_msg1': "成功登入NID,但此NID帳號未與中華開放教育平台帳號綁定",
                            'error_msg2': "請先登入中華開放教育平台或註冊新帳號進行校園帳號綁定"
                        }

                        response = render_to_response('school_id_login/xerror_auth.html', context)
                        return response
                    else:
                        if puser.ask_nid_link == 'already_bind':
                            email_user = puser.user
                            _check_shib_redirect(email_user)
                            _check_excessive_login_attempts(email_user)

                            possibly_authenticated_user = email_user

                            if possibly_authenticated_user is None or not possibly_authenticated_user.is_active:
                                _handle_failed_authentication(email_user)

                            _handle_nid_authentication_and_login(possibly_authenticated_user, request)

                            # redirect_url = None  # The AJAX method calling should know the default destination upon success
                            redirect_url = reverse('dashboard')

                            response = JsonResponse({
                                'success': True,
                                'redirect_url': redirect_url,
                            })

                            # Ensure that the external marketing site can
                            # detect that the user is logged in.
                            set_logged_in_cookies(request, response, possibly_authenticated_user)
                            return redirect(redirect_url)
                        else:
                            context = {
                                'error_title': 'Error page !!',
                                'error_msg1': "此帳號未綁定校園ID"
                            }

                            response = render_to_response('school_id_login/xerror_auth.html', context)
                            return response
            else:
                context = {
                    'error_title': 'Error page !!',
                    'error_msg1': "查詢使用者資訊失敗"
                }
                response = render_to_response('school_id_login/xerror_auth.html', context)
                return response
    else:
        if request.user.is_authenticated:
            redirect_url = reverse('dashboard')
            return redirect(redirect_url)
        else:
            context = {
                'error_title': 'Error page !!',
                'error_msg1': "錯誤要求"
            }
            response = render_to_response('school_id_login/xerror_auth.html', context)
            return response

def check_stu_id_school(request):
    if request.method == 'GET':
        try:
            profile = Xsuser.objects.get(user__username__iexact=request.GET['username'], ask_nid_link='already_bind')
        except Xsuser.DoesNotExist:
            return JsonResponse({
                'status': 'False',
                'message': "No school id bind to this account"
            })
        else:
            if request.GET['check_school'] == 'FCU':
                if re.match("FCU_+w*", profile.nid_linked):
                    return JsonResponse({
                        'status': 'True',
                        'message': "From FCU"
                    })
                else:
                    return JsonResponse({
                        'status': 'False',
                        'message': "From Other school"
                    })
            else:
                return JsonResponse({
                    'status': 'False',
                    'message': "No match with target school"
                })
