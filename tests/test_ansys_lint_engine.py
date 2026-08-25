"""Engine unit tests for the ANSYS Script & Journal Linter.

Covers detection scoring, provenance integrity, Fluent version packs,
MAPDL structure, Workbench nested SendCommand coordinate mapping, CCL
balance rules, ICEM Tcl structure, System Coupling checks and shared
portability rules. Everything runs offline and deterministically.
"""

from __future__ import annotations

import pytest

from ansys_lint import LintOptions, ExecMode, Strictness, TargetOS
from ansys_lint.api import lint_text
from ansys_lint.detection import AUTO_THRESHOLD, detect
from ansys_lint.sources import ProvenanceError, all_sources, get_source
from ansys_lint.dialects.fluent import (
    load_tui_catalog,
    load_version_pack,
    normalize_set_tui_value,
    supported_versions,
)


# ---------------------------------------------------------------------------
# Provenance integrity: every shipped catalog reference must resolve.
# ---------------------------------------------------------------------------


def test_sources_registry_loads_and_is_official_only():
    sources = all_sources()
    assert len(sources) >= 30
    for ref in sources:
        assert ref.url.startswith("https://ansyshelp.ansys.com/") or "ansys" in ref.url.lower()
        assert ref.title
        assert ref.release


def test_unknown_source_id_raises():
    with pytest.raises(ProvenanceError):
        get_source("definitely-not-a-source")


def test_fluent_catalog_provenance_ids_exist():
    source_id = load_tui_catalog()["source_id"]
    get_source(source_id)  # must not raise
    get_source("ansys-mapdl-command-reference-25r2")
    get_source("ansys-sysc-reference-25r2")


# ---------------------------------------------------------------------------
# Fluent version packs.
# ---------------------------------------------------------------------------


def test_fluent_supported_versions_and_default():
    assert supported_versions() == ("24.2", "25.1", "25.2", "26.1")
    assert load_version_pack()["default_version"] == "25.2"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("25.2", "25.2"),
        ("24.2", "24.2"),
        ("2025 R2", "25.2"),
        ("26.1", "26.1"),
        ("23.0", None),
        ("garbage", None),
    ],
)
def test_normalize_set_tui_value(raw, expected):
    assert normalize_set_tui_value(raw) == expected


def test_fluent_version_missing_diagnostic():
    result = lint_text(
        "/file/read-case a.cas.h5\n/exit yes\n",
        file_name="job.jou",
        options=LintOptions(),
    )
    codes = {d.code for d in result.diagnostics}
    assert "FLUENT_VERSION_MISSING" in codes


def test_fluent_version_unsupported_diagnostic():
    result = lint_text(
        "/file/set-tui-version 23.0\n/exit yes\n",
        file_name="job.jou",
        options=LintOptions(),
    )
    codes = {d.code for d in result.diagnostics}
    assert "FLUENT_VERSION_UNSUPPORTED" in codes


def test_fluent_gui_in_headless_and_bare_exit():
    text = "/file/set-tui-version 25.2\n/display/set/picture\n/exit\n"
    result = lint_text(text, file_name="job.jou", options=LintOptions())
    by_code = {}
    for diag in result.diagnostics:
        by_code.setdefault(diag.code, []).append(diag)
    assert "FLUENT_GUI_IN_HEADLESS" in by_code
    bare = by_code["FLUENT_INTERACTIVE_PROMPT"][0]
    assert "yes" in bare.suggested_fix


def test_fluent_interactive_mode_suppresses_gui_warning():
    text = "/file/set-tui-version 25.2\n/display/set/picture\n/exit yes\n"
    options = LintOptions(exec_mode=ExecMode.INTERACTIVE)
    result = lint_text(text, file_name="job.jou", options=options)
    assert all(d.code != "FLUENT_GUI_IN_HEADLESS" for d in result.diagnostics)


def test_fluent_shell_escape_detected():
    text = "!rm -rf /tmp/x\n"
    result = lint_text(text, file_name="j.jou", options=LintOptions(dialect_override="fluent"))
    assert any(d.code == "SECURITY_EXTERNAL_PROCESS" for d in result.diagnostics)


def test_fluent_no_output_after_solve():
    text = "/file/set-tui-version 25.2\n/file/read-case a.cas.h5\n/solve/iterate 10\n/exit yes\n"
    result = lint_text(text, file_name="j.jou", options=LintOptions(dialect_override="fluent"))
    assert any(d.code == "FLUENT_NO_OUTPUT" for d in result.diagnostics)


