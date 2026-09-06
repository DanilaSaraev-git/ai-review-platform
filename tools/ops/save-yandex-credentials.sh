#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

credentials_dir="${XDG_CONFIG_HOME:-$HOME/.config}/ai-analytics-review"
mkdir -p "$credentials_dir"
chmod 700 "$credentials_dir"

read -r -p 'ID каталога Yandex Cloud: ' yandex_folder_id
if [[ ! "$yandex_folder_id" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  printf 'Некорректный ID каталога; файлы не изменены.\n' >&2
  exit 1
fi
read -r -s -p 'API-ключ (ввод скрыт): ' yandex_api_key
printf '\n'
if [[ -z "$yandex_api_key" || "$yandex_api_key" =~ [[:space:]] ]]; then
  printf 'Ключ пустой или содержит пробелы; файлы не изменены.\n' >&2
  exit 1
fi

printf '%s\n' "$yandex_folder_id" > "$credentials_dir/yandex.folder-id"
printf '%s' "$yandex_api_key" > "$credentials_dir/yandex.token"
chmod 600 "$credentials_dir/yandex.folder-id" "$credentials_dir/yandex.token"
unset yandex_api_key
printf 'ID каталога и ключ сохранены в %s. Ключ не выводится.\n' "$credentials_dir"
