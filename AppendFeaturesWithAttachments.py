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
    """Convert FieldList object to list of fields"""
    fields = arcpy.ListFields(fc)
    fieldNames = []
    for f in fields:
        fieldNames.append(f.name)
    return fieldNames

def appendFeatures(features,targetFc):
    """Writes each update feature to target feature class, then appends attachments to the target
    feature class attachment table with the GUID from the newly added update feature"""
    import uuid
    desc = arcpy.Describe(targetFc)
    #List of fields from feature class to append
    afieldNames = fieldNameList(features)
    #List of fields from target feature class
    tfieldNames = fieldNameList(targetFc)
    #Find Guid field index for later use
    guidField = afieldNames.index('GlobalID') if 'GlobalID' in afieldNames else None
    tempField = None
    tempID = None
    newGuid = None
    tfields = arcpy.ListFields(targetFc)
    #find a field we can use temporarily to hold a unique ID
    for f in tfields:
        if f.type == 'String' and f.length> 32 and f.domain == '':
            tempField = f.name
            break
    editor= arcpy.da.Editor(desc.path)
    with arcpy.da.SearchCursor(features,'*') as fscur:

        for arow in fscur:
            editor.startEditing(False, False)

            #Insert new row and write temp ID to the field.
            #The new row will have a new GUID assigned to it
            with arcpy.da.InsertCursor(targetFc,tempField) as icur:
                #Generate random ID
                tempID = str(uuid.uuid4())[:16]
                icur.insertRow([tempID])

            #Format expression to query new row
            fieldDelimited = arcpy.AddFieldDelimiters(desc.path, tempField)
            expression = "{} = '{}'".format(fieldDelimited,tempID)

            #Query new row and get new GUID
            with arcpy.da.SearchCursor(targetFc,'GlobalID',expression) as scur:
                for srow in scur:
                    #Get new GUID
                    newGuid = scur[0]

            #Update new empty row with all the information from update feature
            with arcpy.da.UpdateCursor(targetFc,'*', expression)as ucur:
                urow = ucur.next()
                for f in tfields:
                    fname = f.name
                    if fname != 'OBJECTID' and fname != 'GlobalID' and fname in afieldNames:
                         urow[tfieldNames.index(fname)] = arow[afieldNames.index(fname)]
                ucur.updateRow(urow)

            editor.stopEditing(True)

            appendAttachments(features,arow[guidField],targetFc,newGuid)

def appendAttachments(fc,guid,tfc,newGuid):
    desc = arcpy.Describe(fc)
    #Format query
    fieldDelimited = arcpy.AddFieldDelimiters(desc.path, 'GlobalID')
    expression = "{} = '{}'".format(fieldDelimited,guid)
    #Make feature layer of feature
    flayer = arcpy.MakeFeatureLayer_management(fc, expression)
    #Select related attachments
    records = selectRelatedRecords(flayer,fc+'__ATTACH','GlobalID','REL_GLOBALID')
    editor = arcpy.da.Editor(desc.path)
    editor.startEditing(False, False)
    #Update attachments with new GUID for target features
    with arcpy.da.UpdateCursor(records,'REL_GLOBALID') as ucur:
        for urow in ucur:
            urow[0] = newGuid
            ucur.updateRow(urow)
    editor.stopEditing(True)

    #Make query for attachment table, looking for newly written GUIDS
    fieldDelimited = arcpy.AddFieldDelimiters(desc.path, 'REL_GLOBALID')
    expression = "{} = '{}'".format(fieldDelimited,newGuid)
    #Make table view of attachments
    tView = arcpy.MakeTableView_management(fc+'__ATTACH',"AppendRows", expression)
    #Append rows
    arcpy.Append_management(tView,tfc+'__ATTACH','NO_TEST')
    return None


def main():
    updateFeatureClass = r'C:\Users\ben7682\AppData\Local\Temp\Update.gdb\SEMPRA_DBO_P_GasLeak'
    targetFeatureClass = r'C:\Users\ben7682\AppData\Local\Temp\Target.gdb\SEMPRA_DBO_P_GasLeak'

    appendFeatures(updateFeatureClass, targetFeatureClass)


if __name__ == '__main__':
    main()
