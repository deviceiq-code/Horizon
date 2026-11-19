from django.utils import translation

from .models import UserPreferences


class UserLanguageMiddleware:
    """Activate the language saved in the logged-in user's preferences.

    Must come after LocaleMiddleware (which handles anonymous visitors via Accept-Language)
    and AuthenticationMiddleware (which sets request.user from the session).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            language = (
                UserPreferences.objects.filter(user=request.user)
                .values_list("language", flat=True)
                .first()
            )
            if language:
                translation.activate(language)
                request.LANGUAGE_CODE = language
        return self.get_response(request)
