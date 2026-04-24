import pandas as pd

from worklog_finance import calculate_finances, explode_proect_share_amounts, rollup_project_metric


def test_calculate_finances_empty_logs() -> None:
    logs = pd.DataFrame()
    rates = pd.DataFrame({"Sotrudnik": ["A"], "Rate": [100], "Client_Rate": [200]})
    out = calculate_finances(logs, rates)
    assert out.empty


def test_calculate_finances_merges_and_profit() -> None:
    logs = pd.DataFrame(
        {
            "Date": ["2026-01-01"],
            "Sotrudnik": [" Ivan "],
            "Proect": ["P1"],
            "Time": [10],
        }
    )
    rates = pd.DataFrame({"Sotrudnik": ["Ivan"], "Rate": [100], "Client_Rate": [250]})
    out = calculate_finances(logs, rates)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["Revenue"] == 2500
    assert row["Cost"] == 1000
    assert row["Profit"] == 1500


def test_explode_proect_splits_profit_evenly() -> None:
    df = pd.DataFrame({"Proect": ["A, B", "C"], "Profit": [100.0, 60.0]})
    out = explode_proect_share_amounts(df, amount_cols=("Profit",))
    assert len(out) == 3
    by = out.groupby("Proect")["Profit"].sum()
    assert by["A"] == 50
    assert by["B"] == 50
    assert by["C"] == 60


def test_rollup_project_metric_top_n_other() -> None:
    df = pd.DataFrame({"Proect": [f"P{i}" for i in range(5)], "Profit": [10, 20, 30, 40, 50.0]})
    out = rollup_project_metric(df, "Profit", top_n=3)
    assert len(out) == 4
    proech = out[out["Proect"].str.startswith("Прочее")]
    assert len(proech) == 1
    assert proech["Profit"].iloc[0] == 30.0
