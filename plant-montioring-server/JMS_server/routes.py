""" module that incorporates all routes to recources of the app
"""
from views import (index, get_data)


def setup_routes(app):
    app.router.add_get('/', index)
    app.router.add_get('/data', get_data)
