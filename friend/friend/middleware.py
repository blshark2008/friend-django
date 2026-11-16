"""
Middleware to block common scanner/bot probe requests.

Blocks known paths used by automated security scanners
(WordPress, Spring Boot, Kubernetes, phpinfo, etc.)
and returns 403 instead of 404 to avoid revealing the framework.
"""

import re
import logging

logger = logging.getLogger('django.request')

# Paths commonly probed by automated scanners
SCANNER_PATHS = re.compile(
    r'^('
    r'wp-json/|'           # WordPress
    r'wp-login\.php|'      # WordPress login
    r'wp-admin/|'          # WordPress admin
    r'xmlrpc\.php|'        # WordPress XML-RPC
    r'wp-content/|'        # WordPress content
    r'wp-includes/|'       # WordPress includes
    r'wp-config\.php|'     # WordPress config
    r'actuator/|'          # Spring Boot Actuator
    r'api/v[0-9]+/namespaces/|'  # Kubernetes API
    r'phpinfo\.php|'       # PHP info
    r'phpinfo\(\)|'        # PHP info function call
    r'info\.php|'          # PHP info alternate
    r'api/config|'         # Generic API config probes
    r'/\.env|'             # Environment file probe
    r'/\.git/|'            # Git repo probe
    r'adminer\.php|'       # Adminer probe
    r'phpmyadmin/|'        # phpMyAdmin probe
    r'shell\.php|'         # Web shell probe
    r'cmd\.php|'           # Command execution probe
    r'eval\.php|'          # Eval probe
    r'c99\.php|'           # C99 shell
    r'r57\.php|'           # R57 shell
    r'/cgi-bin/|'          # CGI probe
    r'/cgi/|'              # CGI alternate
    r'/etc/passwd|'        # Path traversal
    r'/etc/shadow|'        # Path traversal
    r'\.\./\.\.'           # Directory traversal
    r')',
    re.IGNORECASE,
)


class ScannerBlockMiddleware:
    """Block known scanner probe paths."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if SCANNER_PATHS.search(path):
            logger.debug(
                'Blocked scanner probe: %s from %s',
                path,
                request.META.get('REMOTE_ADDR', '-'),
            )
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('<h1>Forbidden</h1>')
        return self.get_response(request)
