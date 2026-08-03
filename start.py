import os

port = int(os.environ.get("PORT", 8503))
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))

if os.environ.get("RENDER") or os.environ.get("PRODUCTION"):
    from dash_app import server
    import gunicorn.app.base

    class StandaloneApplication(gunicorn.app.base.BaseApplication):
        def __init__(self, app, options=None):
            self.application = app
            self.options = options or {}
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key, value)

        def load(self):
            return self.application

    StandaloneApplication(server, {
        "bind": f"0.0.0.0:{port}",
        "workers": workers,
        "threads": 2,
        "timeout": 30,
        "preload_app": False,
        "loglevel": "info",
    }).run()
else:
    from dash_app import app
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
