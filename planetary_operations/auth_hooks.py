from allianceauth import hooks
from allianceauth.menu.hooks import MenuItemHook
from allianceauth.services.hooks import UrlHook

from . import urls


class PlanetaryMenu(MenuItemHook):
    def __init__(self):
        super().__init__(
            "Planetary Operations", "fa-solid fa-globe", "planetary_operations:index", order=1500
        )

    def render(self, request):
        if request.user.has_perm("planetary_operations.basic_access"):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def menu_item():
    return PlanetaryMenu()


@hooks.register("url_hook")
def url_hook():
    return UrlHook(urls, "planetary_operations", r"^planetary-operations/")
