from scripts.repo_checks import check_line_limits, scan_sensitive


def _write(path, n):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("linha\n" * n, encoding="utf-8")


def test_line_limits_ok_warning_and_error(tmp_path):
    _write(tmp_path / "CLAUDE.md", 100)
    _write(tmp_path / "docs/plan/STATUS.md", 101)
    errors, warnings = check_line_limits(tmp_path)
    assert errors == []
    assert len(warnings) == 1 and "STATUS.md" in warnings[0]

    _write(tmp_path / "CLAUDE.md", 151)
    errors, _ = check_line_limits(tmp_path)
    assert len(errors) == 1 and "CLAUDE.md" in errors[0]


def test_scan_sensitive_detects_personal_data(tmp_path):
    bad = tmp_path / "notas.md"
    # montado em tempo de execução para o próprio arquivo de teste não conter dados sensíveis
    cnpj = "11.222.333/" + "0001-81"
    email = "fulano@" + "gmail.com"
    key = "AIza" + "x" * 35
    bad.write_text(f"CNPJ {cnpj}\ncontato {email}\nchave {key}\n", encoding="utf-8")
    ok = tmp_path / "ok.md"
    ok.write_text("CNAE 85.92-9/99 e site https://scorpionbits.com\n", encoding="utf-8")
    findings = scan_sensitive([bad, ok], tmp_path)
    labels = " ".join(findings)
    assert "CNPJ" in labels and "e-mail pessoal" in labels and "chave de API" in labels
    assert all("ok.md" not in f for f in findings)
