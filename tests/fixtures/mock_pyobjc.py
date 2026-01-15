"""Mock PyObjC classes for cross-platform testing."""

from unittest.mock import MagicMock


class MockNSRect:
    """Mock NSRect structure."""

    def __init__(self, x=0, y=0, width=200, height=300):
        self.origin = MagicMock()
        self.origin.x = x
        self.origin.y = y
        self.size = MagicMock()
        self.size.width = width
        self.size.height = height


class MockNSImage:
    """Mock NSImage for image loading."""

    def __init__(self, path=None):
        self._path = path
        self._size = MagicMock()
        self._size.width = 200
        self._size.height = 300

    @classmethod
    def alloc(cls):
        return cls()

    def initWithContentsOfFile_(self, path):
        self._path = path
        return self

    def size(self):
        return self._size


class MockNSWindow:
    """Mock NSWindow for overlay testing."""

    def __init__(self):
        self._frame = MockNSRect(0, 0, 200, 300)
        self._alpha = 1.0
        self._visible = False
        self._level = 0
        self._content_view = None

    @classmethod
    def alloc(cls):
        return cls()

    def initWithContentRect_styleMask_backing_defer_(
        self, rect, style, backing, defer
    ):
        self._frame = rect
        return self

    def setFrame_display_(self, frame, display):
        self._frame = frame

    def frame(self):
        return self._frame

    def setAlphaValue_(self, alpha):
        self._alpha = alpha

    def alphaValue(self):
        return self._alpha

    def orderFront_(self, sender):
        self._visible = True

    def orderOut_(self, sender):
        self._visible = False

    def isVisible(self):
        return self._visible

    def setLevel_(self, level):
        self._level = level

    def setOpaque_(self, opaque):
        pass

    def setBackgroundColor_(self, color):
        pass

    def setIgnoresMouseEvents_(self, ignores):
        pass

    def setHasShadow_(self, shadow):
        pass

    def setContentView_(self, view):
        self._content_view = view

    def contentView(self):
        return self._content_view

    def animator(self):
        return self


class MockNSView:
    """Mock NSView for content rendering."""

    def __init__(self):
        self._frame = MockNSRect()
        self._needs_display = False
        self._image = None

    @classmethod
    def alloc(cls):
        return cls()

    def initWithFrame_(self, frame):
        self._frame = frame
        return self

    def setNeedsDisplay_(self, needs):
        self._needs_display = needs


class MockNSApplication:
    """Mock NSApplication for app lifecycle."""

    _shared = None

    def __init__(self):
        self._running = False
        self._delegate = None

    @classmethod
    def sharedApplication(cls):
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    def run(self):
        self._running = True

    def terminate_(self, sender):
        self._running = False

    def setDelegate_(self, delegate):
        self._delegate = delegate


class MockNSWorkspace:
    """Mock NSWorkspace for frontmost app detection."""

    _shared = None
    _frontmost_pid = 12345
    _frontmost_name = "Terminal"

    def __init__(self):
        pass

    @classmethod
    def sharedWorkspace(cls):
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    def frontmostApplication(self):
        app = MagicMock()
        app.processIdentifier.return_value = self._frontmost_pid
        app.localizedName.return_value = self._frontmost_name
        return app

    @classmethod
    def set_frontmost(cls, pid, name="Terminal"):
        """Helper to set frontmost app for tests."""
        cls._frontmost_pid = pid
        cls._frontmost_name = name


class MockNSTimer:
    """Mock NSTimer for polling callbacks."""

    _timers = []

    def __init__(self, interval=0, target=None, selector=None, repeats=False):
        self._interval = interval
        self._target = target
        self._selector = selector
        self._repeats = repeats
        self._valid = True

    @classmethod
    def scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        cls, interval, target, selector, info, repeats
    ):
        timer = cls(interval, target, selector, repeats)
        cls._timers.append(timer)
        return timer

    def invalidate(self):
        self._valid = False
        if self in MockNSTimer._timers:
            MockNSTimer._timers.remove(self)

    def isValid(self):
        return self._valid

    @classmethod
    def clear_all(cls):
        """Helper to clear all timers between tests."""
        cls._timers.clear()


class MockNSColor:
    """Mock NSColor for window styling."""

    @staticmethod
    def clearColor():
        return MagicMock()

    @staticmethod
    def colorWithCalibratedRed_green_blue_alpha_(r, g, b, a):
        return MagicMock()


class MockNSAnimationContext:
    """Mock NSAnimationContext for animations."""

    _current = None

    def __init__(self):
        self.duration = 0
        self.completionHandler = None

    @classmethod
    def beginGrouping(cls):
        cls._current = cls()

    @classmethod
    def endGrouping(cls):
        if cls._current and cls._current.completionHandler:
            cls._current.completionHandler()
        cls._current = None

    @classmethod
    def currentContext(cls):
        if cls._current is None:
            cls._current = cls()
        return cls._current

    def setDuration_(self, duration):
        self.duration = duration

    def setCompletionHandler_(self, handler):
        self.completionHandler = handler


class MockQuartz:
    """Mock Quartz window detection functions."""

    _windows = []

    @staticmethod
    def CGWindowListCopyWindowInfo(options, window_id):
        """Return mock window list."""
        if not MockQuartz._windows:
            return [
                {
                    'kCGWindowOwnerPID': 12345,
                    'kCGWindowOwnerName': 'Terminal',
                    'kCGWindowNumber': 54321,
                    'kCGWindowBounds': {
                        'X': 100,
                        'Y': 100,
                        'Width': 800,
                        'Height': 600,
                    },
                }
            ]
        return MockQuartz._windows

    @classmethod
    def set_windows(cls, windows):
        """Helper to set window list for tests."""
        cls._windows = windows

    @classmethod
    def clear_windows(cls):
        """Helper to clear window list."""
        cls._windows = []


# Constants that would be imported from Quartz
kCGWindowListOptionOnScreenOnly = 1
kCGNullWindowID = 0
NSFloatingWindowLevel = 3
NSBorderlessWindowMask = 0
NSBackingStoreBuffered = 2
