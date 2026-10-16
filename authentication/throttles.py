import re
from hashlib import sha256
from django.conf import settings
from ipaddress import ip_address

from rest_framework.throttling import SimpleRateThrottle


class LoginAccountThrottle(SimpleRateThrottle):
    scope = "login_account"
    rate = "5/min"

    def get_cache_key(self, request, view):
        data = request.data if isinstance(request.data, dict) else {}
        username = str(data.get("username", ""))[:150].casefold()
        digest = sha256(username.encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class AuthAddressThrottle(SimpleRateThrottle):
    scope = "auth_address"
    rate = "60/min"

    def get_cache_key(self, request, view):
        address = request.META.get("REMOTE_ADDR", "unknown")
        if getattr(settings, "TRUST_PROXY_ADDRESS", False):
            try:
                address = str(ip_address(request.META.get("HTTP_X_FORWARDED_FOR", "")))
            except ValueError:
                pass
        return self.cache_format % {"scope": self.scope, "ident": address}


class RegistrationThrottle(AuthAddressThrottle):
    scope = "registration"
    rate = "10/hour"


class RefreshThrottle(AuthAddressThrottle):
    scope = "refresh"
    rate = "120/min"


class RegistrationCodeAddressThrottle(AuthAddressThrottle):
    scope = "registration_code_address"
    rate = "20/hour"


class RegistrationPhoneThrottle(SimpleRateThrottle):
    scope = "registration_phone"
    rate = "5/hour"

    def get_cache_key(self, request, view):
        data = request.data if isinstance(request.data, dict) else {}
        phone = re.sub(r"[^0-9]", "", str(data.get("phone_number", ""))[:32])
        return self.cache_format % {"scope": self.scope, "ident": sha256(phone.encode()).hexdigest()}
