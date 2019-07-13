# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from django.contrib.auth import authenticate, load_backend, login as django_login, logout
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from student.models import (
    CourseAccessRole,
    CourseEnrollment,
    LoginFailures,
    PasswordHistory,
    Registration,
    UserProfile,
    anonymous_id_for_user,
    create_comments_service_user
)
from student.cookies import delete_logged_in_cookies, set_logged_in_cookies
from student.views.login import _check_excessive_login_attempts, _check_forced_password_reset, _check_shib_redirect, _handle_failed_authentication, _track_user_login, AuthFailedError
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
        if request.POST.get('remember') == 'true':
            request.session.set_expiry(604800)
            log.debug("Setting user session to never expire")
        else:
            request.session.set_expiry(0)
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
                            _check_forced_password_reset(email_user)

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