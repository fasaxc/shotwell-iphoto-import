#!/usr/bin/env python

import sqlite3
import argparse
import logging
from os.path import join as join_path
import os.path
import sys
import time
import shutil
import plistlib
import datetime
from PIL import Image #@UnresolvedImport
from pyexiv2.metadata import ImageMetadata
import hashlib
import mimetypes
import re

# Shotwell's orientation enum
TOP_LEFT = 1
TOP_RIGHT = 2
BOTTOM_RIGHT = 3
BOTTOM_LEFT = 4
LEFT_TOP = 5
RIGHT_TOP = 6
RIGHT_BOTTOM = 7
LEFT_BOTTOM = 8

FILE_FORMAT = {
    "image/jpeg": 0,
    # Raw = 1
    "image/png": 2,
    "image/tiff": 3,
    "image/x-ms-bmp": 4,
}

_log = logging.getLogger("iphotoimport")

SUPPORTED_SHOTWELL_SCHEMAS = (16, )

def exif_datetime_to_time(dt):
    if isinstance(dt, basestring):
        # Looks like the exif lib couldn't parse the date.  I've seen dates 
        # like 2007:00:00 00:00:00.  Let's try that.
        match = re.match(r'(\d{4}):(\d\d):(\d\d) (\d\d):(\d\d):(\d\d)', dt)
        if match:
            y, m, d, h, mn, s = [int(x) for x in match.groups()]
            m += 1 # datetime uses 1-indexed months/days
            assert m <= 12
            d += 1
            assert d <= 31
            dt = datetime.datetime(y, m, d, h, mn, s)
        else:
            raise Exception("Failed to parse date %s" % dt)
    
    return time.mktime(dt.timetuple())

def md5_for_file(filename, block_size=2**20):
    with open(filename, "rb") as f:
        md5 = hashlib.md5()
        while True:
            data = f.read(block_size)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()

def import_photos(iphoto_dir, shotwell_db, photos_dir):
    # Sanity check the iPhoto dir and Shotwell DB.
    _log.debug("Performing sanity checks on iPhoto and Shotwell DBs.")
    now = time.time()
    album_data_filename = join_path(iphoto_dir, "AlbumData.xml")
    if not os.path.exists(album_data_filename):
        _log.error("Failed to find expected file inside iPhoto library: %s", 
                   album_data_filename)
        sys.exit(1)
    if not os.path.exists(shotwell_db):
        _log.error("Shotwell DB not found at %s", shotwell_db)
        sys.exit(2)
    db = sqlite3.connect(shotwell_db) #@UndefinedVariable
    with db:
        cursor = db.execute("SELECT schema_version from VersionTable;")
        schema_version = cursor.fetchone()[0]
        if schema_version not in SUPPORTED_SHOTWELL_SCHEMAS:
            _log.error("Shotwell DB uses unsupported schema version %s. "
                       "Giving up, just to be safe.", schema_version)
            sys.exit(3)
        _log.debug("Sanity checks passed.")
        
        # Back up the Shotwell DB.
        fmt_now = time.strftime('%Y-%m-%d_%H%M%S')
        db_backup = "%s.iphotobak_%s" % (shotwell_db, fmt_now)
        _log.debug("Backing up shotwell DB to %s", db_backup)
        shutil.copy(shotwell_db, db_backup)
        _log.debug("Backup complete")
        
        # Load and parse the iPhoto DB.
        _log.debug("Loading the iPhoto library file. Might take a while for a large DB!")
        album_data = plistlib.readPlist(album_data_filename)
        _log.debug("Finished loading the iPhoto library.")
        path_prefix = album_data["Archive Path"]
        def fix_prefix(path, new_prefix=iphoto_dir):
            if path:
                if path[:len(path_prefix)] != path_prefix:
                    raise AssertionError("Path %s didn't begin with %s" % (path, path_prefix))
                path = path[len(path_prefix):]
                path = join_path(new_prefix, path.strip(os.path.sep)) 
            return path
        photos = {} # Map from photo ID to photo info.
        
        
