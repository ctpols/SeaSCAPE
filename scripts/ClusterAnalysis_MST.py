"""
Cluster Analysis Tool (MST + Statistics) - Optimised
=====================================================
Performs cluster analysis for each detection polygon, producing structural
gap measurements and cluster area statistics from a single consistent
post-merge cluster set.

Process:
    1. Reads cluster polygons grouped by parent detection
    2. Pre-filters detections below the resolution gate (Class 4)
       to avoid unnecessary computation on unclassifiable detections
    3. Merges any touching clusters using a single-pass dissolve approach
       (union all geometries, then explode multipart result)
    4. Calculates cluster area statistics (sum, max, min, mean, count)
    5. Calculates cluster dominance (max area / sum area)
    6. Computes maximum structural gap using Minimum Spanning Tree (MST)
       on edge-to-edge polygon distances

The MST approach correctly handles cases where small intermediate clusters
sit between larger structural sections.

All statistics are derived from the post-merge cluster set, ensuring
consistency between area metrics, dominance, and gap measurements.

Detections below the resolution gate receive default values (Clst_Count=1,
MaxGap=0, Clst_DOM=1) and are skipped for the expensive MST computation.

Usage:
    - As a standalone script tool in ArcGIS Pro geoprocessing pane
    - As an embedded script tool within a ModelBuilder workflow

Inputs:
    - Cluster polygon feature class (with FID_ field linking to parent detection)
    - Detection polygon feature class (for resolution gate filtering)
    - Field name identifying the parent detection (default: FID_)
    - Resolution gate - minimum polygon length in metres (default: 50)

Outputs:
    - Output table with fields:
        FID_        : Parent detection ID
        Clst_Count  : Number of clusters (post-merge)
        Clst_Sum    : Total cluster area (m2)
        Clst_Max    : Area of largest cluster (m2)
        Clst_Min    : Area of smallest cluster (m2)
        Clst_Mean   : Mean cluster area (m2)
        Clst_DOM    : Cluster dominance (Clst_Max / Clst_Sum)
        MaxGap      : Maximum structural gap from MST (m)

Author: Cal T. Pols
Date: 2026
"""

import arcpy
import os
import numpy as np
from functools import reduce
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import minimum_spanning_tree


