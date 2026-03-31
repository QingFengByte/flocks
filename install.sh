#!/usr/bin/env bash

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

REPO_SLUG="${FLOCKS_REPO_SLUG:-AgentFlocks/Flocks}"
DEFAULT_BRANCH="${FLOCKS_DEFAULT_BRANCH:-main}"
VERSION="${VERSION:-$DEFAULT_BRANCH}"
INSTALL_TUI=0
TMP_DIR=""
DEFAULT_INSTALL_DIR="${PWD%/}/flocks"
INSTALL_DIR="${FLOCKS_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"

info() {
  printf '[flocks-bootstrap] %s\n' "$1"
}

fail() {
  printf '[flocks-bootstrap] error: %s\n' "$1" >&2
  exit 1
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}

print_usage() {
  cat <<EOF
Usage: install.sh [--with-tui] [--version <tag-or-branch>]

Bootstrap installer for Flocks.
This script downloads the GitHub source archive, extracts it to a temporary
directory, copies it to a persistent install location, then delegates to
scripts/install.sh inside the repository. By default it creates a "flocks"
subdirectory under the current working directory.

Options:
  --with-tui, -t         Also install TUI dependencies.
  --version <value>      Install from a Git tag or branch. Defaults to: $DEFAULT_BRANCH
  --help, -h             Show this help message.

Environment variables:
  VERSION                Same as --version.
  FLOCKS_INSTALL_DIR     Override the persistent install location. Defaults to: $INSTALL_DIR
  FLOCKS_REPO_SLUG       Override GitHub repo, e.g. owner/repo.
  FLOCKS_DEFAULT_BRANCH  Override default branch. Defaults to: $DEFAULT_BRANCH
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --with-tui|-t)
        INSTALL_TUI=1
        ;;
      --version)
        [[ $# -ge 2 ]] || fail "--version 需要一个值。"
        VERSION="$2"
        shift
        ;;
      --help|-h)
        print_usage
        exit 0
        ;;
      *)
        print_usage
        fail "不支持的参数: $1"
        ;;
    esac
    shift
  done
}

ensure_dependencies() {
  has_cmd curl || fail "未检测到 curl，无法下载 GitHub 源码包。"
  has_cmd tar || fail "未检测到 tar，无法解压 GitHub 源码包。"
  has_cmd bash || fail "未检测到 bash，无法运行仓库内安装脚本。"
}

build_candidate_urls() {
  local repo_url_base="https://github.com/$REPO_SLUG/archive/refs"

  if [[ "$VERSION" == "$DEFAULT_BRANCH" ]]; then
    printf '%s\n' "$repo_url_base/heads/$VERSION.tar.gz"
    return 0
  fi

  printf '%s\n' "$repo_url_base/tags/$VERSION.tar.gz"
  printf '%s\n' "$repo_url_base/heads/$VERSION.tar.gz"
}

download_archive() {
  local archive_path="$1"
  local last_error=""
  local url=""

  while IFS= read -r url; do
    [[ -n "$url" ]] || continue
    info "尝试下载源码包: $url"
    if curl -fsSL "$url" -o "$archive_path"; then
      printf '%s' "$url"
      return 0
    fi
    last_error="$url"
  done < <(build_candidate_urls)

  fail "无法从 GitHub 下载版本 \"$VERSION\" 的源码包。最后一次尝试: ${last_error:-<none>}"
}

resolve_project_dir() {
  local candidate=""
  for candidate in "$TMP_DIR"/*; do
    [[ -d "$candidate" ]] || continue
    if [[ -f "$candidate/scripts/install.sh" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done

  return 1
}

main() {
  local archive_path download_url project_dir install_parent

  trap cleanup EXIT
  parse_args "$@"
  ensure_dependencies

  TMP_DIR="$(mktemp -d)"
  archive_path="$TMP_DIR/flocks.tar.gz"

  info "仓库: $REPO_SLUG"
  info "版本: $VERSION"
  info "临时目录: $TMP_DIR"
  download_url="$(download_archive "$archive_path")"

  info "解压源码包..."
  tar -xzf "$archive_path" -C "$TMP_DIR"

  project_dir="$(resolve_project_dir)" || fail "解压完成，但未找到 scripts/install.sh。"

  install_parent="$(dirname "$INSTALL_DIR")"
  mkdir -p "$install_parent"
  rm -rf "$INSTALL_DIR"
  cp -R "$project_dir" "$INSTALL_DIR"

  info "下载来源: $download_url"
  info "安装目录: $INSTALL_DIR"
  info "转调安装脚本: $INSTALL_DIR/scripts/install.sh"

  if [[ "$INSTALL_TUI" -eq 1 ]]; then
    bash "$INSTALL_DIR/scripts/install.sh" --with-tui
  else
    bash "$INSTALL_DIR/scripts/install.sh"
  fi
}

main "$@"
