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

def selectRelatedRecords(OriginTable, DestinationTable, PrimaryKeyField, ForiegnKeyField):
    """Defines the record selection from the record selection of the OriginTable
      and applys it to the DestinationTable using a SQL WHERE clause built
      in the previous defintion"""

    # Set the SearchCursor to look through the selection of the OriginTable
    sourceIDs = set([row[0] for row in arcpy.da.SearchCursor(OriginTable, PrimaryKeyField)])

    # Establishes the where clause used to select records from DestinationTable
    whereClause = buildWhereClauseFromList(DestinationTable, ForiegnKeyField, sourceIDs)

    # Process: Select Layer By Attribute
    return arcpy.MakeTableView_management(DestinationTable, "NEW_SELECTION", whereClause)

def fieldNameList(fc):
    fields = arcpy.ListFields(fc)
    fieldNames = []
    for f in fields:
        fieldNames.append(f.name)
    return fieldNames

def appendFeatures(features,targetFc):
    import uuid
    desc = arcpy.Describe(targetFc)
    afieldNames = fieldNameList(features)
    tfieldNames = fieldNameList(targetFc)
    guidField = afieldNames.index('GlobalID') if 'GlobalID' in afieldNames else None
    tempField = None
    tempID = None
    tfields = arcpy.ListFields(targetFc)
    for f in tfields:
        if f.type == 'String' and f.length> 32 and f.domain == '':
            tempField = f.name
            break
    with arcpy.da.SearchCursor(features,'*') as fscur:
        for arow in fscur:
            editor= arcpy.da.Editor(desc.path)
            editor.startEditing(False, False)
            with arcpy.da.InsertCursor(targetFc,tempField) as icur:
                tempID = str(uuid.uuid4())[:16]
                icur.insertRow([tempID])
            fieldDelimited = arcpy.AddFieldDelimiters(desc.path, tempField)
            expression = "{} = '{}'".format(fieldDelimited,tempID)

            with arcpy.da.SearchCursor(targetFc,'GLOBALID',expression) as scur:
                for srow in scur:
                    appendAttachments(features,arow[guidField],targetFc,scur[0])

            with arcpy.da.UpdateCursor(targetFc,'*', expression)as ucur:
                urow = ucur.next()
                for f in tfields:
                    fname = f.name
                    if fname != 'OBJECTID' and fname != 'GlobalID' and fname in afieldNames:
                         urow[tfieldNames.index(fname)] = arow[afieldNames.index(fname)]
                ucur.updateRow(urow)
            editor.stopEditing(True)
            with arcpy.da.SearchCursor(targetFc,'GLOBALID',expression) as scur:
                for srow in scur:
                    appendAttachments(features,arow[guidField],targetFc,scur[0])

def appendAttachments(fc,guid,tfc,newGuid):
    desc = arcpy.Describe(fc)
    fieldDelimited = arcpy.AddFieldDelimiters(desc.path, 'GlobalID')
    expression = "{} = '{}'".format(fieldDelimited,guid)
    flayer = arcpy.MakeFeatureLayer_management(fc, expression)
    records = selectRelatedRecords(flayer,fc+'__ATTACH','GlobalID','REL_GLOBALID')
    print arcpy.GetCount_management(records)
    editor = arcpy.da.Editor(desc.path)
    editor.startEditing(False, False)
    with arcpy.da.UpdateCursor(records,'REL_GLOBALID') as ucur:
        for urow in ucur:
            urow[0] = newGuid
            ucur.updateRow(urow)
    editor.stopEditing(True)

    fieldDelimited = arcpy.AddFieldDelimiters(desc.path, 'REL_GLOBALID')
    expression = "{} = '{}'".format(fieldDelimited,newGuid)
    flayer = arcpy.MakeTableView_management(fc+'__ATTACH',"AppendRows", expression)
    arcpy.Append_management(flayer,tfc+'__ATTACH','NO_TEST')
    return None


def main():
    appendFeatures(UpdateFeatureClass, TargetFeatureClass)


if __name__ == '__main__':
    main()
