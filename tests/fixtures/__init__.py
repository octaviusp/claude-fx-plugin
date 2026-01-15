# Test fixtures package
from tests.fixtures.mock_pyobjc import (
    MockNSWindow,
    MockNSApplication,
    MockNSWorkspace,
    MockNSImage,
    MockQuartz,
)
from tests.fixtures.sample_data import (
    SAMPLE_SETTINGS,
    SAMPLE_MANIFEST,
    SAMPLE_STATE,
    SAMPLE_HOOK_DATA,
)

__all__ = [
    "MockNSWindow",
    "MockNSApplication",
    "MockNSWorkspace",
    "MockNSImage",
    "MockQuartz",
    "SAMPLE_SETTINGS",
    "SAMPLE_MANIFEST",
    "SAMPLE_STATE",
    "SAMPLE_HOOK_DATA",
]
