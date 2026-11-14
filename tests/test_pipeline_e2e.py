from decodematrimony.pipeline import main


def test_pipeline_no_db(tmp_path, raw_frame, monkeypatch):
    f = tmp_path / "fixture.csv"
    raw_frame.to_csv(f, index=False)
    monkeypatch.setenv("DM_N_BOOT", "40")
    monkeypatch.setenv("DM_OUT_DIR", str(tmp_path / "out"))
    assert main(["--dhs", str(f), "--year", "2017", "--no-db"]) == 0
    assert (tmp_path / "out" / "results.csv").exists()
    assert (tmp_path / "out" / "missingness_report.csv").exists()
    assert (tmp_path / "out" / "run_summary.json").exists()


def test_pipeline_reads_stata_file(tmp_path, raw_frame, monkeypatch):
    f = tmp_path / "fixture.dta"
    raw_frame.to_stata(f, write_index=False)
    monkeypatch.setenv("DM_N_BOOT", "40")
    monkeypatch.setenv("DM_OUT_DIR", str(tmp_path / "out"))
    assert main(["--dhs", str(f), "--year", "2017", "--no-db"]) == 0


def test_pipeline_refuses_synthetic_named_files(tmp_path, raw_frame):
    f = tmp_path / "synthetic_couples.csv"
    raw_frame.to_csv(f, index=False)
    assert main(["--dhs", str(f), "--year", "2017", "--no-db"]) == 2
