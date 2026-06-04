#!/usr/bin/env python3
"""Build a public RFM segmentation portfolio case from Online Retail II."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", ".matplotlib-cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


SEGMENT_ACTIONS = {
    "Champions": {
        "business_interpretation": "Recent, frequent, high-value customers.",
        "suggested_action": "Protect relationship quality and prioritise retention offers.",
        "reporting_use": "Track as the core high-value active customer group.",
    },
    "Loyal Customers": {
        "business_interpretation": "Frequent customers with solid purchase value.",
        "suggested_action": "Use targeted cross-sell and loyalty communications.",
        "reporting_use": "Monitor repeat purchase behaviour and revenue contribution.",
    },
    "Potential Loyalists": {
        "business_interpretation": "Recently active customers with room to grow.",
        "suggested_action": "Nurture with onboarding, recommendations, and follow-up.",
        "reporting_use": "Track conversion into higher-frequency segments.",
    },
    "At Risk": {
        "business_interpretation": "Historically valuable customers with weaker recent activity.",
        "suggested_action": "Prioritise win-back and reactivation campaigns.",
        "reporting_use": "Monitor revenue at risk and reactivation opportunity.",
    },
    "Hibernating": {
        "business_interpretation": "Low recent activity and limited current engagement.",
        "suggested_action": "Use low-cost automated reactivation or suppress from high-touch actions.",
        "reporting_use": "Separate low-priority customers from active commercial segments.",
    },
    "Low Value": {
        "business_interpretation": "Low frequency and low monetary contribution.",
        "suggested_action": "Use automated, low-cost communication and monitor for change.",
        "reporting_use": "Keep visible in reporting without over-allocating manual effort.",
    },
}

SEGMENT_COLORS = {
    "Champions": "#1F77B4",
    "Loyal Customers": "#2CA02C",
    "Potential Loyalists": "#17BECF",
    "At Risk": "#FF7F0E",
    "Hibernating": "#8C8C8C",
    "Low Value": "#BDBDBD",
}

SEGMENT_PRIORITIES = {
    "Champions": "Retain",
    "Loyal Customers": "Grow",
    "Potential Loyalists": "Grow",
    "At Risk": "Reactivate",
    "Hibernating": "Low-touch",
    "Low Value": "Low-touch",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RFM customer segmentation on the UCI Online Retail II dataset."
    )
    parser.add_argument(
        "--input",
        default="data/raw/online_retail_II.xlsx",
        help="Path to the Online Retail II Excel file.",
    )
    parser.add_argument(
        "--outputs-dir",
        default="outputs",
        help="Directory for generated CSV outputs.",
    )
    parser.add_argument(
        "--images-dir",
        default="images",
        help="Directory for generated chart images.",
    )
    return parser.parse_args()


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "Customer ID": "CustomerID",
        "Price": "UnitPrice",
    }
    return df.rename(columns=rename_map)


def load_online_retail(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}. "
            "Download online_retail_II.xlsx from UCI and place it in data/raw/."
        )

    sheets = pd.read_excel(path, sheet_name=None)
    frames = []
    for sheet_name, sheet in sheets.items():
        frame = normalise_columns(sheet)
        frame["source_sheet"] = sheet_name
        frames.append(frame)

    df = pd.concat(frames, ignore_index=True)
    expected = {"Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"}
    if "InvoiceNo" in df.columns:
        df = df.rename(columns={"InvoiceNo": "Invoice"})
    missing = expected.difference(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")

    return df


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["Invoice"] = cleaned["Invoice"].astype(str)
    cleaned["InvoiceDate"] = pd.to_datetime(cleaned["InvoiceDate"], errors="coerce")
    cleaned["Quantity"] = pd.to_numeric(cleaned["Quantity"], errors="coerce")
    cleaned["UnitPrice"] = pd.to_numeric(cleaned["UnitPrice"], errors="coerce")
    cleaned["CustomerID"] = pd.to_numeric(cleaned["CustomerID"], errors="coerce")

    cleaned = cleaned.dropna(subset=["InvoiceDate", "CustomerID", "Quantity", "UnitPrice"])
    cleaned = cleaned[~cleaned["Invoice"].str.upper().str.startswith("C")]
    cleaned = cleaned[(cleaned["Quantity"] > 0) & (cleaned["UnitPrice"] > 0)]
    cleaned["CustomerID"] = cleaned["CustomerID"].astype(int)
    cleaned["Revenue"] = cleaned["Quantity"] * cleaned["UnitPrice"]
    return cleaned


def build_data_cleaning_summary(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    working["Invoice"] = working["Invoice"].astype(str)
    working["InvoiceDate"] = pd.to_datetime(working["InvoiceDate"], errors="coerce")
    working["Quantity"] = pd.to_numeric(working["Quantity"], errors="coerce")
    working["UnitPrice"] = pd.to_numeric(working["UnitPrice"], errors="coerce")
    working["CustomerID"] = pd.to_numeric(working["CustomerID"], errors="coerce")

    rows = []

    def add_step(step: str, before: int, after: int, note: str) -> None:
        rows.append(
            {
                "step": step,
                "rows_before": before,
                "rows_after": after,
                "rows_removed": before - after,
                "note": note,
            }
        )

    before = len(working)
    rows.append(
        {
            "step": "raw_rows",
            "rows_before": before,
            "rows_after": before,
            "rows_removed": 0,
            "note": "All rows loaded from the Online Retail II workbook.",
        }
    )

    after_df = working.dropna(subset=["InvoiceDate", "CustomerID", "Quantity", "UnitPrice"])
    add_step(
        "remove_missing_required_fields",
        before,
        len(after_df),
        "Remove rows missing invoice date, customer id, quantity, or unit price.",
    )
    working = after_df
    before = len(working)

    after_df = working[~working["Invoice"].str.upper().str.startswith("C")]
    add_step("remove_cancellations", before, len(after_df), "Remove cancellation invoices beginning with C.")
    working = after_df
    before = len(working)

    after_df = working[working["Quantity"] > 0]
    add_step("remove_non_positive_quantity", before, len(after_df), "Remove returns or invalid quantity rows.")
    working = after_df
    before = len(working)

    after_df = working[working["UnitPrice"] > 0]
    add_step("remove_non_positive_unit_price", before, len(after_df), "Remove rows without positive unit price.")

    return pd.DataFrame(rows)


def score_rfm(cleaned: pd.DataFrame) -> pd.DataFrame:
    analysis_date = cleaned["InvoiceDate"].max() + pd.Timedelta(days=1)
    rfm = (
        cleaned.groupby("CustomerID")
        .agg(
            last_purchase_date=("InvoiceDate", "max"),
            Recency=("InvoiceDate", lambda x: (analysis_date - x.max()).days),
            Frequency=("Invoice", "nunique"),
            Monetary=("Revenue", "sum"),
            order_lines=("Invoice", "size"),
            country=("Country", lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"),
        )
        .reset_index()
    )

    rfm["R_Score"] = pd.qcut(rfm["Recency"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["F_Score"] = pd.qcut(rfm["Frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["M_Score"] = pd.qcut(rfm["Monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["RFM_Score"] = (
        rfm["R_Score"].astype(str) + rfm["F_Score"].astype(str) + rfm["M_Score"].astype(str)
    )
    rfm["Segment"] = rfm.apply(assign_segment, axis=1)
    return rfm


def assign_segment(row: pd.Series) -> str:
    r, f, m = row["R_Score"], row["F_Score"], row["M_Score"]
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if f >= 4 and m >= 3:
        return "Loyal Customers"
    if r >= 4 and f >= 2 and m >= 2:
        return "Potential Loyalists"
    if r <= 2 and m >= 4:
        return "At Risk"
    if r <= 2 and f <= 2:
        return "Hibernating"
    return "Low Value"


def build_segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rfm.groupby("Segment")
        .agg(
            customer_count=("CustomerID", "nunique"),
            total_revenue=("Monetary", "sum"),
            avg_recency_days=("Recency", "mean"),
            avg_frequency=("Frequency", "mean"),
            avg_monetary=("Monetary", "mean"),
        )
        .reset_index()
    )
    summary["customer_share"] = summary["customer_count"] / summary["customer_count"].sum()
    summary["revenue_share"] = summary["total_revenue"] / summary["total_revenue"].sum()
    summary = summary.sort_values("total_revenue", ascending=False)
    ordered_cols = [
        "Segment",
        "customer_count",
        "customer_share",
        "total_revenue",
        "revenue_share",
        "avg_recency_days",
        "avg_frequency",
        "avg_monetary",
    ]
    return summary[ordered_cols]


def build_action_table(segment_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for segment in segment_summary["Segment"]:
        action = SEGMENT_ACTIONS[segment]
        rows.append({"Segment": segment, **action})
    return pd.DataFrame(rows)


def build_metric_definitions() -> pd.DataFrame:
    rows = [
        {
            "metric": "Revenue",
            "definition": "Quantity * UnitPrice",
            "grain": "Transaction line",
            "notes": "Calculated after removing cancellations, missing customer IDs, and non-positive values.",
        },
        {
            "metric": "Analysis Date",
            "definition": "max(InvoiceDate) + 1 day",
            "grain": "Dataset",
            "notes": "Used as the reference date for recency calculation.",
        },
        {
            "metric": "Recency",
            "definition": "Analysis Date - latest purchase date",
            "grain": "Customer",
            "notes": "Lower values mean more recent activity.",
        },
        {
            "metric": "Frequency",
            "definition": "Count distinct Invoice",
            "grain": "Customer",
            "notes": "Counts unique invoices, not order lines.",
        },
        {
            "metric": "Monetary",
            "definition": "Sum Revenue",
            "grain": "Customer",
            "notes": "Total cleaned revenue attributed to each customer.",
        },
        {
            "metric": "R/F/M Scores",
            "definition": "Quintile scores from Recency, Frequency, and Monetary",
            "grain": "Customer",
            "notes": "Recency is reverse-scored so more recent customers receive higher R scores.",
        },
        {
            "metric": "Segment",
            "definition": "Business-readable grouping from R/F/M score combinations",
            "grain": "Customer",
            "notes": "Designed for portfolio reporting and interpretability, not as a final CRM production model.",
        },
    ]
    return pd.DataFrame(rows)


def save_outputs(
    data_cleaning_summary: pd.DataFrame,
    metric_definitions: pd.DataFrame,
    segment_summary: pd.DataFrame,
    action_table: pd.DataFrame,
    rfm: pd.DataFrame,
    outputs_dir: Path,
) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    data_cleaning_summary.to_csv(outputs_dir / "data_cleaning_summary.csv", index=False)
    metric_definitions.to_csv(outputs_dir / "metric_definitions.csv", index=False)
    segment_summary.to_csv(outputs_dir / "customer_segment_summary.csv", index=False, float_format="%.4f")
    action_table.to_csv(outputs_dir / "segment_action_table.csv", index=False)
    rfm[["CustomerID", "Recency", "Frequency", "Monetary", "Segment"]].to_csv(
        outputs_dir / "rfm_customers.csv", index=False, float_format="%.2f"
    )


def save_executive_summary(segment_summary: pd.DataFrame, outputs_dir: Path) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    top = segment_summary.iloc[0]
    hibernating = segment_summary[segment_summary["Segment"] == "Hibernating"].iloc[0]
    at_risk = segment_summary[segment_summary["Segment"] == "At Risk"].iloc[0]
    potential = segment_summary[segment_summary["Segment"] == "Potential Loyalists"].iloc[0]
    memo = f"""# Executive Insight Memo

