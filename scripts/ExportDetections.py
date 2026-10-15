"""
Detection Export Tool
======================
Exports detection polygons into two output feature classes:

    1. All Stats  - complete attribute table, all fields retained
    2. Simple     - reduced to key output fields only:
                    FID, Shape, Confidence, Degrees, BearingTxt,
                    Pres_Class, Pres_Index

This tool exists because ArcGIS Pro's Export Features tool cannot
resolve the attribute schema of upstream script tool outputs at
ModelBuilder design time. This script performs the same function
with hardcoded field retention, ensuring it works reliably within
a ModelBuilder chain.

Inputs:
    - Classified detection polygon feature class

Outputs:
    - Full export feature class (all fields)
    - Simplified export feature class (key fields only)

Date: 2026
"""

import arcpy


def export_detections(input_fc, output_all, output_simple):
    """
    Exports detection polygons to full and simplified feature classes.

    Parameters:
        input_fc (str): Path to classified detection polygon feature class
        output_all (str): Path for full export (all fields)
        output_simple (str): Path for simplified export (key fields only)
    """

    # =========================================================================
    # STEP 1: Export full attribute table version
    # =========================================================================
    arcpy.AddMessage("Exporting full attribute table version...")
    arcpy.management.CopyFeatures(input_fc, output_all)
    arcpy.AddMessage(f"  Output: {output_all}")

    # =========================================================================
    # STEP 2: Export simplified version
    # =========================================================================
    arcpy.AddMessage("Exporting simplified version...")

    # Copy the full feature class first
    arcpy.management.CopyFeatures(input_fc, output_simple)

    # Fields to keep in the simplified output
    # FID and Shape are system fields and cannot be deleted
    keep_fields = ["Confidence", "Degrees", "BearingTxt",
                   "Pres_Class", "Pres_Index"]

    # Get all fields in the feature class
    all_fields = [f.name for f in arcpy.ListFields(output_simple)]

    # Identify fields to delete (everything except system fields and keep list)
    # System fields (FID, Shape, OID, etc.) cannot be deleted so we skip them
    system_fields = ["FID", "Shape", "OBJECTID", "Shape_Length", "Shape_Area"]

    delete_fields = [f for f in all_fields
                     if f not in keep_fields
                     and f.upper() not in [s.upper() for s in system_fields]]

    if delete_fields:
        arcpy.management.DeleteField(output_simple, delete_fields)
        arcpy.AddMessage(f"  Removed {len(delete_fields)} field(s)")

    # Report the fields retained
    final_fields = [f.name for f in arcpy.ListFields(output_simple)]
    arcpy.AddMessage(f"  Retained fields: {', '.join(final_fields)}")
    arcpy.AddMessage(f"  Output: {output_simple}")

    # =========================================================================
    # STEP 3: Summary
    # =========================================================================
    count = int(arcpy.management.GetCount(input_fc)[0])
    arcpy.AddMessage(f"--- Summary ---")
    arcpy.AddMessage(f"Total features exported: {count}")
    arcpy.AddMessage("Complete.")

    return output_all, output_simple


# =============================================================================
# SCRIPT TOOL INTERFACE
# =============================================================================

if __name__ == "__main__":

    # Parameter 0: Input classified detection polygons
    # Set up in tool properties as Feature Class (Input)
    input_fc = arcpy.GetParameterAsText(0)

    # Parameter 1: Output - all stats
    # Set up in tool properties as Feature Class (Output)
    output_all = arcpy.GetParameterAsText(1)

    # Parameter 2: Output - simplified
    # Set up in tool properties as Feature Class (Output)
    output_simple = arcpy.GetParameterAsText(2)

    # Run export
    result_all, result_simple = export_detections(input_fc, output_all,
                                                  output_simple)

    # Set output parameters for ModelBuilder chaining
    arcpy.SetParameterAsText(1, result_all)
    arcpy.SetParameterAsText(2, result_simple)
