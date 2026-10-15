"""
Variable Threshold Detection Tool
====================================
Applies a zone-based variable detection threshold system to identify
potential shipwreck features from combined bathymetric derivative layers.

The tool uses an Adjusted BPI raster (3-class seabed complexity map)
to vary the detection threshold across the survey area:

    - High complexity zones (value 3):  higher threshold (default >= 15)
    - Medium complexity zones (value 2): moderate threshold (default >= 13)
    - Low complexity zones (value 1):   lower threshold (default >= 12)

This ensures that the detector is conservative in complex seabed areas
(where natural features can mimic wreck signatures) and more sensitive
in low-complexity areas (where wrecks stand out against flat seabed).

For each zone the tool:
    1. Extracts cells where Adjusted_BPI == zone AND All_Reclass >= threshold
    2. Converts extracted cells to detection polygons
    3. Merges detection polygons from all zones into a single output
    4. Combines extracted rasters into a unified high-value cell layer

This script replaces the following ModelBuilder steps:
    - Variable Threshold: Extract by Attributes (x3)
    - Variable Threshold: Raster Calculator (x3)
    - Variable Threshold: Raster to Polygon (x3)
    - Detections: Merge
    - High Value Cell Count: Mosaic to New Raster

Downstream ModelBuilder steps that connect to this tool's outputs:
    - Detections: Buffer (30m) → takes Output Detection Polygons
    - High Value Cell Count: Zonal Statistics → takes Output High Value Raster

Inputs:
    - Adjusted BPI raster (3-class: 1=low, 2=medium, 3=high complexity)
    - All Reclass raster (combined slope + curvature + TPI, values 3-15)
    - High complexity zone threshold (default: 15)
    - Medium complexity zone threshold (default: 13)
    - Low complexity zone threshold (default: 12)
    - Output detection polygons path
    - Output high value cells raster path

Outputs:
    - Merged detection polygons (all zones combined)
    - All_HighVals raster (binary: 1 where any zone met its threshold)

ArcGIS Pro Script Tool Parameters:
    Parameter 0: Adjusted BPI raster     (Raster Dataset, Input, Required)
    Parameter 1: All Reclass raster      (Raster Dataset, Input, Required)
    Parameter 2: High zone threshold     (Long, Input, Required, Default=15)
    Parameter 3: Medium zone threshold   (Long, Input, Required, Default=13)
    Parameter 4: Low zone threshold      (Long, Input, Required, Default=12)
    Parameter 5: Output detection polys  (Feature Class, Output, Required)
    Parameter 6: Output high value cells (Raster Dataset, Output, Required)

Author: Cal T. Pols
Date: 2026
"""

import arcpy
from arcpy.sa import Con, Raster, CellStatistics
import os


