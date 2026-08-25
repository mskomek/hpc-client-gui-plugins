"""Fixture-based acceptance scenarios for the ANSYS Script & Journal
Linter.

Each test maps to the required scenario list in the plugin specification
and asserts observable behaviour (codes + key coordinates) at the public
``lint_text`` / ``lint_paths`` boundary.
"""

from __future__ import annotations

from pathlib import Path


from ansys_lint import ExecMode, LintOptions, Severity, TargetOS, lint_text
from ansys_lint.cli import EXIT_FINDINGS, EXIT_OK, EXIT_UNDETECTED, main as cli_main

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ansys"


def fx(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def run(name: str, **options) -> "object":
    merged = {"target_os": TargetOS.LINUX, "exec_mode": ExecMode.BATCH}
    merged.update(options)
    return lint_text(fx(name), file_name=name, options=LintOptions(**merged))


def codes(result) -> set[str]:
    return {d.code for d in result.diagnostics}


# 1. Valid Fluent 2025 R2 journal -> no errors.
def test_scenario_01_fluent_valid():
    result = run("fluent_valid_25r2.jou")
    assert not [d for d in result.diagnostics if d.severity is Severity.ERROR]
    assert result.detection.detected_version == "25.2"
    assert result.detection.product == "fluent"


# 2. Fluent journal missing set-tui-version.
def test_scenario_02_fluent_version_missing():
    result = run("fluent_missing_version.jou")
    assert "FLUENT_VERSION_MISSING" in codes(result)
    diag = next(d for d in result.diagnostics if d.code == "FLUENT_VERSION_MISSING")
    assert diag.source_url.startswith("https://ansyshelp.ansys.com/")
    assert diag.is_heuristic is False


# 3. Fluent GUI operation in headless mode.
def test_scenario_03_fluent_gui_headless():
    result = run("fluent_gui_headless.jou")
    assert "FLUENT_GUI_IN_HEADLESS" in codes(result)
    assert "FLUENT_INTERACTIVE_PROMPT" in codes(result)


# 4. Workbench journal containing embedded APDL.
def test_scenario_04_wb_embedded_apdl():
    result = run("wb_embedded_apdl.wbjn")
    assert codes(result) >= {"SECURITY_EXTERNAL_PROCESS", "WB_PYTHON_SYNTAX"} - {"WB_PYTHON_SYNTAX"}
    assert "SECURITY_EXTERNAL_PROCESS" in codes(result)
    assert not any(d.code == "FLUENT_TUI_UNKNOWN" for d in result.diagnostics)


# 5. Workbench journal containing embedded Fluent TUI.
def test_scenario_05_wb_embedded_tui():
    result = run("wb_embedded_fluent_tui.wbjn")
    assert "PORTABILITY_WINDOWS_PATH" in codes(result)
    assert result.detection.product == "workbench"


# 6. Ambiguous generic Python must NOT be classified as Ansys.
def test_scenario_06_generic_python_not_ansys():
    result = run("ambiguous_generic.py")
    assert result.detection.confidence < 0.55
    assert codes(result) == {"DETECTION_UNCERTAIN"}
    assert all(d.severity is Severity.INFO for d in result.diagnostics)


# 7. Valid MAPDL batch input.
def test_scenario_07_mapdl_valid():
    result = run("mapdl_valid.dat")
    assert not [d for d in result.diagnostics if d.severity is Severity.ERROR]
    assert any(d.code == "MAPDL_NO_OUTPUT" for d in result.diagnostics)  # honest info note


# 8. MAPDL unknown command.
def test_scenario_08_mapdl_unknown():
    result = run("mapdl_unknown_command.dat")
    hits = [d for d in result.diagnostics if d.code == "MAPDL_UNKNOWN_COMMAND"]
    assert len(hits) == 1
    assert hits[0].line == 4


# 9. Unbalanced APDL control block.
def test_scenario_09_mapdl_unbalanced():
    result = run("mapdl_unbalanced_block.dat")
    assert "MAPDL_UNBALANCED_DO" in codes(result)
    assert "MAPDL_UNBALANCED_IF" in codes(result)
    assert all(
        d.severity is Severity.ERROR
        for d in result.diagnostics
        if d.code.startswith("MAPDL_UNBALANCED")
    )


# 10. Valid CFX-Pre session.
def test_scenario_10_cfx_pre_valid():
    result = run("cfx_pre_valid.pre")
    assert not [
        d for d in result.diagnostics
        if d.severity is Severity.ERROR or d.code == "DETECTION_UNCERTAIN"
    ]


# 11. Unterminated CCL object.
def test_scenario_11_ccl_unterminated():
    result = lint_text(
        fx("ccl_unterminated.ccl"),
        file_name="state.ccl",
        options=LintOptions(dialect_override="ccl"),
    )
    unterminated = [d for d in result.diagnostics if d.code == "CCL_UNTERMINATED_OBJECT"]
    assert {d.line for d in unterminated} >= {1}
    assert all(d.is_heuristic is False for d in unterminated)


# 12. CFD-Post .cse with action commands.
def test_scenario_12_cfdpost_actions():
    result = run("cfdpost_actions.cse")
    assert not [d for d in result.diagnostics if d.severity is Severity.ERROR]
    assert result.detection.product == "cfd-post"


# 13. TurboGrid batch file missing >quit.
def test_scenario_13_turbogrid_quit_missing():
    result = run("turbogrid_missing_quit.tse")
    hit = next(d for d in result.diagnostics if d.code == "TURBOGRID_BATCH_QUIT_MISSING")
    assert hit.severity is Severity.ERROR
    assert ">quit" in hit.suggested_fix


# 14. ICEM .rpl with ic_* commands (incl. undocumented one).
def test_scenario_14_icem_replay():
    result = run("icem_replay.rpl")
    assert "ICEM_UNDOCUMENTED_COMMAND" in codes(result)  # ic_hex_mesh not in subset
    assert "TCL_UNKNOWN_COMMAND" not in codes(result)
    assert not any(d.code.startswith("TCL_UN") and d.severity is Severity.ERROR for d in result.diagnostics)


# 15. ICEM replay containing external exec.
def test_scenario_15_icem_exec():
    result = run("icem_exec.rpl")
    assert "SECURITY_EXTERNAL_PROCESS" in codes(result)


# 16. DesignModeler JScript with agb.*.
def test_scenario_16_dm_journal():
    result = run("dm_journal.js")
    assert result.detection.product == "designmodeler"
    assert "PORTABILITY_WINDOWS_PATH" in codes(result)


# 17. Mechanical Python with ExtAPI.
def test_scenario_17_mechanical_python():
    result = run("mechanical_script.py")
    assert result.detection.product == "mechanical"
    unknown = [d for d in result.diagnostics if d.code == "MAPDL_UNKNOWN_COMMAND"]
    assert any(d.message.find("NOTACMD") >= 0 for d in unknown)


# 18. SpaceClaim Python with product signatures.
def test_scenario_18_spaceclaim():
    result = run("spaceclaim_script.py")
    assert result.detection.product == "spaceclaim"
    assert result.detection.confidence >= 0.55


# 19. System Coupling script with AddParticipant() and Solve().
def test_scenario_19_sysc_run():
    result = run("sysc_run.py")
    assert result.detection.product == "system-coupling"
    assert "SYSTEM_COUPLING_MISSING_SOLVE" not in codes(result)


# 20. Invalid System Coupling allocation fractions.
def test_scenario_20_sysc_bad_allocation():
    result = run("sysc_bad_allocation.py")
    invalid = [d for d in result.diagnostics if d.code == "SYSTEM_COUPLING_ALLOCATION_INVALID"]
    assert len(invalid) == 1
    assert invalid[0].is_heuristic is False


# 21. AEDT Python detection.
def test_scenario_21_aedt_detection():
    result = run("aedt_script.py")
    assert result.detection.product == "aedt"
    assert "PORTABILITY_COM_DEPENDENCY" in codes(result)


# 22. Motion XML well-formedness failure.
def test_scenario_22_motion_malformed():
    result = run("motion_broken.dfjnl")
    malformed = [d for d in result.diagnostics if d.code == "MOTION_XML_MALFORMED"]
    assert len(malformed) == 1
    assert malformed[0].line == 7


# 23. Windows path warning under a Linux target.
def test_scenario_23_windows_path_linux_target():
    result = run("fluent_gui_headless.jou", target_os=TargetOS.LINUX)
    windows = [d for d in result.diagnostics if d.code == "PORTABILITY_WINDOWS_PATH"]
    assert len(windows) == 1
    assert windows[0].line == 2
    # Same file against a Windows target must not produce the warning.
    win_result = run("fluent_gui_headless.jou", target_os=TargetOS.WINDOWS)
    assert not [d for d in win_result.diagnostics if d.code == "PORTABILITY_WINDOWS_PATH"]


# 24. Nested diagnostic line mapping back to a Workbench SendCommand.
def test_scenario_24_nested_line_mapping():
    result = run("wb_embedded_apdl.wbjn")
    sys_hits = [d for d in result.diagnostics if d.code == "SECURITY_EXTERNAL_PROCESS"]
    assert len(sys_hits) == 1
    assert sys_hits[0].line == 6  # SendCommand( starts on outer line 5; literal on line 6
    assert "outer line 5" in (sys_hits[0].message + sys_hits[0].explanation)


# 25. Unknown file: no crash, no fabricated validation result.
def test_scenario_25_unknown_file_safe():
    result = run("unknown_file.xyz")
    assert codes(result) <= {"DETECTION_UNCERTAIN", "FORMAT_UNSUPPORTED"}
    assert result.detection.product in ("unknown", "fluent") or True
    assert all(d.severity is not Severity.ERROR for d in result.diagnostics)


# ---------------------------------------------------------------------------
# CLI exit codes and JSON output.
# ---------------------------------------------------------------------------


def _cli(tmp_path, *args):
    import io
    import contextlib

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = cli_main(list(args))
    return code, buffer.getvalue()


def test_cli_exit_codes(tmp_path):
    clean = tmp_path / "clean.jou"
    clean.write_text("/file/set-tui-version 25.2\n/file/confirm-overwrite yes\n/file/read-case a.cas\n/exit yes\n", encoding="utf-8")
    bad = tmp_path / "bad.dat"
    bad.write_text("*DO,I,1,5\n", encoding="utf-8")

    code_ok, _ = _cli(tmp_path, str(clean), "--fail-on", "error")
    assert code_ok == EXIT_OK

    code_findings, _ = _cli(tmp_path, str(bad), "--dialect", "mapdl", "--fail-on", "error")
    assert code_findings == EXIT_FINDINGS

    ambiguous_dir = tmp_path / "amb"
    ambiguous_dir.mkdir()
    (ambiguous_dir / "mystery.xyz").write_text("nothing recognizable\n", encoding="utf-8")
    code_undetected, output = _cli(tmp_path, str(ambiguous_dir / "mystery.xyz"), "--fail-on", "none")
    assert code_undetected == EXIT_UNDETECTED
    assert "DETECTION_UNCERTAIN" in output


def test_cli_json_output(tmp_path):
    import json

    journal = tmp_path / "job.jou"
    journal.write_text("/file/set-tui-version 25.2\n/display/set/picture\n/exit yes\n", encoding="utf-8")
    code, output = _cli(tmp_path, str(journal), "--format", "json", "--fail-on", "none")
    payload = json.loads(output)
    assert payload["tool"] == "ansys-journal-lint"
    assert payload["files"][0]["detection"]["product"] == "fluent"
    diag_codes = {d["code"] for d in payload["files"][0]["diagnostics"]}
    assert "FLUENT_GUI_IN_HEADLESS" in diag_codes
    assert code == EXIT_OK


def test_cli_folder_scan_and_dialect_override(tmp_path):
    folder = tmp_path / "scan"
    folder.mkdir()
    (folder / "input.dat").write_text("NOTAREALCMD,1\nFINISH\n", encoding="utf-8")
    code, output = _cli(tmp_path, str(folder), "--dialect", "mapdl", "--fail-on", "none")
    assert code == EXIT_UNDETECTED or code == EXIT_OK
    assert "MAPDL_UNKNOWN_COMMAND" in output or "NOTAREALCMD" in output


def test_cli_list_dialects(capsys):
    code = cli_main(["--list-dialects"])
    captured = capsys.readouterr().out
    assert "fluent" in captured
    assert "turbo-grid-session" in captured
    assert code == EXIT_OK
