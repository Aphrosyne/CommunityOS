# CommunityOS Architecture

> **Status:** Draft
> **Version:** v0.2
> **Last Updated:** 2026-06-28

---

# Purpose

This document defines the overall software architecture of CommunityOS.

Architecture defines **how the system is organized**, not how individual features are implemented.

All bot functionality, platform adapters, and shared services should follow this architecture.

---

# Design Goals

CommunityOS pursues the following architectural goals:

* Modular
* Plugin-Oriented
* Platform Independent
* Maintainable
* Extensible
* Automation First

Any new functionality should minimize impact on existing modules.

---

# Overall Architecture

```text
                  CommunityOS
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
      Core          Services        Plugins
        │               │               │
        └───────────────┼───────────────┘
                        │
                Platform Adapter
                        │
                     NapCat / QQ
```

CommunityOS is divided into four main layers:

* Core
* Services
* Plugins
* Platform Adapter

---

# Core

Core is the center of the system.

Responsibilities include:

* Receiving platform events
* Dispatching tasks
* Managing plugin lifecycle
* Providing unified interfaces

Core does not handle business logic.

No business logic should be written directly in Core.

---

# Services

Services provide reusable shared capabilities.

Examples include:

* Logger
* Storage
* Config
* Scheduler
* Backup

Services do not respond directly to QQ messages.

Services exist only to provide capabilities to plugins.

Multiple plugins share the same Service.

---

# Plugins

All CommunityOS functionality exists as plugins.

Example directory layout:

```text
plugins/

welcome/

image/

backup/

statistics/

keyword/

risk/

scheduler/
```

Each plugin is responsible for a single, clear responsibility.

Plugins should remain as independent as possible.

When adding new functionality, prioritize creating a new plugin rather than modifying an existing one.

---

# Platform Adapter

The Platform Adapter handles communication with chat platforms.

Current support:

* NapCat (QQ)

Future platforms:

* Discord
* Telegram
* Matrix
* Web

Platform Adapter responsibilities:

* Receiving platform events
* Sending messages
* Uploading files
* Calling platform APIs

No business logic should be written in the Platform Adapter.

---

# Request Flow

A typical request follows this flow:

```text
QQ Group Event

↓

NapCat

↓

Platform Adapter

↓

Core

↓

Plugin

↓

Service (if needed)

↓

Return Result

↓

Platform Adapter

↓

QQ Group
```

The platform handles communication only.

Plugins handle business logic.

Services provide shared capabilities.

---

# Plugin Lifecycle

Plugins are managed by Core.

The lifecycle includes:

* Load
* Enable
* Disable
* Reload
* Unload

Plugins should not manage their own lifecycle.

---

# Configuration

All configuration uses external configuration files.

The following must not be hardcoded:

* QQ numbers
* Group numbers
* Tokens
* API keys
* File paths

Configuration should support centralized management in the future.

---

# Logging

All important operations should be logged.

Recommended log events include:

* Moderation actions
* Plugin exceptions
* Automated tasks
* Image processing
* Member approval

Logging should be centrally managed by the Logger Service.

---

# Error Handling

When any plugin encounters an exception:

* It must not cause the entire bot to exit.
* An error log should be recorded.
* Other plugins should continue running whenever possible.

Plugins should be isolated from each other.

---

# Directory Structure

Recommended directory layout:

```text
bot/

core/

services/

plugins/

platform/

config/

data/

logs/
```

docs/
```

Each directory has a clearly defined responsibility.

Avoid mixing different responsibilities.

---

# Design Principles

CommunityOS follows these principles during development:

* Single Responsibility
* Loose Coupling
* Configuration over Hardcode
* Plugin over Modification
* Stability Before Complexity

---

# Out of Scope

This document does not cover:

* Community governance
* Group rules
* NapCat deployment
* Plugin internals
* Image processing workflow
* Database design

These topics are documented elsewhere.

---

# Summary

CommunityOS aims to build a long-term maintainable community automation system through clear module boundaries.

Platforms may change.

Plugins may be added.

Implementations may be refactored.

The overall architecture should remain stable and continue supporting the community's growth.
