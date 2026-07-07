"""
Dynamic plugin discovery and loading.

Scans the plugins/ directory at startup for Python modules that implement
the Translator interface. Plugins are loaded via importlib without any
static dependency on their implementation.

The application finds the best available translator automatically:
  1. Scan plugins/ for Translator implementations.
  2. If a specific plugin name is configured, use that one.
  3. Otherwise, pick the first available plugin.
  4. Fall back to GenericTranslator if nothing else is found.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Optional

from translation.translator import Translator
from translation.generic_translator import GenericTranslator
from utils.logger import get_logger

logger = get_logger(__name__)


class PluginLoader:
    """Discovers and loads Translator plugins from the plugins/ directory.

    Usage:
        loader = PluginLoader()
        translator = loader.load(preferred="google_translate")
        result = translator.translate("Hello world")
    """

    def __init__(self, plugins_dir: Path | None = None) -> None:
        """Initialize the plugin loader.

        Args:
            plugins_dir: Path to the plugins directory. Defaults to
                         <project_root>/plugins/ with PyInstaller support.
        """
        if plugins_dir is None:
            plugins_dir = self._resolve_plugins_dir()
        self._plugins_dir = Path(plugins_dir)
        self._available: dict[str, type[Translator]] = {}

    @staticmethod
    def _resolve_plugins_dir() -> Path:
        """Find the plugins directory, handling PyInstaller bundles."""
        import sys

        base = Path(__file__).resolve().parent.parent

        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent
            bundled = exe_dir / "_internal" / "plugins"
            if bundled.exists():
                return bundled
            unbundled = exe_dir / "plugins"
            if unbundled.exists():
                return unbundled

        return base / "plugins"

    @property
    def plugins_dir(self) -> Path:
        """Return the path to the plugins directory."""
        return self._plugins_dir

    @property
    def available_plugins(self) -> dict[str, type[Translator]]:
        """Return a mapping of plugin name -> Translator class."""
        return dict(self._available)

    def scan(self) -> dict[str, type[Translator]]:
        """Scan the plugins directory for Translator implementations.

        Does NOT import any modules. Only discovers available plugins.

        Returns:
            Dictionary of plugin_name -> Translator class.
        """
        self._available.clear()

        if not self._plugins_dir.exists():
            logger.debug("Plugins directory does not exist: %s", self._plugins_dir)
            self._plugins_dir.mkdir(parents=True, exist_ok=True)
            return {}

        for entry in self._plugins_dir.iterdir():
            if entry.name.startswith("_") or entry.name.startswith("."):
                continue
            if entry.is_dir():
                self._scan_package(entry)
            elif entry.suffix == ".py" and entry.name != "__init__.py":
                self._scan_module(entry)

        logger.info(
            "Plugin scan complete. Found %d plugin(s): %s",
            len(self._available),
            list(self._available.keys()),
        )
        return dict(self._available)

    def _scan_module(self, file_path: Path) -> None:
        """Scan a single .py file for Translator implementations."""
        try:
            module = self._load_module(file_path)
            self._find_translators(module)
        except Exception as e:
            logger.warning("Failed to scan module %s: %s", file_path.name, e)

    def _scan_package(self, dir_path: Path) -> None:
        """Scan a package directory for Translator implementations."""
        init_file = dir_path / "__init__.py"
        if not init_file.exists():
            return
        try:
            module = self._load_module(init_file, package_name=dir_path.name)
            self._find_translators(module)
        except Exception as e:
            logger.warning("Failed to scan package %s: %s", dir_path.name, e)

    def _load_module(self, file_path: Path, package_name: str | None = None) -> object:
        """Dynamically load a Python module from a file path.

        Args:
            file_path: Path to the .py file.
            package_name: Optional package name for the module.

        Returns:
            The loaded module object.
        """
        if package_name is None:
            package_name = file_path.stem

        qualified_name = f"plugins.{package_name}"

        if qualified_name in sys.modules:
            return sys.modules[qualified_name]

        spec = importlib.util.spec_from_file_location(
            qualified_name,
            str(file_path),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified_name] = module
        spec.loader.exec_module(module)
        return module

    def _find_translators(self, module: object) -> None:
        """Scan a loaded module for Translator subclasses."""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if not isinstance(attr, type):
                continue
            if attr is Translator:
                continue
            if not issubclass(attr, Translator):
                continue
            if getattr(attr, "__abstractmethods__", None):
                continue

            try:
                instance = attr()
                self._available[instance.name] = attr
                logger.info("Found translator plugin: %s", instance.name)
            except Exception as e:
                logger.warning(
                    "Found plugin class %s but failed to instantiate: %s",
                    attr.__name__,
                    e,
                )

    def load(self, preferred: str | None = None) -> Translator:
        """Load the best available translator.

        Priority order:
        1. The preferred plugin (if specified and available).
        2. The first plugin found during scanning.
        3. GenericTranslator as fallback.

        Args:
            preferred: Name of the preferred plugin to use.

        Returns:
            A Translator instance ready for use.
        """
        self.scan()

        if preferred and preferred in self._available:
            plugin_cls = self._available[preferred]
            logger.info("Using preferred translator: %s", preferred)
            try:
                return plugin_cls()
            except Exception as e:
                logger.error("Failed to instantiate preferred plugin '%s': %s", preferred, e)

        if self._available:
            name, plugin_cls = next(iter(self._available.items()))
            logger.info("Using discovered translator: %s", name)
            try:
                return plugin_cls()
            except Exception as e:
                logger.error("Failed to instantiate plugin '%s': %s", name, e)

        logger.info("No plugins found. Using GenericTranslator (pass-through).")
        return GenericTranslator()


def discover_translator(plugins_dir: Path | None = None, preferred: str | None = None) -> Translator:
    """Convenience function to discover and load a translator.

    Args:
        plugins_dir: Path to plugins directory.
        preferred: Name of preferred plugin.

    Returns:
        A Translator instance.
    """
    loader = PluginLoader(plugins_dir)
    return loader.load(preferred)
