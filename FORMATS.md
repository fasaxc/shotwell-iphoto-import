Data formats
============

Shotwell PhotoTable (v20)
-------------------------

PhotoTable maintains information on all photos imported into the library. Most of its fields are self-explanatory. A couple of notes:
ImportID does not refer to a primary key of another table. Each round of imports is assigned a unique value for all photos in that import batch. The ImportID is, in fact, the time taken at the start of the import. Previously this was a conveniently unique number; now it is guaranteed, and so the date and ordering of all the import rolls can be relied upon by examining their IDs.
All transformations other than orientation (i.e. crop, color adjustment, etc.) are stored as a text KeyFile in the transformations column. This allows for new transformations to be easily added without modifying the database schema.

* md5 is a full MD5 hash of the entire photo file
* thumbnailmd5 is only of its embedded preview and exifmd5 is only of the EXIF data (not including the preview, which is commonly attached to the tail of the EXIF block).

Backlinks are persistent links to container objects, i.e. Events and Tags. These are used when a Photo has been removed from one (for example, it's been trashed or marked offline). If the Photo is returned to the main heap of photos (i.e. untrashed), these backlinks are used to restore its connections to the containers. 

Because a low application start time is seen as valuable, optimization testing showed the quickest way to load the photos was to scoop up the entire PhotoTable in one transaction and then store the entire row in memory (one row per TransformablePhoto object). This is the most significant example of database caching in Shotwell. 
                
    CREATE TABLE PhotoTable (
        id INTEGER PRIMARY KEY,
        filename TEXT UNIQUE NOT NULL,
        width INTEGER,
        height INTEGER,
        filesize INTEGER,
        timestamp INTEGER,
        exposure_time INTEGER,
        orientation INTEGER,
        original_orientation INTEGER,
        import_id INTEGER,
        event_id INTEGER,
        transformations TEXT,
        md5 TEXT,
        thumbnail_md5 TEXT,
        exif_md5 TEXT,
        time_created INTEGER,
        flags INTEGER DEFAULT 0,
        rating INTEGER DEFAULT 0,
        file_format INTEGER DEFAULT 0,
        title TEXT,
        backlinks TEXT,
        time_reimported INTEGER,
        editable_id INTEGER DEFAULT -1,
        metadata_dirty INTEGER DEFAULT 0,
        developer TEXT,
        develop_shotwell_id INTEGER DEFAULT -1,
        develop_camera_id INTEGER DEFAULT -1,
        develop_embedded_id INTEGER DEFAULT -1,
        comment TEXT
    );
    CREATE INDEX PhotoEventIDIndex ON PhotoTable (event_id);

The BackingPhotoTable is designed to hold reference information to any number of alternative backing photos for a Photo object. Currently the only use is for the editable photo, which is generated when the user asks to edit a photo with an external program. (Shotwell's non-destructive edits are flattened to this editable backing file.)

No transformations are held in the BackingPhotoTable. All transformations are held in the PhotoTable. 
       
    CREATE TABLE BackingPhotoTable (
        id INTEGER PRIMARY KEY, 
        filepath TEXT UNIQUE NOT NULL, 
        timestamp INTEGER, 
        filesize INTEGER, 
        width INTEGER, 
        height INTEGER, 
        original_orientation INTEGER, 
        file_format INTEGER, 
        time_created INTEGER
    );

In Shotwell, an event is a grouping of photos based on the time of their exposure. A primary design note of events is that a photo can only belong to one event (or none at all). Thus, rather than each row in an EventTable maintaining it's list of photos, each photo in PhotoTable maintains an event_id. Thus, EventTable is a pretty simple table, maintaining only the event's name and it's primary photo (which is displayed as a thumbnail representing the entire event). 

    CREATE TABLE EventTable (
        id INTEGER PRIMARY KEY, 
        name TEXT, 
        primary_photo_id INTEGER, 
        time_created INTEGER,
        primary_source_id TEXT,
        comment TEXT
    );


Links
-----

* [Shotwell Architecture Overview: Database](https://wiki.gnome.org/Apps/Shotwell/Architecture/Database)