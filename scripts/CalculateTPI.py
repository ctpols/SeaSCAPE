"""
Topographic Position Index (TPI) Calculator
=============================================
Calculates Topographic Position Index (TPI) after Weiss (2001), as implemented by Jenness (2006) and Dilts (2015). TPI measures whether a cell is higher or lower than its surrounding neighbourhood using a circular focal window. Positive values indicate locally elevated positions, negative values indicate depressions, values near zero indicate flat or constant-slope areas. This script replaces the dependency on the external Topography Tools toolbox (Dilts, 2015) with a pure arcpy.sa implementation, allowing it to be embedded directly within the SeaSCAPE toolbox.

Inputs: Input bathymetric/elevation raster, Neighbourhood radius (in cells), Output TPI raster path

Outputs: TPI raster (continuous float values)

References:
•	 Weiss, A.D. (2001) Topographic position and landforms analysis. Poster, ESRI Users Conference, San Diego, CA.
•	 Jenness, J. (2006) Topographic Position Index (tpi_jen.avx) extension for ArcView 3.x, v. 1.3a. Jenness Enterprises.
•	 Dilts, T. (2015) Topography Tools for ArcGIS 10.3. University of Nevada, Reno. URL: https://www.arcgis.com/home/item.html?id=b13b3b40fa3c43d4a23a1a09c5fe96b9

ArcGIS Pro Script Tool Parameters:
    Parameter 0: Input raster          (Raster Dataset, Input, Required)
    Parameter 1: Neighbourhood radius  (Long, Input, Required, Default=30)
    Parameter 2: Output TPI raster     (Raster Dataset, Output, Required)

Author: Cal T. Pols
Date: 2026
"""

import arcpy
from arcpy.sa import FocalStatistics, NbrCircle, Raster


def calculate_tpi(input_raster, radius, output_raster):
    """
    Calculate Topographic Position Index.

    TPI = cell_value - FocalMean(cell_value, NbrCircle(radius))

    Parameters:
        input_raster (str): Path to input elevation/bathymetry raster
        radius (int): Circular neighbourhood radius in cells
        output_raster (str): Path for output TPI raster
    """

    # =========================================================================
    # STEP 1: Validate inputs
    # =========================================================================
    arcpy.AddMessage("Validating inputs...")

    if not arcpy.Exists(input_raster):
        arcpy.AddError(f"Input raster does not exist: {input_raster}")
        return

    if radius < 1:
        arcpy.AddError(f"Neighbourhood radius must be >= 1 cell. Got: {radius}")
        return

    # Check Spatial Analyst extension
    if arcpy.CheckExtension("Spatial") != "Available":
        arcpy.AddError("Spatial Analyst extension is not available.")
        return
    arcpy.CheckOutExtension("Spatial")

    # =========================================================================
    # STEP 2: Report parameters
    # =========================================================================
    desc = arcpy.Describe(input_raster)
    cell_size = desc.meanCellWidth

    arcpy.AddMessage(f"Input raster: {input_raster}")
    arcpy.AddMessage(f"Cell size: {cell_size}")
    arcpy.AddMessage(f"Neighbourhood radius: {radius} cells "
                     f"({radius * cell_size:.1f} map units)")
    arcpy.AddMessage(f"Output: {output_raster}")

    # =========================================================================
    # STEP 3: Calculate TPI
    # =========================================================================
    arcpy.AddMessage("Calculating focal mean...")

    # Load the input as a Raster object
    ras = Raster(input_raster)

    # Define circular neighbourhood
    neighbourhood = NbrCircle(radius, "CELL")

    # Calculate focal mean within neighbourhood
    focal_mean = FocalStatistics(ras, neighbourhood, "MEAN", "DATA")

    arcpy.AddMessage("Computing TPI (elevation minus focal mean)...")

    # TPI = cell value - focal mean
    tpi = ras - focal_mean

    # =========================================================================
    # STEP 4: Save output
    # =========================================================================
    arcpy.AddMessage("Saving TPI raster...")
    tpi.save(output_raster)

    # Check in the extension
    arcpy.CheckInExtension("Spatial")

    arcpy.AddMessage(f"TPI raster saved: {output_raster}")
    arcpy.AddMessage("Complete.")

    return output_raster


# =============================================================================
# SCRIPT TOOL INTERFACE
# =============================================================================

if __name__ == "__main__":

    # Parameter 0: Input elevation/bathymetry raster
    # Set up in tool properties as Raster Dataset (Input, Required)
    input_raster = arcpy.GetParameterAsText(0)

    # Parameter 1: Neighbourhood radius (cells)
    # Set up in tool properties as Long (Input, Required)
    # Default value: 30
    radius = arcpy.GetParameter(1)
    if radius is None or radius == "":
        radius = 30
    else:
        radius = int(radius)

    # Parameter 2: Output TPI raster
    # Set up in tool properties as Raster Dataset (Output, Required)
    output_raster = arcpy.GetParameterAsText(2)

    # Run TPI calculation
    result = calculate_tpi(input_raster, radius, output_raster)

    # Set output parameter for ModelBuilder chaining
    arcpy.SetParameterAsText(2, result)
