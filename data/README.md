# Data Source

This public portfolio version uses the Online Retail II dataset from the UCI Machine Learning Repository:

- Dataset: Online Retail II
- Source: https://archive.ics.uci.edu/dataset/502/online+retail+ii
- Citation: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)

The original analysis workflow was inspired by private operational customer transaction analysis. This public version uses the UCI dataset to demonstrate the same customer segmentation method without exposing confidential business data.

## Download

Download `online_retail_II.xlsx` from the UCI page and place it here:

```text
data/raw/online_retail_II.xlsx
```

The raw Excel file is not committed to this repository because it is a large external dataset. The repository commits only scripts, aggregated outputs, and charts generated from the dataset.

## Privacy and Use

The public dataset uses numeric customer identifiers. It does not include direct personal contact details such as names, emails, phone numbers, addresses, or payment information.

This project does not attempt to identify individual customers. Public outputs are aggregated at segment level and are intended for portfolio demonstration of customer analytics, RFM segmentation, and decision-support reporting.

## Fields Used

| Field | Use |
|---|---|
| `InvoiceNo` | Transaction identifier and cancellation filtering |
| `InvoiceDate` | Recency calculation and analysis date |
| `Customer ID` / `CustomerID` | Customer-level aggregation |
| `Quantity` | Revenue calculation and invalid-row filtering |
| `Price` / `UnitPrice` | Revenue calculation and invalid-row filtering |
| `Country` | Optional reporting dimension |

## Cleaning Rules

- Remove rows without customer identifiers.
- Remove cancellation invoices where `InvoiceNo` starts with `C`.
- Remove rows with non-positive `Quantity`.
- Remove rows with non-positive unit price.
- Calculate `Revenue = Quantity * UnitPrice`.
- Use `max(InvoiceDate) + 1 day` as the analysis date.
