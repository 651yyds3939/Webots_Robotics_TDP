# Git 推送与分支排障

记录 2026-10-13 一次"推送成功后 GitHub 首页看不到最新内容"的排查与处理，供后续遇到同类问题时参考。

## 现象

本地提交并推送成功（`git status` 显示与远端一致），但打开 GitHub 仓库首页看到的 README 和 `docs/` 仍是旧版本，看起来像"没有传上去"。

## 原因

两个独立问题叠加：

1. **内容推到了非默认分支。** 开发工作在 `optimize-dribble-alignment` 分支上进行并推送。GitHub 仓库首页只展示默认分支 `main` 的内容；当时 `main` 停留在较早提交（`f4a234d`），因此首页显示旧版 README。文件本身早已上传成功，只是不在首页展示的分支上。
2. **终端环境没有 GitHub 凭据。** 合并后从命令行 `git push` 报 `fatal: could not read Username for 'https://github.com'`。本机未配置 git credential helper、没有 `~/.git-credentials`、`gh` CLI 未登录、也没有 SSH 密钥；此前成功推送依靠 VSCode 界面内单独保存的 GitHub 登录，命令行读取不到。

## 处理步骤

1. 检查各分支与远端状态：

   ```bash
   git branch -a
   git ls-remote --heads origin
   git log --oneline main..<工作分支>   # 工作分支领先 main 的提交
   ```

2. 确认 `main` 没有独有提交（`git log <工作分支>..main` 为空）后，本地快进合并：

   ```bash
   git checkout main
   git merge --ff-only <工作分支>
   ```

3. 推送，任选其一：

   - VSCode 源代码管理面板点击"同步更改"（使用 VSCode 保存的 GitHub 登录）；
   - 或配置一次 `gh auth login`（设备码流程，一次配置长期有效）后由命令行推送；
   - 或使用 Personal Access Token 配置命令行凭据。

4. 验证远端：

   ```bash
   git ls-remote origin main   # 应与本地 main 提交一致
   ```

## 预防

- 日常改动尽量直接提交到 `main`；在功能分支上工作时，完成后及时快进合并回 `main` 并推送，避免首页长期停留在旧提交。
- 需要命令行推送时，先配置 `gh auth login`，避免再次出现"终端无凭据"的问题。
