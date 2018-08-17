# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
#
"""Tests for the plugin."""# Test library imports
import pytest

# Local imports
from spyder_modelx.modelxplugin import ModelxPlugin


@pytest.fixture
def setup_modelx(qtbot):
    """Set up the ModelxPlugin plugin."""
    modelx = ModelxPlugin(None)
    qtbot.addWidget(modelx)
    modelx.show()
    return modelx


def test_basic_initialization(qtbot):
    """Test ModelxPlugin initialization."""
    modelx = setup_modelx(qtbot)

    # Assert that plugin object exist
    assert modelx is not None


if __name__ == "__main__":
    pytest.main()