def variable_threshold_detection(adjusted_bpi_path, all_reclass_path,
                                 high_threshold, med_threshold, low_threshold,
                                 output_detections, output_highvals):
    """
    Apply zone-based variable thresholds and produce merged detection
    polygons and a combined high-value cell raster.

    Parameters:
        adjusted_bpi_path (str): Path to Adjusted BPI raster (values 1-3)
        all_reclass_path (str): Path to All Reclass raster (values 3-15)
        high_threshold (int): Detection threshold for high complexity zone
        med_threshold (int): Detection threshold for medium complexity zone
        low_threshold (int): Detection threshold for low complexity zone
        output_detections (str): Path for output merged detection polygons
        output_highvals (str): Path for output combined high value raster
    """

    # =========================================================================
    # STEP 1: Validate inputs
    # =========================================================================
    arcpy.AddMessage("Validating inputs...")

    if not arcpy.Exists(adjusted_bpi_path):
        arcpy.AddError(f"Adjusted BPI raster does not exist: "
                       f"{adjusted_bpi_path}")
        return

    if not arcpy.Exists(all_reclass_path):
        arcpy.AddError(f"All Reclass raster does not exist: "
                       f"{all_reclass_path}")
        return

    # Threshold validation
    for name, val in [("High", high_threshold), ("Medium", med_threshold),
                      ("Low", low_threshold)]:
        if val < 3 or val > 15:
            arcpy.AddError(f"{name} threshold must be between 3 and 15. "
                           f"Got: {val}")
            return

    if not (high_threshold >= med_threshold >= low_threshold):
        arcpy.AddWarning("Thresholds are not in descending order "
                         "(high >= medium >= low). Proceeding anyway.")

    # Check Spatial Analyst extension
    if arcpy.CheckExtension("Spatial") != "Available":
        arcpy.AddError("Spatial Analyst extension is not available.")
        return
    arcpy.CheckOutExtension("Spatial")

    # =========================================================================
    # STEP 2: Report parameters
    # =========================================================================
    arcpy.AddMessage("Variable Threshold Detection parameters:")
    arcpy.AddMessage(f"  High complexity zone (3): >= {high_threshold}")
    arcpy.AddMessage(f"  Medium complexity zone (2): >= {med_threshold}")
    arcpy.AddMessage(f"  Low complexity zone (1): >= {low_threshold}")

    # =========================================================================
    # STEP 3: Load input rasters
    # =========================================================================
    arcpy.AddMessage("Loading input rasters...")

    adj_bpi = Raster(adjusted_bpi_path)
    all_rcls = Raster(all_reclass_path)

    # Scratch workspace for intermediate outputs
    scratch_gdb = arcpy.env.scratchGDB
    scratch_folder = arcpy.env.scratchFolder

    # Track intermediate files for cleanup
    intermediates = []

    try:
        # =================================================================
        # STEP 4: Extract cells per zone that meet threshold
        # =================================================================
        # Each Con statement replicates the ModelBuilder sequence:
        #   Extract by Attributes (isolate zone) →
        #   Raster Calculator (apply threshold)
        # Combined into a single Con per zone.

        zone_config = [
            (1, "low",    low_threshold),
            (2, "medium", med_threshold),
            (3, "high",   high_threshold),
        ]

        extracted_rasters = []
        poly_inputs = []

        for zone_val, zone_label, threshold in zone_config:

            arcpy.AddMessage(f"Processing {zone_label} complexity zone "
                             f"(value={zone_val}, threshold>={threshold})...")

            # Con((Adjusted_BPI == zone) & (All_Reclass >= threshold), 1)
            # Output: 1 where both conditions met, NoData elsewhere
            extracted = Con(
                (adj_bpi == zone_val) & (all_rcls >= threshold), 1
            )

            # Save extracted raster to scratch (needed for polygon
            # conversion and for combining into All_HighVals)
            ext_ras_path = os.path.join(scratch_folder,
                                        f"{zone_label}_extract.tif")
            extracted.save(ext_ras_path)
            extracted_rasters.append(ext_ras_path)
            intermediates.append(ext_ras_path)

            # Check if any cells were extracted
            all_nodata = arcpy.management.GetRasterProperties(
                ext_ras_path, "ALLNODATA"
            )

            if all_nodata.getOutput(0) == "1":
                arcpy.AddWarning(f"  No detections in {zone_label} "
                                 f"complexity zone.")
                continue

            # Count extracted cells
            cell_count = arcpy.management.GetRasterProperties(
                ext_ras_path, "COLUMNCOUNT"
            )

            # ---------------------------------------------------------
            # Raster to Polygon
            # Replicates: "Simplify Polygons = No, Create Multipart
            # Features = No"
            # ---------------------------------------------------------
            poly_path = os.path.join(scratch_gdb,
                                     f"{zone_label}_det_poly")
            arcpy.conversion.RasterToPolygon(
                ext_ras_path, poly_path,
                "NO_SIMPLIFY", "VALUE",
                "SINGLE_OUTER_PART"
            )
            poly_inputs.append(poly_path)
            intermediates.append(poly_path)

            # Report detection count
            det_count = int(
                arcpy.management.GetCount(poly_path).getOutput(0)
            )
            arcpy.AddMessage(f"  {zone_label} zone: {det_count} "
                             f"detection polygons")

        # =================================================================
        # STEP 5: Merge detection polygons from all zones
        # =================================================================
        # Replicates: Detections → Merge
        # Output feeds into Buffer (30m) in ModelBuilder

        if not poly_inputs:
            arcpy.AddError("No detections found in any zone. Check input "
                           "rasters and threshold values.")
            return

        arcpy.AddMessage("Merging detection polygons from all zones...")

        if len(poly_inputs) == 1:
            arcpy.management.CopyFeatures(poly_inputs[0], output_detections)
        else:
            arcpy.management.Merge(poly_inputs, output_detections)

        total_dets = int(
            arcpy.management.GetCount(output_detections).getOutput(0)
        )

        # =================================================================
        # STEP 6: Combine extracted rasters into All_HighVals
        # =================================================================
        # Replicates: High Value Cell Count → Mosaic to New Raster
        # Original uses: Pixel Type = 1 bit, Mosaic Operator = Mean
        # Since zones are mutually exclusive (each cell belongs to one
        # zone only), CellStatistics MAXIMUM produces the same result:
        # value 1 where any zone extracted a cell, NoData elsewhere.
        # Output feeds into Zonal Statistics in ModelBuilder.

        arcpy.AddMessage("Combining high value cells across zones...")

        all_highvals = CellStatistics(
            extracted_rasters, "MAXIMUM", "DATA"
        )
        all_highvals.save(output_highvals)

        # =================================================================
        # STEP 7: Summary
        # =================================================================
        arcpy.AddMessage("--- Summary ---")
        arcpy.AddMessage(f"Total detection polygons: {total_dets}")
        for zone_val, zone_label, threshold in zone_config:
            # Count how many polys came from each zone (if poly exists)
            poly_path = os.path.join(scratch_gdb,
                                     f"{zone_label}_det_poly")
            if arcpy.Exists(poly_path):
                n = int(
                    arcpy.management.GetCount(poly_path).getOutput(0)
                )
            else:
                n = 0
            arcpy.AddMessage(f"  Zone {zone_val} ({zone_label:>6}, "
                             f">={threshold:>2}): {n} polygons")

        arcpy.AddMessage(f"Output detections: {output_detections}")
        arcpy.AddMessage(f"Output high value raster: {output_highvals}")
        arcpy.AddMessage("Complete.")

    finally:
        # =================================================================
        # Cleanup intermediate files
        # =================================================================
        arcpy.AddMessage("Cleaning up intermediate files...")
        for item in intermediates:
            try:
                if arcpy.Exists(item):
                    arcpy.management.Delete(item)
            except Exception:
                pass

        # Check in the extension
        arcpy.CheckInExtension("Spatial")

    return output_detections