## Business Question

How can online retail transaction history be converted into practical customer groups for commercial prioritisation, retention planning, and recurring stakeholder reporting?

## Key Result

The RFM segmentation highlights a strong concentration of revenue in the most active high-value customer group. {top['Segment']} represent {top['customer_share']:.1%} of customers but contribute {top['revenue_share']:.1%} of cleaned revenue.

## Recommended Actions

1. Protect Champions through retention monitoring, service quality checks, and high-priority commercial follow-up.
2. Grow Potential Loyalists through onboarding and targeted recommendations because they are recent customers with lower average frequency.
3. Review At Risk customers for reactivation because they have weak recent activity but relatively high average monetary value.
4. Keep Hibernating and Low Value customers visible in reporting, but use lower-cost automated follow-up rather than high-touch manual service.

## Reporting Notes

- Customer-level outputs are not published in this repository.
- Public outputs are aggregated by segment.
- Segment definitions are designed for business interpretability and portfolio demonstration.
- The analysis identifies prioritisation opportunities; it does not measure campaign lift or prove causal business impact.

## Supporting Metrics

| Segment | Customer Share | Revenue Share | Avg Recency Days | Avg Frequency |
|---|---:|---:|---:|---:|
| {top['Segment']} | {top['customer_share']:.1%} | {top['revenue_share']:.1%} | {top['avg_recency_days']:.1f} | {top['avg_frequency']:.1f} |
| {potential['Segment']} | {potential['customer_share']:.1%} | {potential['revenue_share']:.1%} | {potential['avg_recency_days']:.1f} | {potential['avg_frequency']:.1f} |
| {at_risk['Segment']} | {at_risk['customer_share']:.1%} | {at_risk['revenue_share']:.1%} | {at_risk['avg_recency_days']:.1f} | {at_risk['avg_frequency']:.1f} |
| {hibernating['Segment']} | {hibernating['customer_share']:.1%} | {hibernating['revenue_share']:.1%} | {hibernating['avg_recency_days']:.1f} | {hibernating['avg_frequency']:.1f} |
"""
    (outputs_dir / "executive_summary.md").write_text(memo, encoding="utf-8")


def format_axis_as_percent(ax, axis: str = "y") -> None:
    import matplotlib.ticker as mtick

    formatter = mtick.PercentFormatter(1.0)
    if axis == "y":
        ax.yaxis.set_major_formatter(formatter)
    else:
        ax.xaxis.set_major_formatter(formatter)


def polish_axis(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def save_charts(rfm: pd.DataFrame, segment_summary: pd.DataFrame, images_dir: Path) -> None:
    images_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    ordered = segment_summary["Segment"].tolist()
    plot_data = segment_summary.set_index("Segment").loc[ordered]
    colors = [SEGMENT_COLORS[segment] for segment in ordered]

    fig, ax = plt.subplots(figsize=(11, 6))
    x_positions = range(len(plot_data))
    bar_width = 0.36
    customer_bars = ax.bar(
        [x - bar_width / 2 for x in x_positions],
        plot_data["customer_share"],
        width=bar_width,
        color="#6BAED6",
        label="Customer share",
    )
    revenue_bars = ax.bar(
        [x + bar_width / 2 for x in x_positions],
        plot_data["revenue_share"],
        width=bar_width,
        color="#F58518",
        label="Revenue share",
    )
    format_axis_as_percent(ax)
    ax.set_title("Champions Are 22% of Customers and 68% of Revenue", fontsize=14, weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Share of total")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(plot_data.index, rotation=25, ha="right")
    ax.legend(frameon=False, loc="upper right")
    for bars in [customer_bars, revenue_bars]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.1%}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    polish_axis(ax)
    fig.tight_layout()
    fig.savefig(images_dir / "rfm_customer_revenue_mix.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    bubble_sizes = (plot_data["revenue_share"] * 4200).clip(lower=130)
    ax.scatter(
        plot_data["avg_recency_days"],
        plot_data["avg_frequency"],
        s=bubble_sizes,
        alpha=0.72,
        color=colors,
        edgecolor="#333333",
        linewidth=0.8,
    )
    label_offsets = {
        "Champions": (28, -12),
        "Loyal Customers": (10, 8),
        "Potential Loyalists": (10, 8),
        "At Risk": (10, 8),
        "Hibernating": (10, 8),
        "Low Value": (12, 16),
    }
    for segment, row in plot_data.iterrows():
        priority = SEGMENT_PRIORITIES[segment]
        offset = label_offsets.get(segment, (8, 8))
        ax.annotate(
            f"{segment}\n{priority}",
            (row["avg_recency_days"], row["avg_frequency"]),
            xytext=offset,
            textcoords="offset points",
            fontsize=8.5,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 1.5},
        )
    ax.axvline(plot_data["avg_recency_days"].median(), color="#666666", linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(plot_data["avg_frequency"].median(), color="#666666", linestyle="--", linewidth=1, alpha=0.6)
    ax.set_title("Segment Priority Matrix: Recency, Frequency, and Revenue Weight", fontsize=13, weight="bold")
    ax.set_xlabel("Average recency in days (lower is more recent)")
    ax.set_ylabel("Average unique invoices")
    ax.set_xlim(-6, plot_data["avg_recency_days"].max() * 1.12)
    ax.set_ylim(0.4, plot_data["avg_frequency"].max() * 1.13)
    ax.grid(alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(images_dir / "rfm_priority_matrix.png", dpi=180)
    plt.close(fig)

    action_data = plot_data.copy()
    action_data["priority"] = [SEGMENT_PRIORITIES[segment] for segment in action_data.index]
    action_data = action_data.sort_values("revenue_share", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 5.8))
    y_positions = range(len(action_data))
    bars = ax.barh(
        list(y_positions),
        action_data["revenue_share"],
        color=[SEGMENT_COLORS[segment] for segment in action_data.index],
        alpha=0.9,
    )
    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(action_data.index)
    format_axis_as_percent(ax, axis="x")
    ax.set_xlabel("Share of revenue")
    ax.set_title("Recommended Commercial Action by Segment", fontsize=13, weight="bold")
    for i, (segment, row) in enumerate(action_data.iterrows()):
        ax.annotate(
            f"{row['revenue_share']:.1%} | {row['priority']}",
            xy=(row["revenue_share"], i),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
        )
    ax.set_xlim(0, max(action_data["revenue_share"]) * 1.28)
    ax.grid(False)
    ax.xaxis.grid(True, alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    fig.tight_layout()
    fig.savefig(images_dir / "rfm_action_priority.png", dpi=180)
    plt.close(fig)



def print_summary(segment_summary: pd.DataFrame) -> None:
    display_cols = ["Segment", "customer_count", "customer_share", "total_revenue", "revenue_share"]
    print(segment_summary[display_cols].to_string(index=False, float_format=lambda x: f"{x:,.4f}"))


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    outputs_dir = Path(args.outputs_dir)
    images_dir = Path(args.images_dir)

    raw = load_online_retail(input_path)
    data_cleaning_summary = build_data_cleaning_summary(raw)
    cleaned = clean_transactions(raw)
    rfm = score_rfm(cleaned)
    metric_definitions = build_metric_definitions()
    segment_summary = build_segment_summary(rfm)
    action_table = build_action_table(segment_summary)

    save_outputs(data_cleaning_summary, metric_definitions, segment_summary, action_table, rfm, outputs_dir)
    save_executive_summary(segment_summary, outputs_dir)
    save_charts(rfm, segment_summary, images_dir)
    print_summary(segment_summary)


if __name__ == "__main__":
    main()
