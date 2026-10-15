"""MeTube - local YouTube downloader for Windows.

Keep this module import-light: it must never import submodules, so that
``import metube`` cannot trigger circular imports between the config/logger
layer and the UI layer.
"""

__version__ = "2.0.0"
__app_name__ = "MeTube"