def test_fluent_scheme_paren_balance():
    text = '/file/set-tui-version 25.2\n(define (f x)\n  (display x)\n'
    result = lint_text(text, file_name="j.jou", options=LintOptions(dialect_override="fluent"))
    assert any(d.code == "SCHEME_UNBALANCED_PARENS" for d in result.diagnostics)


def test_fluent_windows_path_under_linux_target():
    text = '/file/set-tui-version 25.2\n/file/read-case "C:\\\\data\\\\case.cas.h5"\n'
    result = lint_text(
        text,
        file_name="j.jou",
        options=LintOptions(target_os=TargetOS.LINUX),
    )
    assert any(d.code == "PORTABILITY_WINDOWS_PATH" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# MAPDL.
# ---------------------------------------------------------------------------


def test_mapdl_case_insensitive_commands():
    text = "/prep7\net,1,SOLID186\nfinish\n"
    result = lint_text(text, file_name="m.dat", options=LintOptions(dialect_override="mapdl"))
    unknown = [d for d in result.diagnostics if d.code == "MAPDL_UNKNOWN_COMMAND"]
    assert not unknown


def test_mapdl_slash_alias_not_flagged():
    text = "PREP7\nET,1,SOLID186\nFINISH\n"
    result = lint_text(text, file_name="m.dat", options=LintOptions(dialect_override="mapdl"))
    assert not [d for d in result.diagnostics if d.code == "MAPDL_UNKNOWN_COMMAND"]


def test_mapdl_unknown_command_strict_vs_lenient():
    text = "NOTACOMMAND,1\n"
    lenient = lint_text(
        text, file_name="m.dat", options=LintOptions(dialect_override="mapdl", strictness=Strictness.LENIENT)
    )
    strict = lint_text(
        text, file_name="m.dat", options=LintOptions(dialect_override="mapdl", strictness=Strictness.STRICT)
    )
    lenient_codes = [d.severity.value for d in lenient.diagnostics if d.code == "MAPDL_UNKNOWN_COMMAND"]
    strict_codes = [d.severity.value for d in strict.diagnostics if d.code == "MAPDL_UNKNOWN_COMMAND"]
    assert lenient_codes == ["info"]
    assert strict_codes == ["warning"]


def test_mapdl_unbalanced_do_block():
    text = "*DO,I,1,5\nE,1\n"
    result = lint_text(text, file_name="m.dat", options=LintOptions(dialect_override="mapdl"))
    unbalanced = [d for d in result.diagnostics if d.code == "MAPDL_UNBALANCED_DO"]
    assert len(unbalanced) == 1
    assert unbalanced[0].severity.value == "error"


def test_mapdl_stray_endif():
    text = "*ENDIF\n"
    result = lint_text(text, file_name="m.dat", options=LintOptions(dialect_override="mapdl"))
    assert any(d.code == "MAPDL_UNBALANCED_IF" and d.severity.value == "error" for d in result.diagnostics)


def test_mapdl_processor_context_warning():
    text = "/POST1\nET,1,SOLID186\n"
    result = lint_text(text, file_name="m.dat", options=LintOptions(dialect_override="mapdl"))
    assert any(d.code == "MAPDL_PROCESSOR_CONTEXT" for d in result.diagnostics)


def test_mapdl_sys_security():
    text = "/SYS,cp big.file /tmp\n"
    result = lint_text(text, file_name="m.dat", options=LintOptions(dialect_override="mapdl"))
    assert any(d.code == "SECURITY_EXTERNAL_PROCESS" for d in result.diagnostics)


def test_mapdl_python_embedded_block_syntax_error():
    text = "*PYTHON\ndef broken(:\n*ENDPY\n"
    result = lint_text(text, file_name="m.dat", options=LintOptions(dialect_override="mapdl"))
    assert any(d.code == "PYTHON_SYNTAX_ERROR" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Workbench nested SendCommand + coordinate mapping.
# ---------------------------------------------------------------------------

WB_TUI_SOURCE = (
    '# SetScriptVersion(Version="25.2")\n'          # line 1
    'template = GetTemplate(Template="FLUENT")\n'   # line 2
    'system = CreateSystem(template)\n'             # line 3
    'setup = system.GetContainer(ComponentName="Setup")\n'  # line 4
    'setup.SendCommand(\n'                          # line 5
    '    Command="/file/set-tui-version 25.2\\n/file/read-case C:\\\\bad\\\\case.cas.h5"\n'  # line 6
    ')\n'                                           # line 7
)


def test_workbench_nested_diagnostics_map_to_outer_line():
    options = LintOptions(target_os=TargetOS.LINUX)
    result = lint_text(WB_TUI_SOURCE, file_name="job.wbjn", options=options)
    path_hits = [
        d for d in result.diagnostics if d.code == "PORTABILITY_WINDOWS_PATH"
    ]
    assert path_hits, "embedded Windows path must be detected"
    mapped = path_hits[0]
    assert mapped.line is not None
    # The literal lives on outer line 6; the inner content's second line maps there.
    assert mapped.line == 6
    assert "outer line 5" in (mapped.explanation or mapped.message or "")


def test_workbench_container_resolution_via_propagation():
    options = LintOptions()
    result = lint_text(WB_TUI_SOURCE, file_name="job.wbjn", options=options)
    # If container tracking failed, we would see WB_EMBEDDED_LANGUAGE_UNKNOWN.
    assert not any(d.code == "WB_EMBEDDED_LANGUAGE_UNKNOWN" for d in result.diagnostics)


def test_workbench_apdl_sniffing_beats_tui_prefixes():
    source = (
        'tpl = GetTemplate(Template="Mechanical APDL")\n'
        'sys1 = CreateSystem(tpl)\n'
        'c = sys1.GetContainer(ComponentName="Setup")\n'
        'c.SendCommand(Command="/PREP7\\nET,1,SOLID186\\nFINISH")\n'
    )
    options = LintOptions()
    result = lint_text(source, file_name="job.wbjn", options=options)
    fluent_noise = [d for d in result.diagnostics if d.code == "FLUENT_TUI_UNKNOWN"]
    assert not fluent_noise


def test_workbench_outer_syntax_error():
    result = lint_text("def broken(:\n", file_name="job.wbjn", options=LintOptions())
    assert any(d.code == "WB_PYTHON_SYNTAX" for d in result.diagnostics)


def test_workbench_edit_in_batch_warns():
    source = 'Edit(projects[0])\n'
    options = LintOptions(exec_mode=ExecMode.BATCH)
    result = lint_text(source, file_name="j.wbjn", options=options)
    assert any(d.code == "WB_INTERACTIVE_EDIT" for d in result.diagnostics)


def test_workbench_runwb2_batch_flag_check():
    source = "# journal body\nSave(Overwrite=True)\n"
    options = LintOptions(launch_command="runwb2 -R job.wbjn", exec_mode=ExecMode.BATCH)
    result = lint_text(source, file_name="job.wbjn", options=options)
    assert any(d.code == "WB_BATCH_FLAG_MISSING" for d in result.diagnostics)

    ok_options = LintOptions(launch_command="runwb2 -B -R job.wbjn", exec_mode=ExecMode.BATCH)
    ok_result = lint_text(source, file_name="job.wbjn", options=ok_options)
    assert not any(d.code == "WB_BATCH_FLAG_MISSING" for d in ok_result.diagnostics)


def test_workbench_version_mismatch_note():
    source = 'SetScriptVersion(Version="24.2")\nSave(Overwrite=True)\n'
    options = LintOptions(target_version="25.2")
    result = lint_text(source, file_name="job.wbjn", options=options)
    assert any(d.code == "WB_VERSION_MISMATCH" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# CCL family.
# ---------------------------------------------------------------------------


def test_ccl_unterminated_object_exact_lines():
    text = "LIBRARY:\n  MATERIAL: Air\n    Density = 1.2\n"
    from ansys_lint.dialects.ccl import lint as ccl_lint

    diags = ccl_lint(text, LintOptions(), file_path="state.ccl", product="cfx", kind="state")
    unterminated = [d for d in diags if d.code == "CCL_UNTERMINATED_OBJECT"]
    assert {d.line for d in unterminated} == {1, 2}


def test_ccl_stray_end():
    text = "LIBRARY:\nEND\nEND\n"
    from ansys_lint.dialects.ccl import lint as ccl_lint

    diags = ccl_lint(text, LintOptions(), file_path="s.ccl", product="cfx", kind="state")
    assert any(d.code == "CCL_UNEXPECTED_END" and d.line == 3 for d in diags)


def test_turbogrid_batch_quit_missing():
    text = "COMMAND FILE:\n>load filename=a.tse\nEND\n"
    from ansys_lint.dialects.ccl import lint as ccl_lint

    diags = ccl_lint(
        text, LintOptions(), file_path="run.tse", product="turbo-grid", kind="session"
    )
    assert any(d.code == "TURBOGRID_BATCH_QUIT_MISSING" for d in diags)


def test_turbogrid_session_with_quit_clean():
    text = "COMMAND FILE:\n>load filename=a.tse\nEND\n>quit\n"
    from ansys_lint.dialects.ccl import lint as ccl_lint

    diags = ccl_lint(
        text, LintOptions(), file_path="run.tse", product="turbo-grid", kind="session"
    )
    assert not [d for d in diags if d.code == "TURBOGRID_BATCH_QUIT_MISSING"]


def test_cel_unbalanced_parens():
    text = "LIBRARY:\n  X = sqrt((1+2)\nEND\n"
    from ansys_lint.dialects.ccl import lint as ccl_lint

    diags = ccl_lint(text, LintOptions(), file_path="s.ccl", product="cfx", kind="state")
    assert any(d.code == "CEL_UNBALANCED_PARENS" for d in diags)


def test_cfdpost_session_quit_info_when_batch():
    text = "COMMAND FILE:\n>load filename=a.res\nEND\n"
    from ansys_lint.dialects.ccl import lint as ccl_lint

    diags = ccl_lint(
        text,
        LintOptions(exec_mode=ExecMode.BATCH),
        file_path="s.cse",
        product="cfd-post",
        kind="session",
    )
    assert any(d.code == "SESSION_QUIT_MISSING" for d in diags)


# ---------------------------------------------------------------------------
# ICEM replay (Tcl).
# ---------------------------------------------------------------------------


def test_icem_known_commands_pass():
    text = "ic_point pnt.001 0 0 0\nic_part p\n"
    from ansys_lint.dialects.icem import lint as icem_lint

    diags = icem_lint(text, LintOptions(), file_path="a.rpl")
    assert not [d for d in diags if d.code in ("ICEM_UNDOCUMENTED_COMMAND", "TCL_UNKNOWN_COMMAND")]


def test_icem_undocumented_command_flagged():
    text = "ic_hex_mesh b1\n"
    from ansys_lint.dialects.icem import lint as icem_lint

    diags = icem_lint(text, LintOptions(), file_path="a.rpl")
    assert any(d.code == "ICEM_UNDOCUMENTED_COMMAND" for d in diags)


def test_icem_exec_security():
    text = "exec rm -rf x\n"
    from ansys_lint.dialects.icem import lint as icem_lint

    diags = icem_lint(text, LintOptions(), file_path="a.rpl")
    assert any(d.code == "SECURITY_EXTERNAL_PROCESS" for d in diags)


def test_icem_unclosed_brace_structural_error():
    text = "foreach i {1 2 {\nputs $i\n"
    from ansys_lint.dialects.icem import lint as icem_lint

    diags = icem_lint(text, LintOptions(), file_path="a.rpl")
    assert any(d.code == "TCL_UNCLOSED_BRACE" and d.severity.value == "error" for d in diags)


def test_icem_undo_pairing():
    text = "ic_undo_begin\nic_point p1 0 0 0\n"
    from ansys_lint.dialects.icem import lint as icem_lint

    diags = icem_lint(text, LintOptions(), file_path="a.rpl")
    assert any(d.code == "ICEM_UNDO_SECTION_OPEN" for d in diags)


# ---------------------------------------------------------------------------
# System Coupling.
# ---------------------------------------------------------------------------


def test_sysc_valid_script_minimal_findings():
    text = (
        "p1 = coupling.AddParticipant(ParticipantType=\"FLUENT\", ParticipantPath=\"case.cas.h5\")\n"
        "coupling.Solve()\n"
    )
    options = LintOptions(target_os=TargetOS.LINUX)
    result = lint_text(text, file_name="run.py", options=options)
    blocking = [d for d in result.diagnostics if d.severity.value in ("error",)]
    assert not blocking


def test_sysc_allocation_invalid():
    text = (
        "a.ParticipantFraction = 0.6\n"
        "b.ParticipantFraction = 0.3\n"
        "coupling.AddParticipant()\n"
        "coupling.Solve()\n"
    )
    result = lint_text(text, file_name="run.py", options=LintOptions())
    invalid = [d for d in result.diagnostics if d.code == "SYSTEM_COUPLING_ALLOCATION_INVALID"]
    assert len(invalid) == 1
    assert invalid[0].severity.value == "error"
    assert invalid[0].is_heuristic is False


def test_sysc_missing_solve_warning():
    text = "coupling.AddParticipant()\ncoupling.Initialize()\n"
    result = lint_text(text, file_name="run.py", options=LintOptions())
    assert any(d.code == "SYSTEM_COUPLING_MISSING_SOLVE" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Detection registry behaviour.
# ---------------------------------------------------------------------------


def test_detection_generic_python_stays_uncertain():
    outcome = detect("script.py", "import os\nprint('hi')\n")
    assert outcome.confidence < AUTO_THRESHOLD
    assert outcome.dialect in ("__generic_python__",) or outcome.confidence < AUTO_THRESHOLD


def test_detection_jou_extension_confident():
    outcome = detect("job.jou", "/file/read-case a.cas.h5\n")
    assert outcome.dialect == "fluent"
    assert outcome.confidence >= AUTO_THRESHOLD


def test_detection_wbjn_signature():
    outcome = detect("job.wbjn", "t = GetTemplate(Template=\"FLUENT\")\nt.Update()\n")
    assert outcome.dialect == "workbench"
    assert outcome.confidence >= AUTO_THRESHOLD


def test_detection_dat_needs_signatures():
    plain = detect("notes.dat", "hello world\nnothing here\n")
    assert plain.confidence < AUTO_THRESHOLD
    apdl = detect("model.dat", "/PREP7\nET,1,SOLID186\nVMESH,ALL\nFINISH\nSOLVE\n")
    assert apdl.confidence >= AUTO_THRESHOLD
    assert apdl.dialect == "mapdl"


def test_detection_launch_command_boost():
    outcome = detect("input.txt", "/PREP7\nET,1,SOLID186\n", launch_command="mapdl -b -i input.txt")
    assert outcome.dialect == "mapdl"


# ---------------------------------------------------------------------------
# Remaining products: structural coverage smoke tests.
# ---------------------------------------------------------------------------


def test_motion_xml_wellformedness_line_col():
    text = "<?xml version=\"1.0\"?>\n<Journal>\n</Journal\n"
    from ansys_lint.dialects.motion import lint as motion_lint

    diags = motion_lint(text, LintOptions(), file_path="a.dfjnl")
    malformed = [d for d in diags if d.code == "MOTION_XML_MALFORMED"]
    assert len(malformed) == 1
    assert malformed[0].line == 3
    assert malformed[0].is_heuristic is False


def test_aedt_com_dependency_linux_target():
    text = "import win32com.client\noDesktop = win32com.client.Dispatch('Ansoft.ElectronicsDesktop')\noProject = oDesktop.NewProject()\noDesign = oProject.Design\n"
    from ansys_lint.dialects.aedt import lint as aedt_lint

    diags = aedt_lint(text, LintOptions(target_os=TargetOS.LINUX), file_path="s.py", kind="python")
    assert any(d.code == "PORTABILITY_COM_DEPENDENCY" for d in diags)


def test_vbscript_block_pairing():
    text = "Sub Run\n  MsgBox \"hi\"\nFunction F(x)\n  F = x\nEnd Function\n"
    from ansys_lint.jscript import lint_vbscript

    diags = lint_vbscript(text, LintOptions(), file_path="a.vbs", product="aedt", dialect="aedt-vbscript")
    assert any(d.code == "VBS_UNBALANCED_BLOCK" for d in diags)


def test_designmodeler_header_and_agb_evidence():
    from ansys_lint.dialects.designmodeler import signature_score

    score, evidence = signature_score("model.js", "/* DesignModeler Script Version 25.2 */\nagb.BeginModelling();\nagb.EndModelling();")
    assert score >= AUTO_THRESHOLD - 0.05
    assert any("header" in e for e in evidence)


def test_shared_rules_windows_env_var():
    from ansys_lint.rules_common import scan_path_literal

    findings = scan_path_literal("%APPDATA%\\Ansys\\x", target_os=TargetOS.LINUX, line=1, column=1)
    codes = {f.code for f in findings}
    assert "PORTABILITY_WINDOWS_ENV_VAR" in codes
