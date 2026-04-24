import pandas as pd

from worklog_import_db import validate_data


def test_validate_data_splits_clean_and_bad() -> None:
    df = pd.DataFrame(
        {
            "Дата": ["2026-03-01", "not-a-date", "2026-03-03"],
            "Сотрудник": ["Anna", "Boris", None],
            "Часы": [8, 4, "x"],
        }
    )
    clean, bad = validate_data(df, "Дата", "Сотрудник", "Часы")
    assert len(clean) == 1
    assert clean.iloc[0]["Сотрудник"] == "Anna"
    assert len(bad) == 2
