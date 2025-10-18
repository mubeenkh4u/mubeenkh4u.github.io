# tests/conftest.py
import os, sys
# Add project root (parent of /tests) to sys.path so 'animal_shelter' is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))