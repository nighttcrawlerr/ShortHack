#!/usr/bin/env python3
"""Собирает конфигурацию машины для Yandex Cloud.

Содержимое файлов кладётся в base64. Это не украшение: утилита yc
подставляет переменные окружения в содержимое файла метаданных, и любой
доллар в тексте превращается в пустую строку. Так ломается и скрипт
установки, и настройка nginx, где $host и $scheme — часть синтаксиса.
В base64 подставлять нечего.
"""
import argparse
import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

ENV_KEYS = [
    "GIT_REPO", "LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_FOLDER_ID",
    "LLM_MODEL", "LLM_TOOLS", "LLM_TIMEOUT", "LLM_FALLBACK_TO_MOCK",
    "EMBEDDINGS_PROVIDER", "VERIFY_WITH_MODEL", "AUTO_SEND",
]

DEFAULTS = {
    "GIT_REPO": "https://github.com/nighttcrawlerr/ShortHack",
    "LLM_PROVIDER": "mock",
    "LLM_BASE_URL": "",
    "LLM_API_KEY": "",
    "LLM_FOLDER_ID": "",
    "LLM_MODEL": "yandexgpt-5-pro",
    "LLM_TOOLS": "auto",
    "LLM_TIMEOUT": "60",
    "LLM_FALLBACK_TO_MOCK": "true",
    "EMBEDDINGS_PROVIDER": "auto",
    "VERIFY_WITH_MODEL": "true",
    "AUTO_SEND": "true",
}


def b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def read_env(path: Path) -> dict:
    values = dict(DEFAULTS)
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in ENV_KEYS:
            values[key.strip()] = value.strip()
    return values


def build(env: dict, ssh_key: str) -> str:
    env_sh = "\n".join(f"{key}={env[key]}" for key in ENV_KEYS) + "\n"

    files = [
        ("/opt/saluteagent/env.sh", "0600", env_sh),
        ("/etc/systemd/system/saluteagent.service", "0644",
         (HERE / "files" / "saluteagent.service").read_text(encoding="utf-8")),
        ("/etc/nginx/sites-available/saluteagent", "0644",
         (HERE / "files" / "nginx.conf").read_text(encoding="utf-8")),
        ("/opt/saluteagent/install.sh", "0755",
         (HERE / "files" / "install.sh").read_text(encoding="utf-8")),
    ]

    lines = [
        "#cloud-config",
        "users:",
        "  - name: pilot",
        "    groups: sudo",
        "    shell: /bin/bash",
        "    sudo: ['ALL=(ALL) NOPASSWD:ALL']",
        "    ssh_authorized_keys:",
        f"      - {json.dumps(ssh_key)}",
        "",
        "package_update: true",
        "packages:",
        "  - python3-venv",
        "  - python3-pip",
        "  - git",
        "  - nginx",
        "  - curl",
        "",
        "write_files:",
    ]
    for path, mode, content in files:
        lines += [
            f"  - path: {path}",
            f"    permissions: '{mode}'",
            "    encoding: b64",
            f"    content: {b64(content)}",
        ]
    lines += [
        "",
        "runcmd:",
        "  - bash /opt/saluteagent/install.sh 2>&1 | tee /var/log/saluteagent-install.log",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=str(HERE.parent / "backend" / ".env"))
    parser.add_argument("--ssh-key", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    env = read_env(Path(args.env))
    ssh_key = Path(args.ssh_key).read_text(encoding="utf-8").strip()
    Path(args.out).write_text(build(env, ssh_key), encoding="utf-8")

    mode = "живая модель" if env["LLM_API_KEY"] else "демонстрационный режим"
    print(f"Конфигурация собрана: {env['LLM_MODEL']}, {mode}")


if __name__ == "__main__":
    main()
