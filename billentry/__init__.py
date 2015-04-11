# the submodule "app" has an object inside it that happens to have the same
# name, and the latter is what consumers actually want to import
from .app import application as app
from .app import application
