"""
Generates a database schema diagram in the file "dbschema.png". See
https://bitbucket.org/zzzeek/sqlalchemy/wiki/UsageRecipes/SchemaDisplay
To run this, you must install the "sqlalchemy_schemadisplay" package.
"""
from sqlalchemy import MetaData
from sqlalchemy_schemadisplay import create_schema_graph
from core import initialize, import_all_model_modules
from core.model import Base

initialize()
import_all_model_modules()

#Base.metadata.reflect()

# create the pydot graph object by autoloading all tables via a bound metadata object
graph = create_schema_graph(metadata=Base.metadata,
   show_datatypes=True,
   show_indexes=False,
   rankdir='LR', # From left to right (instead of top to bottom)
   concentrate=False # Don't try to join the relation lines together
)
graph.write_png('dbschema.png') # write out the file

