import simplegeo
#import shapely.wkb, shapely.geometry
import osgeo.ogr
import sys, os, time

SIMPLEGEO_TOKEN  = ""
SIMPLEGEO_SECRET = ""

def get_ogr_feature_count (filename):
    source = osgeo.ogr.Open(filename, False)
    if not source: raise Exception("Can't open %s" % filename)

    layer = source.GetLayer(0)
    count = layer.GetFeatureCount()
    return count if count != -1 else None

def read_with_ogr (filename, fatal_errors=True):
    """Read features out of a shapefile and yield a tuple of (geometry, attrs)
       for each feature."""
    source = osgeo.ogr.Open(filename, False)
    if not source: raise Exception("Can't open %s" % filename)

    layer = source.GetLayer(0)
    defn = layer.GetLayerDefn()
    fields = [defn.GetFieldDefn(i).GetName().lower() for i in range(defn.GetFieldCount())]

    layer.ResetReading()
    ogr_feature = layer.GetNextFeature()
    while ogr_feature:
        # try:
        #   geometry = shapely.wkb.loads(ogr_feature.GetGeometryRef().ExportToWkb())
        # except Exception, e:
        #    if fatal_errors:
        #        raise
        #    else:
        #        print >>sys.stderr, "Shapely error:", e
        #    ogr_feature.Destroy()
        #    ogr_feature = layer.GetNextFeature()
        #    continue
        geometry_ref = ogr_feature.GetGeometryRef()
        geometry = (geometry_ref.GetX(), geometry_ref.GetY())
        attrs = {}
        for n, name in enumerate(fields):
            value = ogr_feature.GetField(n)
            if isinstance(value, basestring):
                try:
                    value = value.decode("utf-8")
                except UnicodeDecodeError:
                    value = value.decode("latin-1") 
            attrs[name] = value
        ogr_feature.Destroy()
        yield geometry, attrs
        ogr_feature = layer.GetNextFeature()
    source.Destroy()

def create_client(token=SIMPLEGEO_TOKEN, secret=SIMPLEGEO_SECRET):
    token = os.environ.get("SIMPLEGEO_TOKEN", token)
    secret = os.environ.get("SIMPLEGEO_SECRET", secret)
    return simplegeo.Client(token, secret)

def add_records(client, sg_layer, input_file, callback):
    records = []
    start_time = time.time()
    total_imported = 0
    feature_count = get_ogr_feature_count(input_file)
    print >>sys.stderr, "Opening %s..." % input_file
    for id, ((lon, lat), attrs) in enumerate(read_with_ogr(input_file)):
        result = callback(id, (lat, lon), attrs)
        if result is None: continue
        id, (lat, lon), attrs = result 
        record = simplegeo.Record(sg_layer, str(id), lat, lon, type="place", **attrs)
        records.append(record)
        total_imported += 1
        if len(records) == 100:
            runtime = time.time() - start_time
            records_per_sec = total_imported/runtime
            if not feature_count:
                print >>sys.stderr, "\r%d saved to %s (%.1f/s)" % (
                    total_imported, sg_layer, records_per_sec),
            else:
                remaining = (feature_count - total_imported) / records_per_sec
                print >>sys.stderr, "\r% 6d / % 6d | % 4.1f%% | % 7.1f/s | %d:%02d remaining " % (
                    total_imported, feature_count, (total_imported / float(feature_count)) * 100,
                    records_per_sec, remaining/60, int(remaining)%60),
            client.add_records(sg_layer, records)
            records = []
    if records:
        print >>sys.stderr, "Saving %d records to %s..." % (len(records), sg_layer)
        client.add_records(sg_layer, records)

if __name__ == "__main__":
    sg_layer, input_file = sys.argv[1:3]
    id_field = sys.argv[3] if len(sys.argv) >= 4 else None

    def set_id(id, coords, attrs):
        if id_field: id = attrs[id_field]
        return (id, coords, attrs)

    client = create_client()
    add_records(client, sg_layer, input_file, set_id)
