"""Isolated deterministic browser fixture, never imported by production."""
import os
from debate_lab.app import create_app
from test_preparation import PreparationProvider
app=create_app(os.environ['PREPARATION_PREVIEW_DATA'],PreparationProvider())
