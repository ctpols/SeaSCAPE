"""
Broad-Scale Bathymetric Position Index (BPI) Calculator
========================================================
BPI measures whether a cell is elevated or depressed relative to its broader surroundings using an annular (ring) focal neighbourhood. The annular neighbourhood distinguishes Broad BPI from fine-scale BPI (which uses a smaller annulus) and from TPI (which uses a solid circle). The hollow centre of the annulus excludes the immediate surroundings, capturing the position relative to the broader terrain context. Positive values indicate locally elevated features, negative values indicate locally depressed features, values near zero indicate flat seabed or constant slopes. 

This script calculates Broad-Scale Bathymetric Position Index after Lundblad et al. (2006), as implemented in the Benthic Terrain Modeler (BTM) toolbox (Wright et al., 2012; Walbridge et al., 2018). This script replaces the dependency on the BTM toolbox (btm.tbx) with a pure arcpy.sa implementation, allowing it to be embedded directly within the SeaSCAPE toolbox. 

Inputs: Input bathymetric raster, Inner radius of annulus (in cells), Outer radius of annulus (in cells), Output BPI raster path 

Outputs: BPI raster (continuous integer values) 

References: 
•	Lundblad, E.R., Wright, D.J., Miller, J., Larkin, E.M., Rinehart, R.,Naar, D.F., Donahue, B.T., Anderson, S.M. and Battista, T. (2006) A benthic terrain classification scheme for American Samoa.Marine Geodesy, 29(2), pp.89-111. 
•	Wright, D.J., Pendleton, M., Boulware, J., Walbridge, S., Gerlt, B.,Eslinger, D., Sampson, D. and Huntley, E. (2012) ArcGIS Benthic Terrain Modeler (BTM), v. 3.0. NOAA Coastal Services Center. 
•	Walbridge, S., Slocum, N., Pobuda, M. and Wright, D.J. (2018) Unified geomorphological analysis workflows with Benthic Terrain Modeler. Geosciences, 8(3), p.94.

ArcGIS Pro Script Tool Parameters:
    Parameter 0: Input raster       (Raster Dataset, Input, Required)
    Parameter 1: Inner radius       (Long, Input, Required, Default=50)
    Parameter 2: Outer radius       (Long, Input, Required, Default=500)
    Parameter 3: Output BPI raster  (Raster Dataset, Output, Required)

Author: Cal T. Pols
Date: 2026
"""

import arcpy
from arcpy.sa import FocalStatistics, NbrAnnulus, Raster, Int


def calculate_broad_bpi(input_raster, inner_radius, outer_radius,
                        output_raster):
    """
    Calculate Broad-Scale Bathymetric Position Index.

    BPI = cell_value - FocalMean(cell_value, NbrAnnulus(inner, outer))

    The result is cast to integer to match the BTM convention and to
    facilitate downstream classification and reclassification steps.

    Parameters:
        input_raster (str): Path to input bathymetry raster
        inner_radius (int): Inner radius of annulus in cells
        outer_radius (int): Outer radius of annulus in cells
        output_raster (str): Path for output BPI raster
    """

    # =========================================================================
    # STEP 1: Validate inputs
    # =========================================================================
    arcpy.AddMessage("Validating inputs...")

    if not arcpy.Exists(input_raster):
        arcpy.AddError(f"Input raster does not exist: {input_raster}")
        return

    if inner_radius < 1:
        arcpy.AddError(f"Inner radius must be >= 1 cell. Got: {inner_radius}")
        return

    if outer_radius <= inner_radius:
        arcpy.AddError(f"Outer radius ({outer_radius}) must be greater "
                       f"than inner radius ({inner_radius}).")
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
    scale_factor = cell_size * outer_radius

    arcpy.AddMessage(f"Input raster: {input_raster}")
    arcpy.AddMessage(f"Cell size: {cell_size}")
    arcpy.AddMessage(f"Inner radius: {inner_radius} cells "
                     f"({inner_radius * cell_size:.1f} map units)")
    arcpy.AddMessage(f"Outer radius: {outer_radius} cells "
                     f"({outer_radius * cell_size:.1f} map units)")
    arcpy.AddMessage(f"Scale factor: {scale_factor:.1f} map units")
    arcpy.AddMessage(f"Output: {output_raster}")

    # =========================================================================
    # STEP 3: Calculate BPI
    # =========================================================================
    arcpy.AddMessage("Calculating focal mean (annular neighbourhood)...")

    # Load the input as a Raster object
    ras = Raster(input_raster)

    # Define annular neighbourhood
    neighbourhood = NbrAnnulus(inner_radius, outer_radius, "CELL")

    # Calculate focal mean within annular neighbourhood
    focal_mean = FocalStatistics(ras, neighbourhood, "MEAN", "DATA")

    arcpy.AddMessage("Computing BPI (bathymetry minus focal mean)...")

    # BPI = cell value - focal mean
    bpi = ras - focal_mean

    # Cast to integer (BTM convention)
    bpi_int = Int(bpi + 0.5)

    # =========================================================================
    # STEP 4: Save output
    # =========================================================================
    arcpy.AddMessage("Saving BPI raster...")
    bpi_int.save(output_raster)

    # Check in the extension
    arcpy.CheckInExtension("Spatial")

    arcpy.AddMessage(f"Broad BPI raster saved: {output_raster}")
    arcpy.AddMessage("Complete.")

    return output_raster


# =============================================================================
# SCRIPT TOOL INTERFACE
# =============================================================================

if __name__ == "__main__":

    # Parameter 0: Input bathymetric raster
    # Set up in tool properties as Raster Dataset (Input, Required)
    input_raster = arcpy.GetParameterAsText(0)

    # Parameter 1: Inner radius (cells)
    # Set up in tool properties as Long (Input, Required)
    # Default value: 50
    inner_radius = arcpy.GetParameter(1)
    if inner_radius is None or inner_radius == "":
        inner_radius = 50
    else:
        inner_radius = int(inner_radius)

    # Parameter 2: Outer radius (cells)
    # Set up in tool properties as Long (Input, Required)
    # Default value: 500
    outer_radius = arcpy.GetParameter(2)
    if outer_radius is None or outer_radius == "":
        outer_radius = 500
    else:
        outer_radius = int(outer_radius)

    # Parameter 3: Output BPI raster
    # Set up in tool properties as Raster Dataset (Output, Required)
    output_raster = arcpy.GetParameterAsText(3)

    # Run BPI calculation
    result = calculate_broad_bpi(input_raster, inner_radius, outer_radius,
                                 output_raster)

    # Set output parameter for ModelBuilder chaining
    arcpy.SetParameterAsText(3, result)
