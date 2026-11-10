"""Test that the Callwise web API imports and initializes cleanly without LiveKit or gRPC."""

import sys
from unittest.mock import patch


def test_api_main_imports_without_livekit_and_grpc():
    """
    Verify that callwise.api.main imports cleanly even when grpc,
    livekit.plugins.google, and native inference libraries are completely blocked.
    """
    blocked_modules = {
        "grpc": None,
        "grpc._cython": None,
        "grpc._cython.cygrpc": None,
        "livekit.plugins.google": None,
        "livekit.local_inference": None,
        "livekit.blingfire": None,
    }

    with patch.dict(sys.modules, blocked_modules):
        # 1. Importing TextAgent and CallwiseToolset must never load LiveKit/gRPC
        from callwise.agent.text_agent import TextAgent
        from callwise.agent.tools import CallwiseToolset

        assert TextAgent is not None
        assert CallwiseToolset is not None

        # 2. Importing the onboarding router must never load LiveKit/gRPC
        import callwise.api.onboarding

        assert callwise.api.onboarding.router is not None

        # 3. Importing the main FastAPI application must succeed cleanly
        import callwise.api.main

        assert callwise.api.main.app is not None
        assert callwise.api.main.app.title == "Callwise API"

