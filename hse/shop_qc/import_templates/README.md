# Hose crimp chart import templates

Import with Frappe **Data Import** (search "New Data Import"), Import Type "Insert New Records".
Import the hose types first: each crimp spec row links to an existing Hose Type.

## hose_type_import_template.csv -> DocType "Hose Type"

| Column | Required | Notes |
|---|---|---|
| Hose Type | Yes | The manufacturer's hose code, exactly as it will be picked on the hose row. Unique. |
| Manufacturer | No | Defaults to Ryco. |
| Standard | No | e.g. SAE J517 100R2AT / EN 853 2SN |
| Description | No | |

## hose_crimp_spec_import_template.csv -> DocType "Hose Crimp Spec"

One row per hose type + dash size + fitting part number.

| Column | Required | Notes |
|---|---|---|
| Hose Type | Yes | Must match a Hose Type record. |
| Dash Size | Yes | 12, -12 or #12 (stored as -12). |
| Fitting Part Number | Yes | Full part number, as entered on the hose row. Spaces are removed and letters upper-cased for matching. |
| Crimp Diameter (in) | Yes | Measured ferrule OD after crimping, in inches. |
| Crimp Tolerance +/- (in) | No | Inches. |
| Die Size | No | |
| Source | No | Crimp chart or document name. |
| Source Rev | No | Revision of the source. |
| Notes | No | |

A duplicate hose type + dash size + fitting row is rejected. To change values later, edit the
existing record (or use Data Import "Update Existing Records" with the ID column from an export).

## How the chart is used

On a QC Unit hose row, when Hose Type, Dash Size and End A Fitting Part No. match an active
chart entry, the crimp diameter, tolerance and die size are filled from it and the entry is
linked in "Crimp Chart Entry". A manual override on the row is kept until one of those three
values changes. End B Fitting defaults to End A when left blank.