#                  id = 224
#            filename = /home/shaun/Pictures/Photos/2008/03/24/DSCN2416 (Modified (2)).JPG
#               width = 1600
#              height = 1200
#            filesize = 480914
#           timestamp = 1348718403
#       exposure_time = 1206392706
#         orientation = 1
#original_orientation = 1
#           import_id = 1348941635
#            event_id = 3
#     transformations = 
#                 md5 = 3ca3cf05312d0c1a4c141bb582fc43d0
#       thumbnail_md5 = 
#            exif_md5 = cec27a47c34c89f571c0fd4e9eb4a9fe
#        time_created = 1348941635
#               flags = 0
#              rating = 0
#         file_format = 0
#               title = 
#           backlinks = 
#     time_reimported = 
#         editable_id = 1
#      metadata_dirty = 1
#           developer = SHOTWELL
# develop_shotwell_id = -1
#   develop_camera_id = -1
# develop_embedded_id = -1
        skipped = []
        for key, i_photo in album_data["Master Image List"].items():
            mod_image_path = fix_prefix(i_photo.get("ImagePath", None))
            orig_image_path = fix_prefix(i_photo.get("OriginalPath", None))
            
            new_mod_path = fix_prefix(i_photo.get("ImagePath"), new_prefix=photos_dir)
            new_orig_path = fix_prefix(i_photo.get("OriginalPath", None), 
                                       new_prefix=photos_dir)
            
            if not orig_image_path:
                orig_image_path = mod_image_path
                new_orig_path = new_mod_path
                new_mod_path = None
                mod_image_path = None
                mod_file_size = None
            else:
                mod_file_size = os.path.getsize(mod_image_path)
                
            mime, _ = mimetypes.guess_type(orig_image_path)
                
            sys.stdout.write('.')
            sys.stdout.flush()
            if mime not in ("image/jpeg", "image/png", "image/x-ms-bmp", "image/tiff"):
                print
                _log.error("Skipping %s, it's not an image %s", orig_image_path, mime)
                skipped.append(orig_image_path)
                continue
            
            caption = i_photo.get("Caption", "")
            
            img = Image.open(orig_image_path)
            w, h = img.size
            
            md5 = md5_for_file(orig_image_path)
            orig_timestamp = int(os.path.getmtime(orig_image_path))
            
            mod_w, mod_h, mod_md5, mod_timestamp = None, None, None, None
            if mod_image_path:
                try:
                    mod_img = Image.open(mod_image_path)
                except Exception:
                    _log.error("Failed to open modified image %s, skipping", mod_image_path)
                    orig_image_path = mod_image_path
                    new_orig_path = new_mod_path
                    new_mod_path = None
                    mod_image_path = None
                    mod_file_size = None
                else:
                    mod_w, mod_h = mod_img.size
                    mod_md5 = md5_for_file(mod_image_path)
                    mod_timestamp = int(os.path.getmtime(mod_image_path))
            
            file_format = FILE_FORMAT.get(mime, -1)
            if file_format == -1:
                raise Exception("Unknown image type %s" % mime)
            
            photo = {"orig_image_path": orig_image_path,
                           "mod_image_path": mod_image_path,
                           "new_mod_path": new_mod_path,
                           "new_orig_path": new_orig_path,
                           "orig_file_size": os.path.getsize(orig_image_path),
                           "mod_file_size": mod_file_size,
                           "mod_timestamp": mod_timestamp,
                           "orig_timestamp": orig_timestamp,
                           "caption": caption,
                           "rating": i_photo["Rating"],
                           "event": i_photo["Roll"],
                           "date": parse_date(i_photo["DateAsTimerInterval"]),
                           "width": w,
                           "height": h,
                           "mod_width": mod_w,
                           "mod_height": mod_h,
                           "orig_md5": md5,
                           "mod_md5": md5,
                           "file_format": file_format,
                           "time_created": now,
                           "import_id": now,
                           }
            def read_metadata(path, photo, prefix="orig_"):
                photo[prefix + "orientation"] = 1
                photo[prefix + "original_orientation"] = 1
                try:
                    meta = ImageMetadata(path)
                    meta.read()
                    try:
                        photo[prefix + "orientation"] = meta["Exif.Image.Orientation"].value
                        photo[prefix + "original_orientation"] = meta["Exif.Image.Orientation"].value
                    except KeyError:
                        print
                        _log.debug("Failed to read the orientation from %s" % path)
                    exposure_dt = meta["Exif.Image.DateTime"].value
                    photo[prefix + "exposure_time"] = exif_datetime_to_time(exposure_dt)
                except KeyError:
                    pass
                except Exception:
                    print
                    _log.exception("Failed to read date from %s", path)
                    raise
                    
            try:
                read_metadata(orig_image_path, photo, "orig_")
                if mod_image_path:
                    read_metadata(mod_image_path, photo, "mod_")
            except Exception:
                _log.error("**** Skipping %s" % orig_image_path)
                continue
            
            photos[key] = photo
        
        events = {}
        for event in album_data["List of Rolls"]:
            key = event["RollID"]
            events[key] = {
                "date": parse_date(event["RollDateAsTimerInterval"]),
                "key_photo": event["KeyPhotoKey"], 
                "photos": event["KeyList"],
                "name": event["RollName"]
            }
            for photo_key in event["KeyList"]:
                assert photo_key not in photos or photos[photo_key]["event"] == key
        
        # Insert into the Shotwell DB.
        for _, event in events.items():
            c = db.execute("""
                INSERT INTO EventTable (time_created, name) 
                VALUES (?, ?)
            """, (event["date"], event["name"]))
            assert c.lastrowid is not None
            event["row_id"] = c.lastrowid
            for photo_key in event["photos"]:
                if photo_key in photos:
                    photos[photo_key]["event_id"] = event["row_id"]

        
            
        for key, photo in photos.items():
            # The BackingPhotoTable
