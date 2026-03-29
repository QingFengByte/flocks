"""
flocks update  — self-update CLI command
"""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def update_command(
    check: bool = typer.Option(False, "--check", help="仅检查是否有新版本，不执行升级"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认直接升级"),
):
    """
    Check for and upgrade Flocks to the latest version.

    Downloads the latest Release source archive from GitHub, backs up the
    current version to ~/.flocks/version/, extracts and replaces source files,
    re-syncs dependencies, then restarts the service automatically.
    """
    asyncio.run(_update(check=check, yes=yes))


async def _update(check: bool, yes: bool) -> None:
    from flocks.updater import check_update, perform_update, detect_deploy_mode

    with console.status("[cyan]正在检查版本...[/cyan]", spinner="dots"):
        info = await check_update()

    if info.error:
        console.print(f"[red]检查失败：{info.error}[/red]")
        raise typer.Exit(1)

    _print_version_table(info)

    if not info.has_update:
        console.print("[green]✓ 已是最新版本，无需升级[/green]")
        return

    if detect_deploy_mode() == "docker":
        console.print(
            "\n[yellow]Docker deployment detected. In-place upgrade is not available.\n"
            "Please pull the latest image and restart the container to upgrade:\n\n"
            "  [bold]docker pull ghcr.io/agentflocks/flocks:latest[/bold]\n"
            "  [bold]docker restart <container>[/bold][/yellow]"
        )
        return

    if check:
        console.print(f"\n[yellow]运行 [bold]flocks update[/bold] 执行升级[/yellow]")
        return

    if not yes:
        confirmed = typer.confirm("\n是否立即升级？", default=False)
        if not confirmed:
            console.print("[yellow]已取消[/yellow]")
            return

    console.print()
    stage_labels = {
        "fetching":    "下载最新源码包",
        "backing_up":  "备份当前版本",
        "applying":    f"应用 v{info.latest_version}",
        "syncing":     "同步依赖",
        "building":    "构建前端",
        "restarting":  "重启服务",
        "done":        "完成",
    }
    total_steps = 6
    seen_stages: set[str] = set()
    step = 0

    async for progress in perform_update(
        info.latest_version or "",
        zipball_url=info.zipball_url,
        tarball_url=info.tarball_url,
    ):
        if progress.stage == "error":
            console.print(f"\n[red]✗ 升级失败：{progress.message}[/red]")
            raise typer.Exit(1)

        if progress.stage in ("done",):
            continue

        if progress.stage not in seen_stages:
            seen_stages.add(progress.stage)
            step += 1
            label = stage_labels.get(progress.stage, progress.stage)
            if progress.stage == "restarting":
                console.print(f"[cyan][{step}/{total_steps}] {label}...[/cyan]")
            else:
                console.print(f"[cyan][{step}/{total_steps}] {label}...[/cyan]  ", end="")
                console.print("[green]✓[/green]")

    console.print("[green]升级完成[/green]")


def _print_version_table(info) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()

    table.add_row("当前版本", f"[bold]v{info.current_version}[/bold]")

    if info.latest_version:
        if info.has_update:
            latest_str = f"[bold green]v{info.latest_version}[/bold green]  [yellow]✨ 有新版本[/yellow]"
        else:
            latest_str = f"[bold]v{info.latest_version}[/bold]  [green]✓ 已是最新[/green]"
        table.add_row("最新版本", latest_str)

    console.print(table)

    if info.has_update and info.release_notes:
        notes = info.release_notes.strip()[:800]
        console.print(
            Panel(notes, title="发布说明", border_style="dim", padding=(0, 1))
        )
