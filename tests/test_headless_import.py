"""Core RPC must work in an installation that has no Qt modules."""
import os
from pathlib import Path
import subprocess
import sys


def test_core_import_and_reconnect_without_qt():
    script = '''
import importlib.abc
import sys
class NoGui(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'qtpy', 'PySide6', 'PyQt6', 'pyqtgraph'}:
            raise AssertionError('GUI imported by core: ' + fullname)
sys.meta_path.insert(0, NoGui())
from zemrpc.zem.zem_api import zem_api
device = zem_api.device
assert device.socket._socket is None
device.update_remote_addr(('127.0.0.1', 9))
first = device.socket._socket
assert device.socket.rcv_worker.thread.is_alive()
device.disconnect()
assert first.fileno() == -1
assert device.socket.rcv_worker.thread is None
device.update_remote_addr(('127.0.0.1', 9))
assert device.socket._socket is not first
assert device.socket.rcv_worker.thread.is_alive()
device.disconnect()
assert not any(name.startswith(('qtpy', 'PySide6', 'pyqtgraph')) for name in sys.modules)
'''
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-c', script], cwd=root, env={**os.environ, 'PYTHONPATH': str(root)}, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
