from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .authentication import cookie_settings


class CookieTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return response

        access = response.data.get('access')
        refresh = response.data.get('refresh')
        if access:
            response.set_cookie('access_token', access, **cookie_settings())
        if refresh:
            response.set_cookie('refresh_token', refresh, **cookie_settings())
        return response


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if not data.get('refresh'):
            cookie_refresh = request.COOKIES.get('refresh_token')
            if cookie_refresh:
                data['refresh'] = cookie_refresh

        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            response = Response({'detail': 'Refresh token inválido.'}, status=status.HTTP_401_UNAUTHORIZED)
            response.delete_cookie('access_token', path='/')
            response.delete_cookie('refresh_token', path='/')
            return response

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        access = serializer.validated_data.get('access')
        refresh = serializer.validated_data.get('refresh')
        if access:
            response.set_cookie('access_token', access, **cookie_settings())
        if refresh:
            response.set_cookie('refresh_token', refresh, **cookie_settings())
        return response
