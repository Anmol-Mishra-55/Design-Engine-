#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import engine

CityValidation.__table__.create(engine, checkfirst=True)
print("CityValidation table created successfully")
