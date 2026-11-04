from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .city_search import CitySearchUnavailable, search_cities


class CitySearchThrottle(UserRateThrottle):
    scope = "city-search"
    rate = "60/min"


class CitySearchView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [CitySearchThrottle]

    def get(self, request):
        query = " ".join(request.query_params.get("q", "").split())
        if len(query) > 150:
            return Response({"detail": "Shahar nomi juda uzun."}, status=400)
        if len(query) < 2:
            return Response([])
        # The public Photon endpoint supports default/de/en/fr. Native names
        # cover Uzbek and Russian cities while still accepting multilingual input.
        language = "default"
        try:
            return Response(search_cities(query, language))
        except CitySearchUnavailable:
            return Response({"detail": "Shahar qidiruvi vaqtincha ishlamayapti."}, status=503)
