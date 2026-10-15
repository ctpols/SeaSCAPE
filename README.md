<img width="1981" height="682" alt="SeaSCAPE_workflow" src="https://github.com/user-attachments/assets/4fd72d74-37d0-4df2-bdde-0d41a0b662ee" />

**SeaSCAPE Toolbox: Seabed Shipwreck Classification Assessment and Preservation Evaluation**

An open-source ArcGIS Pro toolbox for the automated detection and structural preservation assessment of shipwreck sites from high-resolution bathymetric survey data.

---

## Overview

SeaSCAPE implements a two-stage ModelBuilder workflow that takes a single bathymetric raster and produces classified shipwreck detections with preservation scores:

**Stage 1 — Derivative Generation**
Generates six terrain derivatives from the input bathymetry: slope, curvature, TPI (Topographic Position Index), roughness, resampled bathymetry, and Broad-Scale BPI (Bathymetric Position Index).

**Stage 2 — Detection & Evaluation**
Reclassifies the derivatives using Jenks Natural Breaks, applies a variable-threshold detection system that adjusts sensitivity by seabed complexity zone, converts detections to polygons, scores each on five confidence criteria, determines the orientation of each detection, performs cluster analysis to characterise structural fragmentation, and assigns a four-class preservation classification:

| Class | Label          | Score Range | Description |
|-------|----------------|-------------|-------------|
| 1     | Intact         | 8–10        | Structurally continuous wreck signal |
| 2     | Broken         | 5–7         | Distinct sections separated but dominant structure remains |
| 3     | Fragmented     | 2–4         | Many small clusters with no dominant structural core |
| 4     | Indeterminate  | 1           | Below resolution gate — insufficient spatial information |

## Requirements

- **ArcGIS Pro** 3.x
- **Extensions**: Spatial Analyst, 3D Analyst, Image Analyst
- **Python packages**: `scipy` (for MST cluster analysis — included with ArcGIS Pro's conda environment)
- **Input data**: Bathymetric raster in a projected coordinate system with metres in X, Y, and Z at 1 m resolution

## Installation

1. Download or clone this repository
2. In ArcGIS Pro, open the **Catalog Pane**
3. Right-click **Toolboxes** → **Add Toolbox**
4. Navigate to the downloaded folder and select `SeaSCAPE.atbx`

Once opened as tools in ArcGIS, both workflow stages will provide additional information about each parameter and default settings. 


## Repository Structure

```
SeaSCAPE/
├── SeaSCAPE.zip                       # ArcGIS Pro toolbox (unzip this and add the .abtx file to your project)
├── scripts/                           # Python script tools
│   ├── CalculateBroadBPI.py           # Broad-Scale Bathymetric Position Index
│   ├── CalculateTPI.py                # Topographic Position Index
│   ├── ClusterAnalysisTool.py         # MST-based cluster analysis and gap measurement
│   ├── DetectionExport.py             # Export detections to full and simplified outputs
│   ├── NormaliseMetrics.py            # Min-max normalisation of preservation metrics
│   ├── PreservationClassification.py  # Four-class preservation classification
│   └── VariableThresholdDetection.py  # Zone-based adaptive threshold detection
├── README.md
├── LICENSE
├── CITATION.cff
└── .gitignore
```

## Usage

### Quick Start

1. Add the toolbox to your ArcGIS Pro project
2. Run **Stage 1 — Derivative Generation** with your bathymetric raster
3. Run **Stage 2 — Detection & Evaluation** using the outputs from Stage 1
4. The final output is a polygon feature class with confidence scores (`Confidence`), orientation (`Bearing'), and preservation classifications (`Pres_Class`, `Pres_Index`)

### Custom Script Tools

The seven Python scripts in `scripts/` can also be run independently from the ArcGIS Pro geoprocessing pane:

| Script | Purpose |
|--------|---------|
| `CalculateBroadBPI.py` | Broad-Scale BPI using annular focal neighbourhood (Lundblad et al., 2006; Walbridge et al., 2018) |
| `CalculateTPI.py` | TPI using circular focal neighbourhood (Weiss, 2001; Jenness, 2006; Dilts, 2015) |
| `VariableThresholdDetection.py` | Three-zone adaptive detection with configurable thresholds |
| `ClusterAnalysisTool.py` | Cluster merging, area statistics, dominance, and MST-based MaxGap |
| `NormaliseMetrics.py` | Min-max normalisation of R_mean, R_std, CV_wreck |
| `PreservationClassification.py` | Four-class preservation scheme with composite scoring |
| `DetectionExport.py` | Export to full and simplified feature classes |

### Default Parameters

Detection and classification thresholds have sensible defaults calibrated to 1 m bathymetric data across 12 survey regions in the English Channel. All thresholds are exposed as adjustable parameters for calibration to different environments or resolutions.

Key defaults:
- **Detection thresholds**: High zone = 15, Medium zone = 13, Low zone = 12
- **Buffer distances**: Positive = 30 m, Negative = −15 m
- **Gap threshold**: 5 m (structural separation distance)
- **Dominance threshold**: 0.3 (ratio of largest cluster area to total)
- **Resolution gate**: 50 m (minimum polygon perimeter length)
- **BPI annulus**: Inner = 50 cells, Outer = 500 cells (at 5 m resampled resolution)
- **TPI radius**: 30 cells (at 1 m resolution)

## Citation

If you use SeaSCAPE in your research, please cite:

> Pols, C.T. (2026). SeaSCAPE: Seabed Shipwreck Classification Assessment and Preservation Evaluation [Software]. https://github.com/ctpols/SeaSCAPE

A `CITATION.cff` file is included for automated citation tools. GitHub displays a "Cite this repository" button on the repository page.

## Acknowledgements

This research is funded by the **Leverhulme Trust** through the **Southampton Marine and Maritime Institute (SMMI)**, Intelligence Oceans programme, University of Southampton.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
