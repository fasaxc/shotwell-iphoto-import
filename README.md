This repository contains a script to import an iPhoto library into Shotwell.

It preserves modified images using Shotwell's "open in external editor" 
feature.  Images that you tweaked in iPhoto will appear to have been modified 
in an external editor in Shotwell.  i.e. it will show the tweaked version by 
default and allow you to do non-destructive editing to the tweaked version
or revert to the original and lose your iPhoto tweaks.

Usage
=====

To use the script you will need to pass it

* the path of your shotwell database; the default is '~/.local/share/shotwell/data/photo.db'
* the path of the iPhoto Library directory
* a destination path to copy photos to.  E.g. "~/Pictures/"

The script will copy the photos using the directory hierarchy of the 
iPhoto Library but within your selected pictures folder.  Note: the script will
try to use a hard link rather than a copy if possible.  They means that the 
two paths will actually point at the same file.  This saves disk space but if
you subsequently modify the file under iPhoto Library, it will affect the
Shotwell copy too.

Example
=======

./iphoto_import.py --shotwell-db '~/.local/share/shotwell/data/photo.db' '~/iPhoto\ Library/' ~/Pictures/

Limitations
===========

* Movies are not imported, but they are copied to the destination.
* The script checks the version of the Shotwell and iPhoto libraries to make
  sure they are compatible.  If will reject versions it doesn't understand.
