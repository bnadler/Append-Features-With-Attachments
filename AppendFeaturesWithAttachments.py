#-------------------------------------------------------------------------------
# Name:        AppendFeaturesWithAttachments
# Purpose:     Useful for downladed data from ArcGIS Online Feature Services that have
#              a preexisting feature class in a production environment. With some
#              modification ethod can be used to aggregate different feature classes with attachments
# Author:      ben nadler
#
# Created:     07/05/2015
# Copyright:   (c) ben7682 2015

#-------------------------------------------------------------------------------
import os, arcpy
arcpy.env.overwriteOutput = True

def buildWhereClauseFromList(OriginTable, PrimaryKeyField, valueList):
    """Takes a list of values and constructs a SQL WHERE
       clause to select those values within a given PrimaryKeyField
       and OriginTable."""

    # Add DBMS-specific field delimiters
    fieldDelimited = arcpy.AddFieldDelimiters(arcpy.Describe(OriginTable).path, PrimaryKeyField)

    # Determine field type
    fieldType = arcpy.ListFields(OriginTable, PrimaryKeyField)[0].type

    # Add single-quotes for string field values
    if str(fieldType) == 'String' or str(fieldType) == 'Guid':
        valueList = ["'%s'" % value for value in valueList]

    # Format WHERE clause in the form of an IN statement
    whereClause = "%s IN(%s)" % (fieldDelimited, ', '.join(map(str, valueList)))

    return whereClause


def fieldNameList(fc):
    """Convert FieldList object to list of fields"""
    fieldNames = [fld.name for fld in arcpy.ListFields(fc)]
    return fieldNames

def validate_shape_field(origin, target):
    #Ensure proper formatting for Shapefield name
    if 'Shape' in origin and 'Shape' in target:
        pass
    elif 'SHAPE' in origin and 'SHAPE' in target:
        pass
    elif 'SHAPE' in origin and 'Shape' in target:
        origin[origin.index('SHAPE')] = 'Shape'
    elif 'Shape' in origin and 'SHAPE' in target:
        origin[origin.index('Shape')] = 'SHAPE'

def appendFeatures(features,targetFc):
    """Writes each update feature to target feature class, then appends attachments to the target
    feature class attachment table with the GUID from the newly added update feature"""
    desc = arcpy.Describe(targetFc)
    #List of fields from feature class to append
    afieldNames = fieldNameList(features)
    #Cursor needs SHAPE@ not just shape field
    afieldNames.append('SHAPE@')
    #List of fields from target feature class
    tfieldNames = fieldNameList(targetFc)
    tfieldNames.append('SHAPE@')
    validate_shape_field(afieldNames, tfieldNames)    
    #Find Guid field index for later use
    oldGuidField = afieldNames.index('GlobalID') if 'GlobalID' in afieldNames else None
    tempField = None
    guids = {}
    tfields = arcpy.ListFields(targetFc)
    #find a field we can use temporarily to hold a unique ID
    for f in tfields:
        if f.type == 'String' and f.length> 5 and f.domain == '':
            tempField = f.name
            break
    editor= arcpy.da.Editor(desc.path)
    with arcpy.da.SearchCursor(features,'*') as fscur:

        editor.startEditing(False, False)

        #Insert new row and write temp ID to the field.
        #The new row will have a new GUID assigned to it
        with arcpy.da.InsertCursor(targetFc,tempField) as icur:
            for arow in fscur:

                newRow = icur.insertRow(["TEMP"])

                #Format expression to query new row
                fieldDelimited = arcpy.AddFieldDelimiters(desc.path, "OBJECTID")
                expression = "{} = {}".format(fieldDelimited,newRow)

                #Query new row and get new GUID
                with arcpy.da.SearchCursor(targetFc,'GlobalID',expression) as scur:
                    for srow in scur:
                        print "Old GUID = {} New GUID = {}".format(arow[oldGuidField], scur[0])
                        guids[arow[oldGuidField]] = scur[0]

                #Update empty row with all the information from update feature
                with arcpy.da.UpdateCursor(targetFc,'*', expression)as ucur:
                    urow = ucur.next()
                    for f in tfields:
                        fname = f.name
                        if fname != 'OBJECTID' and fname != 'GlobalID' and fname in afieldNames:
                            if fname.upper() == 'SHAPE':
                                urow[tfieldNames.index('SHAPE@')] = arow[afieldNames.index('SHAPE@')]
                            urow[tfieldNames.index(fname)] = arow[afieldNames.index(fname)]
                    ucur.updateRow(urow)

        editor.stopEditing(True)

        appendAttachments(features,targetFc,guids)

def appendAttachments(fc,tfc,guidDict):
    fc = fc + '__ATTACH'
    tfc = tfc + '__ATTACH'
    expression = None
    tfcLayer = "in_memory\\tfcLayer"
    desc = arcpy.Describe(fc)
    arcpy.Append_management(fc,tfc,"NO_TEST")

    #Make query for attachment table, looking for newly written GUIDS
    expression = buildWhereClauseFromList(tfc,"REL_GLOBALID",guidDict.keys())
    arcpy.MakeTableView_management(tfc,tfcLayer,expression)
    #editor
    editor = arcpy.da.Editor(desc.path)
    editor.startEditing(False, False)
    #Update attachments with new GUID for target features
    with arcpy.da.UpdateCursor(tfcLayer,'REL_GLOBALID') as ucur:
        for urow in ucur:
            urow[0] = guidDict[urow[0]]
            ucur.updateRow(urow)
    editor.stopEditing(True)
    return None


def main():
    updateFeatureClass = r'C:\Temp\TEST\Update.gdb\Orig'
    targetFeatureClass = r'C:\Temp\TEST\Target.gdb\Orig'

    appendFeatures(updateFeatureClass, targetFeatureClass)


if __name__ == '__main__':
    main()
