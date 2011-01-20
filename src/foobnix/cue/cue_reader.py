'''
Created on 7  2010

@author: ivan
'''

from __future__ import with_statement
from foobnix.regui.model import FModel
import os
import logging
from foobnix.util.time_utils import normalize_time
from foobnix.util import file_utils
import chardet
import re
from foobnix.util.image_util import get_image_by_path

from foobnix.util.audio import get_mutagen_audio
from foobnix.util.fc import FC

TITLE = "TITLE"
PERFORMER = "PERFORMER"
FILE = "FILE"
INDEX = "INDEX"

class CueTrack():

    def __init__(self, title, performer, index, path):
        self.title = title
        self.performer = performer
        self.index = index
        self.duration = 0
        self.path = path

    def __str__(self):        
        return "Track: " + self.title + " " + self.performer + " " + self.index

    def get_start_time_str(self):
        return self.index[len("INDEX 01") + 1:]

    def get_start_time_sec(self):
        time = self.get_start_time_str()

        times = re.findall("([0-9]{1,2}):", time)

        if not times or len(times) < 2:
            return 0
    
        min = times[0]
        sec = times[1]
        starts = int(min) * 60 + int(sec)
        return starts
    
class CueFile():
    def __init__(self):
        self.title = None
        self.performer = None
        self.file = ""
        self.image = None
        self.tracks = []
        
    def append_track(self, track):
        self.tracks.append(track)

    def __str__(self):
        if self.title:
            logging.info("Title"+ self.title)
        if self.performer:
            logging.info("Performer"+ self.performer)
        if self.file:
            logging.info("File"+ self.file)

        return "CUEFILE: " + self.title + " " + self.performer + " " + self.file

class CueReader():

    def __init__(self, cue_file):
        self.cue_file = cue_file
        self.is_valid = True

    def get_line_value(self, str):
        first = str.find('"') or str.find("'")
        end = str.find('"', first + 1) or str.find("'", first + 1)
        return str[first + 1:end]
    
    def get_full_duration (self, file):        
        audio = get_mutagen_audio(file)
        return audio.info.length
    
    def normalize(self, cue_file):
        duration_tracks = []
        tracks = cue_file.tracks
        for i in xrange(len(tracks)):
            track = tracks[i]
            if i == len(tracks) - 1: #for last track in cue
                duration = self.get_full_duration(track.path) - track.get_start_time_sec()
            else:
                next_track = tracks[i + 1]
                if next_track.get_start_time_sec() > track.get_start_time_sec():
                    #for cue "one file - several tracks"
                    duration = next_track.get_start_time_sec() - track.get_start_time_sec()
                else: #for cue  "several files - each file involve several tracks"
                    duration = self.get_full_duration(track.path) - track.get_start_time_sec()
                        
            track.duration = duration
            if not track.path:
                track.path = cue_file.file
            duration_tracks.append(track)

        cue_file.tracks = duration_tracks
        return cue_file

    def get_common_beans(self):
        beans = []
        cue = self.parse()
        if not self.is_cue_valid():
            return []
        for i, track  in enumerate(cue.tracks):
            bean = FModel(text=track.performer + " - " + track.title, path=track.path)
            bean.artist = track.performer
            bean.tracknumber = i + 1
            bean.title = track.title
            bean.name = bean.text
            bean.start_sec = track.get_start_time_sec()
            bean.duration_sec = track.duration
            bean.time = normalize_time(track.duration)
            bean.is_file = True
            beans.append(bean)
        
        return beans

    def is_cue_valid(self):
        self.parse()
        logging.info("CUE VALID"+ str(self.cue_file) + str(self.is_valid))
        return self.is_valid

    """detect file encoding"""
    def code_detecter(self, filename):
        with open(filename) as codefile:
            data = codefile.read()
        try:
            return chardet.detect(data)['encoding']
        except:
            return "utf-8" 
         
    def parse(self):
        file = open(self.cue_file, "r")
        code = self.code_detecter(self.cue_file);
        logging.debug("File encoding is"+ str(code))

        cue_file = CueFile()

        title = ""
        performer = ""
        index = "00:00:00"
        full_file = None

        cue_file.image = get_image_by_path(self.cue_file)

        self.files_count = 0

        for line in file:
            if not self.is_valid and not line.startswith(FILE):
                continue
            else: self.is_valid = True
            
            try:
                pass
                line = unicode(line, code)
            except:
                logging.error("File encoding is too strange"+ str(code))
                pass

            line = str(line).strip()
            if not line:
                continue

            if line.startswith(TITLE):
                title = self.get_line_value(line)
                if self.files_count == 0:
                    cue_file.title = title


            if line.startswith(PERFORMER):
                performer = self.get_line_value(line)
                if self.files_count == 0:
                    cue_file.performer = performer

            if line.startswith(FILE):
                self.files_count += 1
                file = self.get_line_value(line)
                dir = os.path.dirname(self.cue_file)
                full_file = os.path.join(dir, file)
                logging.debug("CUE source"+ full_file)
                exists = os.path.exists(full_file)
                """if there no source cue file"""

                if not exists:
                    """try to find other source"""
                    ext = file_utils.get_file_extension(full_file)
                    nor = full_file[:-len(ext)]
                    logging.info("Normalized path"+ nor)
                    
                    find_source = False
                    for support_ext in FC().audio_formats:
                        try_name = nor + support_ext
                        if os.path.exists(try_name):
                            full_file = try_name
                            logging.debug("Found source for cue file name"+ try_name)
                            find_source = True
                            break;
                    
                    if not find_source:    
                        self.is_valid = False
                        self.files_count -= 1
                        logging.warn("Can't find source for "+ line+ "  Check source file name")
                        continue
                
                if self.files_count == 0:
                    cue_file.file = full_file

            if line.startswith(INDEX):
                index = self.get_line_value(line)

            if line.startswith("INDEX 01"):
                cue_track = CueTrack(title, performer, index, full_file)
                cue_file.append_track(cue_track)
        
        logging.debug("CUE file parsed "+ str(cue_file.file))
        return self.normalize(cue_file)
    
def update_id3_for_cue(beans):
    result = []
    for bean in beans:
        if bean.path and bean.path.lower().endswith(".cue"):
                reader = CueReader(bean.path)
                cue_beans = reader.get_common_beans()
                for cue in cue_beans:
                    result.append(cue)
        else:
            result.append(bean)
    return result  

