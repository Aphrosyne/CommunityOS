# Changelog

All notable changes to CommunityOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

---

## [Unreleased]

---

## [0.3.0] - 2026-06-29

### Added

- 图片投稿插件：私聊投稿 → Gilbert 曲线混淆 → 转发到群。
- Gilbert 曲线混淆服务（image_obfuscator.py），numpy 加速。
- 公共服务层：文件存储（storage.py）、定时调度（scheduler.py）。
- 图片处理流水线文档（image-pipeline.md v0.2）。
- 开发记录：2026-06-29-image-pipeline.md。

---

## [0.2.0] - 2026-06-28

### Added

- Bot 框架搭建：NoneBot2 + FastAPI + OneBot V11 适配器。
- 核心/公共服务/插件/平台适配 四层架构。
- greet 插件：被 @ 时自动回复，回复内容由 `.env` 配置。
- 公共服务层：日志（logger.py）、配置（config.py）。
- 开发记录：2026-06-28-bootstrap.md。

---

## [0.1.0] - 2026-06-28

### Added

- 项目初始化，MIT 许可证。
- 核心理念文档（philosophy.md），中英双语。
- 总体架构文档（architecture.md v0.2），中英双语。
- 社区治理框架（governance.md v0.1）。
- 基础项目结构（docs/ bot/ tests/ scripts/）。
