#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _load_env() -> None:
    _load_env_file(Path.home() / ".hermes" / ".env")
    _load_env_file(Path.home() / ".config" / "memoryos-agent.env")


def _env(name: str, fallback: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    if fallback:
        return os.getenv(fallback)
    return None


def _config() -> dict[str, str]:
    _load_env()
    base_url = _env("VAULTMIND_BASE_URL", "MEMORYOS_BASE_URL")
    fallback_url = _env("VAULTMIND_FALLBACK_URL", "MEMORYOS_FALLBACK_URL")
    api_key = _env("VAULTMIND_API_KEY", "MEMORYOS_API_KEY")
    agent_id = _env("VAULTMIND_AGENT_ID", "MEMORYOS_AGENT_ID")
    if not base_url and fallback_url:
        base_url = fallback_url
    if not base_url or not api_key or not agent_id:
        raise SystemExit(
            "Missing VaultMind configuration. Set VAULTMIND_BASE_URL, "
            "VAULTMIND_API_KEY, and VAULTMIND_AGENT_ID in ~/.hermes/.env."
        )
    return {
        "base_url": base_url.rstrip("/"),
        "fallback_url": (fallback_url or "").rstrip("/"),
        "api_key": api_key,
        "agent_id": agent_id,
    }


def _request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    config = _config()
    urls = [config["base_url"]]
    if config["fallback_url"] and config["fallback_url"] not in urls:
        urls.append(config["fallback_url"])

    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "X-Api-Key": config["api_key"],
        "X-Agent-Id": config["agent_id"],
        "Content-Type": "application/json",
    }

    last_error: str | None = None
    for base_url in urls:
        req = request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=8) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = f"{base_url}{path}: HTTP {exc.code} {detail}"
        except error.URLError as exc:
            last_error = f"{base_url}{path}: {exc}"
    raise SystemExit(last_error or f"Request failed for {path}")


def _print_result(data: Any, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if isinstance(data, dict) and "results" in data:
        results = data.get("results") or []
        print(f"mode={data.get('mode')} state={data.get('state')} rounds={data.get('rounds')}")
        if not results:
            print("No results.")
            return
        for index, item in enumerate(results, start=1):
            summary = item.get("summary", "").strip()
            memory_type = item.get("memory_type", "")
            tags = ",".join(item.get("tags", []))
            print(f"{index}. [{memory_type}] {summary}")
            if tags:
                print(f"   tags={tags}")
            body = (item.get("body") or "").strip()
            if body:
                print(f"   body={body}")
        return

    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}={value}")
        return

    print(data)


def cmd_health(args: argparse.Namespace) -> None:
    data = _request_json("GET", "/readyz")
    _print_result(data, args.format)


def cmd_recall(args: argparse.Namespace) -> None:
    payload = {
        "query": args.query,
        "mode": args.mode,
        "limit": args.limit,
        "include_body": args.include_body,
        "session_id": args.session_id,
        "current_topic": args.current_topic,
        "tags": args.tag,
        "entities": args.entity,
    }
    data = _request_json("POST", "/api/v1/memory/retrieve", payload)
    _print_result(data, args.format)


def cmd_remember(args: argparse.Namespace) -> None:
    payload = {
        "session_id": args.session_id or "hermes-skill",
        "memory_type": args.kind,
        "source_type": "hermes-skill",
        "source_ref": "hermes://skill/vaultmind",
        "summary": args.summary or args.text,
        "body": args.text,
        "importance": args.importance,
        "confidence": args.confidence,
        "stability": args.stability,
        "tags": list(dict.fromkeys(["vaultmind-skill", "hermes-parallel-memory", *args.tag])),
        "entities": args.entity,
    }
    data = _request_json("POST", "/api/v1/memory/create", payload)
    _print_result(data, args.format)


def cmd_list(args: argparse.Namespace) -> None:
    payload = {
        "limit": args.limit,
        "tags": args.tag or ["vaultmind-skill"],
        "query": args.query,
        "entities": args.entity,
    }
    data = _request_json("POST", "/api/v1/memory/list", payload)
    _print_result(data, args.format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Use VaultMind as a parallel memory system for Hermes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health = subparsers.add_parser("health", help="Check VaultMind connectivity.")
    health.add_argument("--format", choices=("pretty", "json"), default="pretty")
    health.set_defaults(func=cmd_health)

    recall = subparsers.add_parser("recall", help="Retrieve memories from VaultMind.")
    recall.add_argument("--query", required=True)
    recall.add_argument("--mode", choices=("lightweight", "agentic", "auto"), default="auto")
    recall.add_argument("--limit", type=int, default=5)
    recall.add_argument("--include-body", action="store_true")
    recall.add_argument("--session-id")
    recall.add_argument("--current-topic")
    recall.add_argument("--tag", action="append", default=[])
    recall.add_argument("--entity", action="append", default=[])
    recall.add_argument("--format", choices=("pretty", "json"), default="pretty")
    recall.set_defaults(func=cmd_recall)

    remember = subparsers.add_parser("remember", help="Store a durable memory in VaultMind.")
    remember.add_argument("--text", required=True)
    remember.add_argument("--summary")
    remember.add_argument("--kind", choices=("semantic", "relational", "opinion"), default="semantic")
    remember.add_argument("--session-id")
    remember.add_argument("--tag", action="append", default=[])
    remember.add_argument("--entity", action="append", default=[])
    remember.add_argument("--importance", type=float, default=0.8)
    remember.add_argument("--confidence", type=float, default=0.9)
    remember.add_argument("--stability", choices=("low", "medium", "high"), default="medium")
    remember.add_argument("--format", choices=("pretty", "json"), default="pretty")
    remember.set_defaults(func=cmd_remember)

    list_cmd = subparsers.add_parser("list", help="List memories previously saved through the VaultMind skill.")
    list_cmd.add_argument("--limit", type=int, default=20)
    list_cmd.add_argument("--tag", action="append", default=[])
    list_cmd.add_argument("--entity", action="append", default=[])
    list_cmd.add_argument("--query")
    list_cmd.add_argument("--format", choices=("pretty", "json"), default="pretty")
    list_cmd.set_defaults(func=cmd_list)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
