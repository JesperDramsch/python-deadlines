import sys

sys.path.append(".")
from sort_yaml import sort_data
from import_python_organizers import main as updater

if __name__ == "__main__":
    updater()
    sort_data()