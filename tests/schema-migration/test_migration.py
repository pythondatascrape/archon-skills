from conftest import run


def mig(project, *args):
    return run("schema-migration", "migration.py", *args, "--dir", "migrations", cwd=project)


def test_new_takes_the_next_number(project):
    (project / "migrations").mkdir()
    (project / "migrations" / "0001_init.sql").write_text("")
    (project / "migrations" / "0002_users.sql").write_text("")
    r = mig(project, "new", "add audit log")
    assert r.returncode == 0 and r.stdout.strip() == "migrations/0003_add_audit_log.sql"
    assert (project / "migrations" / "0003_add_audit_log.sql").exists()


def test_new_in_an_empty_folder_starts_at_one(project):
    assert mig(project, "new", "init").stdout.strip() == "migrations/0001_init.sql"


def test_check_finds_gaps_duplicates_and_bad_names(project):
    d = project / "migrations"
    d.mkdir()
    for n in ("0001_a.sql", "0002_b.sql", "0002_c.sql", "0004_d.sql", "notes.sql"):
        (d / n).write_text("")
    r = mig(project, "check")
    assert r.returncode == 1
    assert "0002" in r.stdout and "0003" in r.stdout and "notes.sql" in r.stdout
    for n in ("0002_c.sql", "notes.sql"):
        (d / n).unlink()
    (d / "0003_c.sql").write_text("")
    assert mig(project, "check").returncode == 0


def test_name_format_is_configurable(project):
    r = mig(project, "new", "Init", "--format", "V{n}__{slug}.sql")
    assert r.stdout.strip() == "migrations/V1__init.sql"
    assert mig(project, "new", "users", "--format", "V{n}__{slug}.sql").stdout.strip() == "migrations/V2__users.sql"
