import arcpy
arcpy.AddMessage("Starting Normalisation")
# Defining parameters
in_table = arcpy.GetParameterAsText(0)  # Input wreck table or feature class
fields_to_normalise = ["R_mean", "R_std", "CV_wreck"]
arcpy.AddMessage(f"Input Table: {in_table}")
arcpy.AddMessage(f"Fields to normalise: {fields_to_normalise}")
# Computing min/max for each field
summary = {}
for f in fields_to_normalise:
    arcpy.AddMessage(f"Calculating summary statistics for field: {f}")
    stats_table = arcpy.analysis.Statistics(in_table, f"in_memory/stats_{f}",
                                            [[f, "MIN"], [f, "MAX"]])
    with arcpy.da.SearchCursor(stats_table, [f"MIN_{f}", f"MAX_{f}"]) as cursor:
        for row in cursor:
            summary[f] = {"min": row[0], "max": row[1]}
    arcpy.AddMessage(f" - Min: {summary[f]['min']}, Max: {summary[f]['max']}")
arcpy.AddMessage("Summary statistics complete.")
# Normalising fields
for f in fields_to_normalise:
    min_val = summary[f]["min"]
    max_val = summary[f]["max"]
    new_field = f + "_N"
    arcpy.AddMessage(f"Normalising field... {f} → {new_field}")
    # Add the new field if it doesn't already exist
    existing_fields = [field.name for field in arcpy.ListFields(in_table)]
    if new_field not in existing_fields:
        arcpy.management.AddField(in_table, new_field, "DOUBLE")
        arcpy.AddMessage(f"  Added new field: {new_field}")
    # Normalisation expression
    expr = f"(!{f}! - {min_val}) / ({max_val} - {min_val})"
    arcpy.management.CalculateField(in_table, new_field, expr, "PYTHON3")
    arcpy.AddMessage(f"  Field {new_field} calculated successfully.")
# Defining  derived output
arcpy.SetParameterAsText(1, in_table)
arcpy.AddMessage(f"Output table set to: {in_table}")
arcpy.AddMessage("Normalisation completed")
