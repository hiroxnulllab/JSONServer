"""
WSGI entry point — PythonAnywhere.
"""
import sys, os

project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["JSONSERVER_ENV"] = "production"
os.environ.setdefault("JSONSERVER_DB_PATH", os.path.join(project_home, "data"))

from jsonserver.app import create_app
from jsonserver.config import get_config

application = create_app(get_config())
