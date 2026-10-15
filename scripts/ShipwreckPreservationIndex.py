"""
Preservation Classification and Scoring Tool
==============================================
Assigns a structural preservation class and calculates a composite
preservation score for each detection polygon.

Classification scheme:
    Class 1 - Intact (score 8-10):   MaxGap <= 5m or single cluster
    Class 2 - Broken (score 5-7):    MaxGap > 5m and dominance >= 0.3
    Class 3 - Fragmented (score 2-4): MaxGap > 5m and dominance < 0.3
    Class 4 - Indeterminate (score 1): Polygon longest axis < 50m

Classification rules are applied in order:
    1. Resolution gate (Class 4) checked first
    2. MaxGap threshold separates intact from broken/fragmented
    3. Cluster dominance separates broken from fragmented

Within each class, the signal score determines placement in the score range.
Signal score = (R_mean_N + R_std_N + (1 - CV_wreck_N)) / 3

Inputs:
    - Detection polygon feature class (with all required fields)
    - Gap threshold (default: 5m)
    - Dominance threshold (default: 0.3)
    - Resolution gate polygon length (default: 50m)

Outputs:
    - Updates the input feature class with two new fields:
        Pres_Class : Structural preservation class (1-4)
        Pres_Index : Composite preservation score (1-10)

Author: Cal T. Pols
Date: 2026
"""

import arcpy


def classify_and_score(detection_fc, gap_threshold, dom_threshold, res_gate,
                       output_fc):
    """
    Assigns preservation class and score to each detection polygon.
    Produces a new output feature class with the classification fields added.

    Parameters:
        detection_fc (str): Path to input detection polygon feature class
        gap_threshold (float): MaxGap threshold separating intact/broken (m)
        dom_threshold (float): Dominance threshold separating broken/fragmented
        res_gate (float): Minimum polygon length for classification (m)
        output_fc (str): Path for output feature class with classification
    """

    # =========================================================================
    # STEP 1: Copy input to output so we work on a new feature class
    # =========================================================================
    arcpy.AddMessage("Creating output feature class...")
    arcpy.management.CopyFeatures(detection_fc, output_fc)

    # =========================================================================
    # STEP 2: Add output fields if they don't already exist
    # =========================================================================
    arcpy.AddMessage("Preparing output fields...")

    existing_fields = [f.name for f in arcpy.ListFields(output_fc)]

    if "Pres_Class" not in existing_fields:
        arcpy.management.AddField(output_fc, "Pres_Class", "SHORT")
    if "Pres_Index" not in existing_fields:
        arcpy.management.AddField(output_fc, "Pres_Index", "DOUBLE")

    # =========================================================================
    # STEP 3: Verify all required input fields exist
    # =========================================================================
    required_fields = ["MaxGap", "Clst_DOM", "Clst_Count",
                       "R_mean_N", "R_std_N", "CV_wreck_N", "Length"]

    missing = [f for f in required_fields if f not in existing_fields]
    if missing:
        arcpy.AddError(f"Missing required fields: {', '.join(missing)}")
        arcpy.AddError("Ensure all upstream workflow steps have been completed.")
        return

    arcpy.AddMessage(f"Classification parameters:")
    arcpy.AddMessage(f"  Gap threshold: {gap_threshold} m")
    arcpy.AddMessage(f"  Dominance threshold: {dom_threshold}")
    arcpy.AddMessage(f"  Resolution gate (polygon length): {res_gate} m")

    # =========================================================================
    # STEP 4: Classify each detection and calculate preservation score
    # =========================================================================
    arcpy.AddMessage("Classifying detections and calculating scores...")

    # Fields to read and write
    read_fields = ["MaxGap", "Clst_DOM", "Clst_Count", "Length",
                   "R_mean_N", "R_std_N", "CV_wreck_N"]
    write_fields = ["Pres_Class", "Pres_Index"]
    all_fields = read_fields + write_fields

    # Counters for summary
    class_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    with arcpy.da.UpdateCursor(output_fc, all_fields) as cursor:
        for row in cursor:
            # Unpack input fields
            max_gap = row[0]
            clst_dom = row[1]
            clst_count = row[2]
            poly_length = row[3]
            r_mean_n = row[4]
            r_std_n = row[5]
            cv_wreck_n = row[6]

            # -----------------------------------------------------------------
            # Calculate signal score (0-1)
            # Equal weighting of normalised roughness mean, STD, and
            # inverted CV (lower CV = more coherent signal = higher score)
            # -----------------------------------------------------------------
            signal_score = (r_mean_n + r_std_n + (1 - cv_wreck_n)) / 3

            # Clamp signal score to 0-1 range as a safety check
            signal_score = max(0.0, min(1.0, signal_score))

            # -----------------------------------------------------------------
            # Apply classification rules in order
            # -----------------------------------------------------------------

            # Rule 1: Resolution gate — too small to classify
            if poly_length < res_gate:
                pres_class = 4
                pres_index = 1.0

            # Rule 2: Intact — no significant structural gap
            elif max_gap <= gap_threshold or clst_count == 1:
                pres_class = 1
                # Score range 8-10
                pres_index = 8 + (signal_score * 2)

            # Rule 3: Fragmented — large gap AND low dominance
            elif clst_dom < dom_threshold:
                pres_class = 3
                # Score range 2-4
                pres_index = 2 + (signal_score * 2)

            # Rule 4: Broken — large gap but still has dominant structure
            else:
                pres_class = 2
                # Score range 5-7
                pres_index = 5 + (signal_score * 2)

            # Round the score to 1 decimal places
            pres_index = round(pres_index, 1)

            # Update the row
            row[7] = pres_class
            row[8] = pres_index
            cursor.updateRow(row)

            class_counts[pres_class] += 1

    # =========================================================================
    # STEP 5: Summary for user feedback
    # =========================================================================
    total = sum(class_counts.values())

    arcpy.AddMessage("--- Summary ---")
    arcpy.AddMessage(f"Total detections classified: {total}")
    arcpy.AddMessage(f"  Class 1 - Intact:         {class_counts[1]}")
    arcpy.AddMessage(f"  Class 2 - Broken:         {class_counts[2]}")
    arcpy.AddMessage(f"  Class 3 - Fragmented:     {class_counts[3]}")
    arcpy.AddMessage(f"  Class 4 - Indeterminate:  {class_counts[4]}")
    arcpy.AddMessage(f"Output: {output_fc}")
    arcpy.AddMessage("Complete.")

    return output_fc


