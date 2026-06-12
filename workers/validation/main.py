import os
import sys

# Add root folder to python path to import app settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workers.validation.subscriber import start_subscriber

if __name__ == "__main__":
    start_subscriber()
