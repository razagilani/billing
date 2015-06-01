# the submodule "app" has an object inside it that happens to have the same
# name, and the latter is what consumers actually want to import
from .app import application as app
from .app import application

# according to Flask documentation, it seems that the officially correct way
# to structure the project is to put the "app" object, and probably the
# entire contents of "app.py", into this file, into this file.
# http://flask.pocoo.org/docs/0.10/patterns/packages/