# =============================================================================
# SCRIPT TOOL INTERFACE
# =============================================================================

if __name__ == "__main__":

    # Parameter 0: Adjusted BPI raster (3-class seabed complexity)
    # Set up in tool properties as Raster Dataset (Input, Required)
    adjusted_bpi_path = arcpy.GetParameterAsText(0)

    # Parameter 1: All Reclass raster (combined derivatives, values 3-15)
    # Set up in tool properties as Raster Dataset (Input, Required)
    all_reclass_path = arcpy.GetParameterAsText(1)

    # Parameter 2: High zone threshold
    # Set up in tool properties as Long (Input, Required)
    # Default value: 15
    high_threshold = arcpy.GetParameter(2)
    if high_threshold is None or high_threshold == "":
        high_threshold = 15
    else:
        high_threshold = int(high_threshold)

    # Parameter 3: Medium zone threshold
    # Set up in tool properties as Long (Input, Required)
    # Default value: 13
    med_threshold = arcpy.GetParameter(3)
    if med_threshold is None or med_threshold == "":
        med_threshold = 13
    else:
        med_threshold = int(med_threshold)

    # Parameter 4: Low zone threshold
    # Set up in tool properties as Long (Input, Required)
    # Default value: 12
    low_threshold = arcpy.GetParameter(4)
    if low_threshold is None or low_threshold == "":
        low_threshold = 12
    else:
        low_threshold = int(low_threshold)

    # Parameter 5: Output detection polygons
    # Set up in tool properties as Feature Class (Output, Required)
    output_detections = arcpy.GetParameterAsText(5)

    # Parameter 6: Output high value cells raster
    # Set up in tool properties as Raster Dataset (Output, Required)
    output_highvals = arcpy.GetParameterAsText(6)

    # Run variable threshold detection
    result = variable_threshold_detection(
        adjusted_bpi_path, all_reclass_path,
        high_threshold, med_threshold, low_threshold,
        output_detections, output_highvals
    )

    # Set output parameter for ModelBuilder chaining
    arcpy.SetParameterAsText(5, result)
