#!/usr/bin/python3.2

import argparse
import logging

_log = logging.getLogger("iphotoimport")

def import_photos(iphoto_dir, shotwell_db):
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import photos from iPhoto to Shotwell.')
    parser.add_argument('iphoto_dir', metavar='IPHOTO_DIR', type=str, 
                       help='path to the the iPhoto Library directory')
    parser.add_argument('--shotwell-db', dest='shotwell_db',
                       default=None, action='store', 
                       help='location of the shotwell photos.db file, '
                            'defaults to ~/.local/shared/shotwell/photos.db')
    args = parser.parse_args()
    
    logging.basicConfig()
    import_photos(args.iphoto_dir, args.shortwell_db)