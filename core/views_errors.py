"""Branded error pages. 500 is rendered without database access so it works during outages."""
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader


def not_found(request, exception=None):
    return render(request, '404.html', status=404)


def forbidden(request, exception=None):
    return render(request, '403.html', status=403)


def server_error(request):
    return HttpResponse(loader.render_to_string('500.html'), status=500)
