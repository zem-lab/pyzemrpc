# Agent 工作约定

## 打包方式（用户确认，2026-10-14）

- **pyzemrpc 主包和 GUI 以后不做 C/C++ 编译，不使用 Nuitka，也不调用 MSVC/GCC/Clang 编译 Python 代码。**
- 主包构建纯 Python wheel；独立 GUI 使用 `invoke build_exe` 的 PyInstaller onedir 打包，收集现成的 Python、Qt 和依赖二进制。
- `invoke build_all` 仅生成 wheel 与 PyInstaller GUI，不触发原生编译。`build_rust` 是独立可选加速包入口，不纳入主包/GUI交付流程。
- 打包依赖优先安装已有 wheel，缺少二进制依赖时明确报告，不自动转为源码/C编译。
- 继续遵守下方先提交源码、再生成构建元数据和产物、校验版本/源提交/SHA256 的规则。

## 强制发布顺序：先提交，再构建打包

维护者于 2026-09-30 明确要求所有交付产物先提交再打包，使嵌入的 commit 能准确追溯实际源码。适用于 wheel、exe 及其他发布包。

1. 完成本任务的代码、版本号、资源、打包脚本及必要文档修改，先做开发验证；检查 git status / diff，只提交本任务变更。
2. 提交成功后记录 git rev-parse HEAD 的完整 commit，从该提交的干净源码重新构建，不能交付提交前构建的旧包。
3. 在该提交之后重新生成 zemrpc/__commit__.py，再构建和验证 wheel / exe。嵌入的 GIT_INFO、发布记录的源码 commit 必须等于本次构建提交；核对实际包内容、版本与 SHA-256，不能只检查源目录。
4. 若提交后又修改会进入产物或影响构建的内容，必须重新提交并重建打包。不得仅修改 commit 元数据或发布清单来冒充新构建。
5. 保留无关的未提交工作，不混入提交或产物，也不清理、重置或覆盖。工作区无法保持发布源码干净时，从独立的干净 checkout 或提交快照构建，并重新生成需要的忽略文件。

临时开发构建可用于验证，但不能当作正式交付包。生成的 __commit__.py、wheel、日志等不必循环提交；上传、推送仍按用户实际授权执行。

旧发布脚本的 ConfirmedWorktree 仅是检查确认参数，绝不是允许打包未提交源码的豁免。旧文档或技能中允许混入未提交改动的说法已失效。

注意仓库归属：真实电镜的 software.commit_id 是远程 Shell 的构建提交，SDK 必须原样解析，不能用本地 pyzemrpc 的 GIT_INFO 代替。VirtualZem 报告自己的 SDK 构建身份。跨项目交付时，各仓库分别先提交、再构建并记录各自的 commit。

相关说明：[软件版本接口](doc/software_info.md)、[Python 开发约定](CLAUDE.md)、[发布技能](.agents/skills/release-pyzemrpc/SKILL.md)。