def calculate_cluster_stats(cluster_fc, detection_fc, parent_field,
                            res_gate, output_table):
    """
    Calculates cluster statistics and maximum structural gap per detection.

    Parameters:
        cluster_fc (str): Path to cluster polygon feature class
        detection_fc (str): Path to detection polygon feature class
        parent_field (str): Field name linking clusters to parent detections
        res_gate (float): Minimum polygon length for full analysis (m)
        output_table (str): Path for output table
    """

    # =========================================================================
    # STEP 1: Identify detections below the resolution gate
    #         These get default values and skip expensive cluster analysis
    # =========================================================================
    arcpy.AddMessage("Checking resolution gate...")

    # Build a set of detection IDs that are below the resolution gate
    skip_ids = set()

    with arcpy.da.SearchCursor(detection_fc, ["FID", "Length"]) as cursor:
        for row in cursor:
            if row[1] < res_gate:
                skip_ids.add(row[0])

    arcpy.AddMessage(
        f"  {len(skip_ids)} detection(s) below resolution gate "
        f"({res_gate}m) - will receive default values."
    )

    # =========================================================================
    # STEP 2: Read all cluster polygon geometries, grouped by parent detection
    # =========================================================================
    arcpy.AddMessage("Reading cluster polygon geometries...")

    # Dictionary to store cluster geometries grouped by parent detection ID
    detection_clusters = {}

    with arcpy.da.SearchCursor(cluster_fc, [parent_field, "SHAPE@"]) as cursor:
        for row in cursor:
            parent_id = row[0]
            geometry = row[1]

            if parent_id not in detection_clusters:
                detection_clusters[parent_id] = []
            detection_clusters[parent_id].append(geometry)

    total_detections = len(detection_clusters)
    analyse_count = sum(1 for pid in detection_clusters if pid not in skip_ids)
    arcpy.AddMessage(f"Found {total_detections} detection(s) with cluster data.")
    arcpy.AddMessage(f"  {analyse_count} require full cluster analysis.")

    # =========================================================================
    # STEP 3: Process each detection
    #
    #         For skipped detections (below resolution gate):
    #           - Assign default values
    #
    #         For analysed detections:
    #           a) Merge touching clusters using single-pass dissolve
    #           b) Calculate area statistics on the merged cluster set
    #           c) Calculate cluster dominance
    #           d) Compute MST and extract maximum gap
    # =========================================================================
    arcpy.AddMessage("Processing detections...")

    results = []
    detections_with_merges = 0
    processed = 0

    for parent_id, geometries in detection_clusters.items():

        # ---------------------------------------------------------------------
        # Check if this detection should be skipped (below resolution gate)
        # Assign default values: single cluster, no gap, full dominance
        # ---------------------------------------------------------------------
        if parent_id in skip_ids:
            # Calculate basic area stats even for skipped detections
            cluster_areas = [g.area for g in geometries]
            total_area = sum(cluster_areas)

            results.append((
                parent_id,
                len(geometries),
                round(total_area, 2),
                round(max(cluster_areas), 2),
                round(min(cluster_areas), 2),
                round(total_area / len(geometries), 2),
                round(max(cluster_areas) / total_area, 4) if total_area > 0 else 0.0,
                0.0  # MaxGap = 0 for skipped detections
            ))
            continue

        # ---------------------------------------------------------------------
        # 3a) Merge touching clusters using single-pass dissolve
        #     Union all geometries into one, then explode multipart result
        #     back into individual (merged) clusters
        # ---------------------------------------------------------------------
        if len(geometries) > 1:
            # Union all cluster geometries in a single operation
            merged_geom = reduce(lambda a, b: a.union(b), geometries)

            # Explode multipart geometry back into individual parts
            # Each part is a group of formerly-touching clusters, now merged
            original_count = len(geometries)

            if merged_geom.isMultipart:
                # Extract each part as a separate geometry
                geometries = []
                for i in range(merged_geom.partCount):
                    part_array = merged_geom.getPart(i)
                    part_geom = arcpy.Polygon(part_array,
                                              merged_geom.spatialReference)
                    geometries.append(part_geom)
            else:
                # All clusters merged into a single geometry
                geometries = [merged_geom]

            if len(geometries) < original_count:
                detections_with_merges += 1

        # ---------------------------------------------------------------------
        # 3b) Calculate cluster area statistics on the post-merge set
        # ---------------------------------------------------------------------
        cluster_count = len(geometries)
        cluster_areas = [g.area for g in geometries]

        clst_sum = sum(cluster_areas)
        clst_max = max(cluster_areas)
        clst_min = min(cluster_areas)
        clst_mean = clst_sum / cluster_count

        # ---------------------------------------------------------------------
        # 3c) Calculate cluster dominance
        # ---------------------------------------------------------------------
        if clst_sum > 0:
            clst_dom = clst_max / clst_sum
        else:
            clst_dom = 0.0

        # ---------------------------------------------------------------------
        # 3d) Calculate maximum structural gap using MST
        # ---------------------------------------------------------------------
        if cluster_count == 1:
            max_gap = 0.0
        elif cluster_count == 2:
            max_gap = geometries[0].distanceTo(geometries[1])
        else:
            # Build pairwise distance matrix
            dist_matrix = np.zeros((cluster_count, cluster_count))

            for i in range(cluster_count):
                for j in range(i + 1, cluster_count):
                    dist = geometries[i].distanceTo(geometries[j])
                    dist_matrix[i][j] = dist
                    dist_matrix[j][i] = dist

            # Compute Minimum Spanning Tree
            sparse_matrix = csr_matrix(dist_matrix)
            mst = minimum_spanning_tree(sparse_matrix)

            # Longest edge in MST = widest structural gap
            mst_edges = mst.toarray()
            max_gap = float(mst_edges.max())

        # ---------------------------------------------------------------------
        # Store results
        # ---------------------------------------------------------------------
        results.append((
            parent_id,
            cluster_count,
            round(clst_sum, 2),
            round(clst_max, 2),
            round(clst_min, 2),
            round(clst_mean, 2),
            round(clst_dom, 4),
            round(max_gap, 2)
        ))

        # Progress feedback every 100 detections
        processed += 1
        if processed % 100 == 0:
            arcpy.AddMessage(f"  Processed {processed} / {analyse_count}...")

    if detections_with_merges > 0:
        arcpy.AddMessage(
            f"Merged touching clusters in {detections_with_merges} detection(s)."
        )

    # =========================================================================
    # STEP 4: Create output table and write results
    # =========================================================================
    arcpy.AddMessage("Writing results to output table...")

    temp_table = "in_memory/cluster_stats_temp"

    if arcpy.Exists(temp_table):
        arcpy.management.Delete(temp_table)

    arcpy.management.CreateTable("in_memory", "cluster_stats_temp")

    # Define output fields (all names <= 10 characters for .dbf compatibility)
    fields = [
        (parent_field, "LONG"),
        ("Clst_Count", "LONG"),
        ("Clst_Sum", "DOUBLE"),
        ("Clst_Max", "DOUBLE"),
        ("Clst_Min", "DOUBLE"),
        ("Clst_Mean", "DOUBLE"),
        ("Clst_DOM", "DOUBLE"),
        ("MaxGap", "DOUBLE")
    ]

    for field_name, field_type in fields:
        arcpy.management.AddField(temp_table, field_name, field_type)

    field_names = [f[0] for f in fields]
    with arcpy.da.InsertCursor(temp_table, field_names) as cursor:
        for row in results:
            cursor.insertRow(row)

    arcpy.management.CopyRows(temp_table, output_table)
    arcpy.management.Delete(temp_table)

    # =========================================================================
    # STEP 5: Summary statistics for user feedback
    # =========================================================================
    analysed_results = [r for r in results
                        if r[0] not in skip_ids]
    skipped_results = [r for r in results
                       if r[0] in skip_ids]

    single_cluster = sum(1 for r in analysed_results if r[1] == 1)
    multi_cluster = len(analysed_results) - single_cluster

    arcpy.AddMessage("--- Summary ---")
    arcpy.AddMessage(f"Total detections: {total_detections}")
    arcpy.AddMessage(f"  Skipped (below resolution gate): {len(skipped_results)}")
    arcpy.AddMessage(f"  Analysed: {len(analysed_results)}")
    arcpy.AddMessage(f"    Single cluster (MaxGap = 0): {single_cluster}")
    arcpy.AddMessage(f"    Multi-cluster: {multi_cluster}")

    if multi_cluster > 0:
        multi_gaps = [r[7] for r in analysed_results if r[1] > 1]
        arcpy.AddMessage(
            f"    Max gap range: {min(multi_gaps):.2f} - "
            f"{max(multi_gaps):.2f} m"
        )
        arcpy.AddMessage(
            f"    Mean max gap: "
            f"{sum(multi_gaps) / len(multi_gaps):.2f} m"
        )

    if analysed_results:
        dom_values = [r[6] for r in analysed_results]
        arcpy.AddMessage(
            f"  Dominance range: {min(dom_values):.4f} - "
            f"{max(dom_values):.4f}"
        )

    arcpy.AddMessage(f"Output table: {output_table}")
    arcpy.AddMessage("Complete.")

    return output_table


