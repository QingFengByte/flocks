from pathlib import Path

from flocks.cli import service_manager


def test_runtime_paths_follow_flocks_root_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLOCKS_ROOT", str(tmp_path))

    paths = service_manager.runtime_paths()

    assert paths.run_dir == tmp_path / "run"
    assert paths.log_dir == tmp_path / "logs"
    assert paths.backend_pid == tmp_path / "run" / "backend.pid"
    assert paths.frontend_log == tmp_path / "logs" / "webui.log"


def test_cleanup_stale_pid_file_removes_dead_pid(tmp_path: Path) -> None:
    pid_file = tmp_path / "backend.pid"
    pid_file.write_text("999999", encoding="utf-8")

    service_manager.cleanup_stale_pid_file(pid_file)

    assert not pid_file.exists()


def test_selected_log_paths_support_specific_targets(tmp_path: Path) -> None:
    paths = service_manager.RuntimePaths(
        root=tmp_path,
        run_dir=tmp_path / "run",
        log_dir=tmp_path / "logs",
        backend_pid=tmp_path / "run" / "backend.pid",
        frontend_pid=tmp_path / "run" / "webui.pid",
        backend_log=tmp_path / "logs" / "backend.log",
        frontend_log=tmp_path / "logs" / "webui.log",
    )

    assert service_manager.selected_log_paths(paths, backend=True) == [paths.backend_log]
    assert service_manager.selected_log_paths(paths, webui=True) == [paths.frontend_log]
    assert service_manager.selected_log_paths(paths) == [paths.backend_log, paths.frontend_log]


def test_tail_lines_returns_recent_content(tmp_path: Path) -> None:
    log_file = tmp_path / "backend.log"
    log_file.write_text("a\nb\nc\n", encoding="utf-8")

    assert service_manager.tail_lines(log_file, 2) == ["b", "c"]


def test_parse_windows_netstat_output_extracts_unique_pids() -> None:
    output = """
  TCP    127.0.0.1:8000       0.0.0.0:0              LISTENING       1234
  TCP    127.0.0.1:8000       0.0.0.0:0              LISTENING       1234
  TCP    127.0.0.1:5173       0.0.0.0:0              LISTENING       5678
"""

    assert service_manager._parse_windows_netstat_output(output) == [1234, 5678]


def test_build_status_lines_reports_running_and_idle_services(monkeypatch, tmp_path: Path) -> None:
    paths = service_manager.RuntimePaths(
        root=tmp_path,
        run_dir=tmp_path / "run",
        log_dir=tmp_path / "logs",
        backend_pid=tmp_path / "run" / "backend.pid",
        frontend_pid=tmp_path / "run" / "webui.pid",
        backend_log=tmp_path / "logs" / "backend.log",
        frontend_log=tmp_path / "logs" / "webui.log",
    )
    paths.run_dir.mkdir(parents=True)
    paths.log_dir.mkdir(parents=True)
    paths.backend_pid.write_text("111", encoding="utf-8")
    paths.frontend_pid.write_text("222", encoding="utf-8")

    monkeypatch.setattr(service_manager, "cleanup_stale_pid_file", lambda _: None)
    monkeypatch.setattr(
        service_manager,
        "port_owner_pids",
        lambda port: [111] if port == 8000 else [],
    )
    monkeypatch.setattr(service_manager, "pid_is_running", lambda pid: pid == 222)

    lines = service_manager.build_status_lines(service_manager.ServiceConfig(), paths)

    assert "后端运行中" in lines[0]
    assert "WebUI 主进程仍在运行" in lines[1]


def test_build_status_lines_uses_custom_server_and_webui_ports(monkeypatch, tmp_path: Path) -> None:
    paths = service_manager.RuntimePaths(
        root=tmp_path,
        run_dir=tmp_path / "run",
        log_dir=tmp_path / "logs",
        backend_pid=tmp_path / "run" / "backend.pid",
        frontend_pid=tmp_path / "run" / "webui.pid",
        backend_log=tmp_path / "logs" / "backend.log",
        frontend_log=tmp_path / "logs" / "webui.log",
    )
    paths.run_dir.mkdir(parents=True)
    paths.log_dir.mkdir(parents=True)

    monkeypatch.setattr(service_manager, "cleanup_stale_pid_file", lambda _: None)
    monkeypatch.setattr(
        service_manager,
        "port_owner_pids",
        lambda port: [111] if port in {9000, 5174} else [],
    )
    monkeypatch.setattr(service_manager, "pid_is_running", lambda _pid: False)

    config = service_manager.ServiceConfig(
        backend_host="0.0.0.0",
        backend_port=9000,
        frontend_host="0.0.0.0",
        frontend_port=5174,
    )
    lines = service_manager.build_status_lines(config, paths)

    assert "http://127.0.0.1:9000" in lines[0]
    assert "http://127.0.0.1:5174" in lines[1]


def test_start_all_stops_services_before_starting(monkeypatch) -> None:
    call_order: list[str] = []

    monkeypatch.setattr(service_manager, "stop_all", lambda _config, _console: call_order.append("stop_all"))
    monkeypatch.setattr(
        service_manager,
        "ensure_runtime_dirs",
        lambda: call_order.append("ensure_runtime_dirs"),
    )
    monkeypatch.setattr(service_manager, "start_backend", lambda _config, _console: call_order.append("start_backend"))
    monkeypatch.setattr(service_manager, "start_frontend", lambda _config, _console: call_order.append("start_frontend"))
    monkeypatch.setattr(
        service_manager,
        "show_start_summary",
        lambda _config, _console: call_order.append("show_start_summary"),
    )
    monkeypatch.setattr(
        service_manager,
        "open_default_browser",
        lambda _url, _console: call_order.append("open_default_browser"),
    )

    service_manager.start_all(service_manager.ServiceConfig(), console=None)

    assert call_order == [
        "stop_all",
        "ensure_runtime_dirs",
        "start_backend",
        "start_frontend",
        "show_start_summary",
        "open_default_browser",
    ]


def test_restart_all_reuses_start_all_flow(monkeypatch) -> None:
    captured = {}

    def fake_start_all(config, console) -> None:
        captured["config"] = config
        captured["console"] = console

    monkeypatch.setattr(service_manager, "start_all", fake_start_all)

    config = service_manager.ServiceConfig(no_browser=True, skip_frontend_build=True)
    console = object()
    service_manager.restart_all(config, console)

    assert captured == {"config": config, "console": console}
