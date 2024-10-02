"""TODO missing docstring."""
import json

import ee

from . import utils


def fromShapefile(filename, crs=None, start=None, end=None):
    """Convert an ESRI file (.shp and .dbf must be present) to a.

    ee.FeatureCollection.

    At the moment only works for shapes with less than 1000 records and doesn't
    handle complex shapes.

    :param filename: the name of the filename. If the shape is not in the
        same path than the script, specify a path instead.
    :type filename: str
    :param start:
    :return: the FeatureCollection
    :rtype: ee.FeatureCollection
    """
    import shapefile

    wgs84 = ee.Projection("EPSG:4326")
    # read the filename
    reader = shapefile.Reader(filename)
    fields = reader.fields[1:]
    field_names = [field[0] for field in fields]
    field_types = [field[1] for field in fields]
    types = dict(zip(field_names, field_types))
    features = []

    projection = utils.getProjection(filename) if not crs else crs
    # catch a string with format "EPSG:XXX"
    if isinstance(projection, str):
        if "EPSG:" in projection:
            projection = projection.split(":")[1]
    projection = "EPSG:{}".format(projection)

    # filter records with start and end
    start = start if start else 0
    if not end:
        records = reader.shapeRecords()
        end = len(records)
    else:
        end = end + 1

    if (end - start) > 1000:
        msg = "Can't process more than 1000 records at a time. Found {}"
        raise ValueError(msg.format(end - start))

    for i in range(start, end):
        # atr = dict(zip(field_names, sr.record))
        sr = reader.shapeRecord(i)
        atr = {}
        for fld, rec in zip(field_names, sr.record):
            if rec is None:
                atr[fld] = None
                continue
            fld_type = types[fld]
            if fld_type == "D":
                value = ee.Date(rec.isoformat()).millis().getInfo()
            elif fld_type in ["C", "N", "F"]:
                value = rec
            else:
                continue
            atr[fld] = value
        geom = sr.shape.__geo_interface__
        if projection is not None:
            geometry = ee.Geometry(geom, projection).transform(wgs84, 1)
        else:
            geometry = ee.Geometry(geom)
        feat = ee.Feature(geometry, atr)
        features.append(feat)

    return ee.FeatureCollection(features)


def fromGeoJSON(filename=None, data=None, crs=None):
    """Create a list of Features from a GeoJSON file. Return a python tuple.

    with ee.Feature inside. This is due to failing when attempting to create a
    FeatureCollection (Broken Pipe ERROR) out of the list. You can try creating
    it yourself casting the result of this function to a ee.List or using it
    directly as a FeatureCollection argument.

    :param filename: the name of the file to load
    :type filename: str
    :param crs: a coordinate reference system in EPSG format. If not specified
        it will try to get it from the geoJSON, and if not there it will rise
        an error
    :type: crs: str
    :return: a tuple of features.
    """
    if filename:
        with open(filename, "r") as geoj:
            content = geoj.read()
            geodict = json.loads(content)
    else:
        geodict = data

    features = []
    # Get crs from GeoJSON
    if not crs:
        filecrs = geodict.get("crs")
        if filecrs:
            name = filecrs.get("properties").get("name")
            splitcrs = name.split(":")
            cleancrs = [part for part in splitcrs if part]
            try:
                if cleancrs[-1] == "CRS84":
                    crs = "EPSG:4326"
                elif cleancrs[-2] == "EPSG":
                    crs = "{}:{}".format(cleancrs[-2], cleancrs[-1])
                else:
                    raise ValueError("{} not recognized".format(name))
            except IndexError:
                raise ValueError("{} not recognized".format(name))
        else:
            crs = "EPSG:4326"

    for n, feat in enumerate(geodict.get("features")):
        properties = feat.get("properties")
        geom = feat.get("geometry")
        ty = geom.get("type")
        coords = geom.get("coordinates")
        if ty == "GeometryCollection":
            ee_geom = utils.GEOMETRY_TYPES.get(ty)(geom, opt_proj=crs)
        else:
            if ty == "Polygon":
                coords = utils.removeZ(coords) if utils.hasZ(coords) else coords
            ee_geom = utils.GEOMETRY_TYPES.get(ty)(coords, proj=ee.Projection(crs))
        ee_feat = ee.feature.Feature(ee_geom, properties)
        features.append(ee_feat)

    return tuple(features)


def fromKML(filename=None, data=None, crs=None, encoding=None):
    """Create a list of Features from a KML file. Return a python tuple.

    with ee.Feature inside. This is due to failing when attempting to create a
    FeatureCollection (Broken Pipe ERROR) out of the list. You can try creating
    it yourself casting the result of this function to a ee.List or using it
    directly as a FeatureCollection argument.

    :param filename: the name of the file to load
    :type filename: str
    :param crs: a coordinate reference system in EPSG format. If not specified
        it will try to get it from the geoJSON, and if not there it will rise
        an error
    :type: crs: str
    :return: a tuple of features.
    """
    geojsondict = utils.kmlToGeoJsonDict(filename, data, encoding)
    features = geojsondict["features"]

    for feat in features:
        # remove styleUrl
        prop = feat["properties"]
        if "styleUrl" in prop:
            prop.pop("styleUrl")

        # remove Z value if needed
        geom = feat["geometry"]
        ty = geom["type"]
        if ty == "GeometryCollection":
            geometries = geom["geometries"]
            for g in geometries:
                c = g["coordinates"]
                utils.removeZ(c)
        else:
            coords = geom["coordinates"]
            utils.removeZ(coords)

    return fromGeoJSON(data=geojsondict, crs=crs)


def toLocal(collection, filename, filetype=None, selectors=None, path=None):
    """Download a FeatureCollection to a local file a CSV or geoJSON file.

    This uses a different method than `toGeoJSON` and `toCSV`.

    :param filetype: The filetype of download, either CSV or JSON.
        Defaults to CSV.
    :param selectors: The selectors that should be used to determine which
        attributes will be downloaded.
    :param filename: The name of the file to be downloaded
    """
    if not filetype:
        filetype = "CSV"

    url = collection.getDownloadURL(filetype, selectors, filename)
    thefile = utils.downloadFile(url, filename, filetype, path)
    return thefile