# =============================================================================
# SCRIPT TOOL INTERFACE
# =============================================================================

if __name__ == "__main__":

    # Parameter 0: Input cluster polygon feature class
    # Set up in tool properties as Feature Class (Input)
    # Use the Spatial Join output (Regions_W_PCT90_SpatialJoin)
    cluster_fc = arcpy.GetParameterAsText(0)

    # Parameter 1: Input detection polygon feature class
    # Set up in tool properties as Feature Class (Input)
    # Used for resolution gate filtering (needs Length field)
    detection_fc = arcpy.GetParameterAsText(1)

    # Parameter 2: Parent detection ID field name
    # Set up in tool properties as Field (Input), obtained from Parameter 0
    # Default value: FID_
    parent_field = arcpy.GetParameterAsText(2)
    if not parent_field:
        parent_field = "FID_"

    # Parameter 3: Resolution gate - minimum polygon length (metres)
    # Set up in tool properties as Double (Input)
    # Default value: 50
    res_gate = arcpy.GetParameter(3)
    if res_gate is None or res_gate == "":
        res_gate = 50.0

    # Parameter 4: Output table
    # Set up in tool properties as Table (Output)
    output_table = arcpy.GetParameterAsText(4)

    # Run the calculation
    result = calculate_cluster_stats(cluster_fc, detection_fc, parent_field,
                                     res_gate, output_table)

    # Set output parameter for ModelBuilder chaining
    arcpy.SetParameterAsText(4, result)
