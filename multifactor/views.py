from django.shortcuts import redirect
from django.http import HttpResponse
from django.conf import settings
from django.utils.module_loading import import_string
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.html import format_html
from django.urls import reverse

from .models import UserKey, KEY_CHOICES
from .common import render, method_url
from .app_settings import mf_settings
from .decorators import multifactor_protected
from .helpers import is_mfa


@login_required
def index(request):
    authed = is_mfa(request)
    methods = [
        (f"multifactor:{value.lower()}_start", label)
        for value, label in KEY_CHOICES
    ]

    if methods and not authed:
        messages.warning(request, format_html(
            'You will not be able to change these settings or add new '
            'factors until until you <a href="{}">authenticate</a> with '
            'one of your existing secondary factors.',
            reverse('multifactor:authenticate')
        ))

    return render(request, "multifactor/home.html", {
        "keys": UserKey.objects.filter(user=request.user),
        "available_methods": methods,
        "authed": authed,
    })


@login_required
def authenticate(request):
    keys = UserKey.objects.filter(user=request.user, enabled=True)
    methods = list(set([k.key_type for k in keys]))

    if not len(keys):
        messages.warning(request, 'You have no keys to authenticate with. Please add one (or more).')
        return redirect('multifactor:home')

    request.session["multifactor_methods"] = methods
    if len(methods) == 1:
        return redirect(method_url(methods[0]))

    method_names = dict(KEY_CHOICES)

    return render(request, 'multifactor/authenticate.html', {
        'methods': [
            (method_url(method), method_names[method])
            for method in methods
        ]
    })


@login_required
def reset_cookie(request):
    del request.session['multifactor']
    return redirect(settings.LOGIN_URL)


@login_required
@multifactor_protected()
def del_key(request, key_id):
    try:
        key = UserKey.objects.get(user=request.user, pk=key_id)
        key.delete()
        messages.info(request, f'{key.get_key_type_display()} has been deleted.')

    except UserKey.DoesNotExist:
        messages.error(request, f'{key.get_key_type_display()} not found.')

    return redirect('multifactor:home')


@login_required
@multifactor_protected()
def toggle_key(request, key_id):
    try:
        key = UserKey.objects.get(user=request.user, pk=key_id)
        key.enabled = not key.enabled
        key.save()
        messages.info(request, f'{key.get_key_type_display()} has been {"enabled" if key.enabled else "disabled"}.')

    except UserKey.DoesNotExist:
        messages.error(request, f'{key.get_key_type_display()} not found.')

    return redirect('multifactor:home')
