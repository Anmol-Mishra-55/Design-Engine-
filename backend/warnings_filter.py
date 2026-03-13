import os
import warnings

# Suppress all warnings at the Python level
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

# Specific filters for external libraries
warnings.filterwarnings("ignore", category=DeprecationWarning, module="sqlalchemy")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pymongo")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=ResourceWarning)
