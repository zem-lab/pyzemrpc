# pyzemrpc wheel 发布

当前仅交付主包纯 Python wheel，不制作独立 GUI exe，不使用 PyInstaller、Nuitka 或 C/C++ 编译。GUI 和样品台运动参数 JSON-RPC 调试页保留在 wheel 中，安装后运行 `pyzemrpc`。

## 构建与校验

遵循 [AGENTS.md](../AGENTS.md)：先提交完整源码和版本修改，再从干净提交生成 `zemrpc/__commit__.py` 和 wheel。构建后修改会进入产物或影响构建的内容，需要重新提交并重建。

```powershell
.venv/Scripts/Activate.ps1
python -m invoke build
# build_all 是兼容入口，也只构建主包 wheel。
python -m twine check dist/pyzemrpc-<版本>-py3-none-any.whl
```

版本定义在 `zemrpc/__version__.py`。核对 wheel 内的版本、`zemrpc/__commit__.py`、GUI/接口模块、文件大小和 SHA256；源码提交必须与构建记录一致。

可选 Rust 加速包是独立项目，`build_rust` 不属于当前主包发布流程。主包发布无需构建或同步其版本。

## 安装与运行

```powershell
python -m pip install dist/pyzemrpc-<版本>-py3-none-any.whl
pyzemrpc
```

## 上传

生成本地产物不等于授权上传。只有用户明确要求发布到相应索引时才上传；使用一个经过校验的确切 wheel 文件，避免通配符带入历史产物。认证沿用本机已有配置，不在仓库保存凭据。

主包发布技能为 [.agents/skills/release-pyzemrpc/SKILL.md](../.agents/skills/release-pyzemrpc/SKILL.md)，用于 PyPI/devpi 发布与远端哈希核验。已上传的同版本产物不可用另一份不同哈希的文件替换。
