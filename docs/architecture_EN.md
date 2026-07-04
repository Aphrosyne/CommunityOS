# CommunityOS Architecture

> **Status:** Stable
> **Version:** v1.0
> **Last Updated:** 2026-07-04

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
  Message Rule       Services        Plugins
    Service
        │               │               │
        └───────────────┼───────────────┘
                        │
              Command System
                        │
                Platform Adapter
                        │
                    NapCat / QQ
```

CommunityOS is divided into six main layers:

* Message Rule Service — unified group message entry, rule matching & routing
* Services — reusable shared capabilities
* Plugins — business feature implementation
* Command System — command registration, permission check, cooldown, dispatch
* Platform Adapter — communication with chat platforms

---

# Message Rule Service

The Message Rule Service is the unified entry point for all group messages:

* Receives all group messages
* Matches by rule type (`exact_text`, `contains_phrase`)
* Auto-routes low-permission commands to Command System (no @bot needed in managed groups)
* Routes keyword matches to auto-moderation plugin
* Does NOT execute commands or recall messages — only matches and routes

---

# Command System

The Command System is the unified command entry point:

* Command registration & alias management
* Command cooldown (3 tiers: query/session/admin)
* Command permission check (User/Admin/Owner)
* Shortcut mapping (full-text → resolved command)
* Command dispatch & audit logging

---

# Services

Services provide reusable shared capabilities.

Currently implemented:

* Logger Service — domain-based log files (bot/command/image/member/moderation/relationship)
* Config Service — external `.env` configuration
* Scheduler Service — based on APScheduler
* Permission Service — three levels (User/Admin/Owner)
* Session Service — multi-step interaction flow management
* Throttle Service — per (user_id, reply_type) reply rate limiting
* Cache Service — file-based cache with LRU eviction
* Runtime Service — startup time & status

Services do not respond directly to QQ messages.

Services exist only to provide capabilities to plugins.

Multiple plugins share the same Service.

---

# Plugins

All CommunityOS functionality exists as plugins.

Currently implemented:

```text
plugins/

├── help.py              # Help command
├── status.py            # Runtime status
├── command_dispatcher.py # Command dispatcher
├── publish.py           # Batch publish (obfuscate + multi-group)
├── obfuscate.py         # Image obfuscation
├── decode.py            # Image deobfuscation (3 methods)
├── mute.py              # Mute / unmute / self-mute
├── auto_recall.py       # Auto-recall on banned keywords
├── auto_complete.py     # URL auto-complete
├── shortcuts.py         # Shortcut mapping query
├── friend.py            # Auto friend-request handling
└── member.py            # Group member change logging
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

Group message flow:

```text
QQ Group Event

↓

NapCat

↓

Platform Adapter

↓

Message Rule Service
  ├─ Command rule hit → Command System → Plugin → Services → Reply
  ├─ Moderation rule hit → Auto Recall Plugin → Delete
  └─ No match → Ignore

↓

QQ Group
```

Private messages go directly to the Command System.

---

# Plugin Lifecycle

Plugins are managed by NoneBot2.

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

Configuration is provided via `.env` and `config/*.json` files.

---

# Logging

All important operations should be logged.

Logs are organized by business domain:

| Log File | Purpose |
|----------|---------|
| `bot.log` | System runtime, startup, errors |
| `command.log` | Command execution |
| `image.log` | Image operations |
| `member.log` | Group member events |
| `moderation.log` | Admin action audit |
| `relationship.log` | Friend relationship events |

Logging is centrally managed by the Logger Service. Console and file output are independently controlled.

---

# Error Handling

When any plugin encounters an exception:

* It must not cause the entire bot to exit.
* An error log should be recorded.
* Other plugins should continue running whenever possible.

Plugins should be isolated from each other.

---

# Directory Structure

Current directory layout:

```text
bot/

├── core/               # Startup & lifecycle hooks
├── services/           # Shared services
├── plugins/            # Business plugins
├── config/             # Config files (.json, gitignored)
├── data/               # Runtime data (gitignored)
├── logs/               # Log files (gitignored)
├── main.py             # Entry point
├── .env                # Environment config (gitignored)
├── .env.example        # Config template
├── setup.bat           # One-click setup
├── start.bat           # One-click start
└── requirements.txt    # Python dependencies
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
* NapCat deployment (see `deployment.md`)
* Plugin internals
* Image processing workflow (see `image-pipeline.md`)
* Command system details (see `command-system.md`)
* Database design

These topics are documented elsewhere.

---

# Summary

CommunityOS aims to build a long-term maintainable community automation system through clear module boundaries.

Platforms may change.

Plugins may be added.

Implementations may be refactored.

The overall architecture should remain stable and continue supporting the community's growth.