# =============================================================================
# SCRIPT TOOL INTERFACE
# =============================================================================

if __name__ == "__main__":

    # Parameter 0: Input detection polygon feature class
    # Set up in tool properties as Feature Class (Input)
    # This should be the detections polygon with all fields from
    # upstream workflow steps (normalised stats + cluster analysis)
    detection_fc = arcpy.GetParameterAsText(0)

    # Parameter 1: Gap threshold (metres)
    # Set up in tool properties as Double (Input)
    # Default value: 5
    gap_threshold = arcpy.GetParameter(1)
    if gap_threshold is None or gap_threshold == "":
        gap_threshold = 5.0

    # Parameter 2: Dominance threshold
    # Set up in tool properties as Double (Input)
    # Default value: 0.3
    dom_threshold = arcpy.GetParameter(2)
    if dom_threshold is None or dom_threshold == "":
        dom_threshold = 0.3

    # Parameter 3: Resolution gate - minimum polygon length (metres)
    # Set up in tool properties as Double (Input)
    # Default value: 50
    res_gate = arcpy.GetParameter(3)
    if res_gate is None or res_gate == "":
        res_gate = 50.0

    # Parameter 4: Output feature class
    # Set up in tool properties as Feature Class (Output)
    output_fc = arcpy.GetParameterAsText(4)

    # Run classification and scoring
    result = classify_and_score(detection_fc, gap_threshold, dom_threshold,
                                res_gate, output_fc)

    # Set output parameter for ModelBuilder chaining
    arcpy.SetParameterAsText(4, result)
