"""GoldenShield Terminal HTTP routes (lazy exports — avoids import cycles with gateway)."""

__all__ = ["handle_get", "handle_post", "handle_put"]


def __getattr__(name: str):
    if name in __all__:
        from terminal_app.routes.router import handle_get, handle_post, handle_put

        return {"handle_get": handle_get, "handle_post": handle_post, "handle_put": handle_put}[name]
    raise AttributeError(name)