#                  id = 1
#            filepath = /home/shaun/Pictures/Photos/2008/03/24/DSCN2416 (Modified (2))_modified.JPG
#           timestamp = 1348968706
#            filesize = 1064375
#               width = 1600
#              height = 1200
#original_orientation = 1
#         file_format = 0
#        time_created = 1348945103
            editable_id = -1
            if photo["mod_image_path"] is not None:
                # This photo has a backing image
                c = db.execute("""
                    INSERT INTO BackingPhotoTable (filepath,
                                                   timestamp,
                                                   filesize,
                                                   width,
                                                   height,
                                                   original_orientation,
                                                   file_format,
                                                   time_created)
                    VALUES (:new_mod_path,
                            :mod_timestamp,
                            :mod_file_size,
                            :mod_width,
                            :mod_height,
                            :mod_original_orientation,
                            :file_format,
                            :time_created)
                """, photo)
                editable_id = c.lastrowid
            
            photo["editable_id"] = editable_id
            try:
                c = db.execute("""
                    INSERT INTO PhotoTable (filename,
                                            width,
                                            height,
                                            filesize,
                                            timestamp,
                                            exposure_time,
                                            orientation,
                                            original_orientation,
                                            import_id,
                                            event_id,
                                            md5,
                                            time_created,
                                            flags,
                                            rating,
                                            file_format,
                                            title,
                                            editable_id,
                                            metadata_dirty,
                                            developer,
                                            develop_shotwell_id,
                                            develop_camera_id,
                                            develop_embedded_id)
                    VALUES (:new_orig_path,
                            :width,
                            :height,
                            :orig_file_size,
                            :orig_timestamp,
                            :orig_exposure_time,
                            :orig_orientation,
                            :orig_original_orientation,
                            :import_id,
                            :event_id,
                            :orig_md5,
                            :time_created,
                            0,
                            :rating,
                            :file_format,
                            :caption,
                            :editable_id,
                            1,
                            'SHOTWELL',
                            -1,
                            -1,
                            -1);
                """, photo)
            except Exception:
                _log.exception("Failed to insert photo %s" % photo)
                raise
            
            
        
        print >> sys.stderr, "Skipped these files:", skipped
        db.rollback()
        # Commit the transaction.
    
    
def parse_date(timer_interval):
    dt = datetime.datetime(2001,1,1) + datetime.timedelta(seconds=timer_interval) 
    return time.mktime(dt.timetuple())
    
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import photos from iPhoto to Shotwell.')
    parser.add_argument('iphoto_dir', metavar='IPHOTO_DIR', type=str, 
                       help='path to the the iPhoto Library directory')
    parser.add_argument('--shotwell-db', dest='shotwell_db',
                       default=None, action='store', 
                       help='location of the shotwell photos.db file, '
                            'defaults to ~/.local/shared/shotwell/photos.db')
    parser.add_argument('photos_dir', metavar='PHOTOS_DIR', type=str,
                       default=None, action='store', 
                       help='location of your photos dir')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG)
    import_photos(args.iphoto_dir, args.shotwell_db, args.photos_dir)