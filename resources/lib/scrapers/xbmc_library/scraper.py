# -*- coding: utf-8 -*-

__scriptID__ = "script.cinema.experience"
__modname__ = "XBMC Library scraper"
"""
XBMC Movie Library Trailer Scraper
"""

import os, sys, time, re, urllib, traceback, datetime
from random import shuffle, random
from xml.sax.saxutils import unescape
if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson

import xbmc, xbmcvfs

logmessage = "[ " + __scriptID__ + " ] - [ " + __modname__ + " ]"

trailer_settings         = sys.modules[ "__main__" ].trailer_settings
BASE_CACHE_PATH          = sys.modules[ "__main__" ].BASE_CACHE_PATH
BASE_RESOURCE_PATH       = sys.modules[ "__main__" ].BASE_RESOURCE_PATH
BASE_CURRENT_SOURCE_PATH = sys.modules[ "__main__" ].BASE_CURRENT_SOURCE_PATH
sys.path.append( os.path.join( BASE_RESOURCE_PATH, "lib" ) )
from ce_playlist import _get_thumbnail, _get_trailer_thumbnail
from utils import list_to_string, log

__useragent__ = "QuickTime/7.2 (qtver=7.2;os=Windows NT 5.1Service Pack 3)"

class Main:
    log( "%s - XBMC Movie Library Trailer Scraper" % logmessage, xbmc.LOGNOTICE )
    
    def __init__( self, equivalent_mpaa=None, mpaa=None, genre=None, settings=None, movie=None ):
        self.settings = settings
        if settings['trailer_limit_mpaa']:
            self.mpaa = mpaa
        else:
            self.mpaa = ""
        if settings['trailer_limit_genre'] and settings['trailer_rating'] == '--':
            self.genre = ""
        else:
            self.genre = genre.split( " / " )[ 0 ]
        self.movie = movie
        #  initialize our trailer list
        self.trailers = []
        self.watched_path = os.path.join( BASE_CURRENT_SOURCE_PATH, self.settings[ "trailer_scraper" ] + "_watched.txt" )
        

    def fetch_trailers( self ):        
        # get watched list
        self._get_watched()
        count = 0
        if self.settings[ "trailer_unwatched_movie_only" ]:
            jsonquery = '''{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "sort": { "order": "ascending", "method": "title", "ignorearticle": true }, "properties" : ["trailer", "mpaa", "genre", "thumbnail", "plot"], "filter": { "and": [  { "field": "playcount", "operator": "is", "value": "0" }, { "field": "mpaarating", "operator": "contains", "value": "%s" }, { "field": "genre", "operator": "contains", "value": "%s" }, { "field": "hastrailer", "operator": "true", "value": "true" } ] }  }, "id": 1}''' % ( self.mpaa, self.genre )
        else:
            jsonquery = '''{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "sort": { "order": "ascending", "method": "title", "ignorearticle": true }, "properties" : ["trailer", "mpaa", "genre", "thumbnail", "plot"], "filter": { "and": [  { "field": "mpaarating", "operator": "contains", "value": "%s" }, { "field": "genre", "operator": "contains", "value": "%s" }, { "field": "hastrailer", "operator": "true", "value": "true" } ] }  }, "id": 1}''' % ( self.mpaa, self.genre )
        jsonresponse = xbmc.executeJSONRPC( jsonquery )
        data = simplejson.loads( jsonresponse )
        if data.has_key('result'):
            if data['result'].has_key('movies'):
                trailers = data['result']['movies']
                shuffle( trailers )
                for trailer in trailers:
                    trailer_rating = trailer['mpaa']
                    # shorten MPAA/BBFC ratings
                    if trailer_rating == "":
                        trailer_rating = "NR"
                    #MPAA    
                    if trailer_rating.startswith("Rated"):
                        trailer_rating = trailer_rating.split( " " )[ 1 - ( len( trailer_rating.split( " " ) ) == 1 ) ]
                        trailer_rating = ( trailer_rating, "NR", )[ trailer_rating not in ( "G", "PG", "PG-13", "R", "NC-17", "Unrated", ) ]
                    #BBFC
                    elif trailer_rating.startswith("UK"):
                        if trailer_rating.startswith( "UK:" ):
                            trailer_rating = trailer_rating.split( ":" )[ 1 - ( len( trailer_rating.split( ":" ) ) == 1 ) ]
                        else:
                            trailer_rating = trailer_rating.split( " " )[ 1 - ( len( trailer_rating.split( " " ) ) == 1 ) ]
                        trailer_rating = ( trailer_rating, "NR", )[ trailer_rating not in ( "12", "12A", "PG", "15", "18", "R18", "MA", "U", ) ]
                    elif trailer_rating.startswith("FSK"):
                        if trailer_rating.startswith( "FSK:" ):
                            trailer_rating = trailer_rating.split( ":" )[ 1 - ( len( trailer_rating.split( ":" ) ) == 1 ) ]
                        else:
                            trailer_rating = trailer_rating.split( " " )[ 1 - ( len( trailer_rating.split( " " ) ) == 1 ) ]
                    else:
                        trailer_rating = ( trailer_rating, "NR", )[ trailer_rating not in ( "0", "6", "12", "12A", "PG", "15", "16", "18", "R18", "MA", "U", ) ]
                    # add trailer to our final list
                    if trailer['trailer'].startswith( 'plugin://' ) and not self.settings['trailer_skip_youtube']:
                        continue
                    else:
                        trailer_info = ( xbmc.getCacheThumbName( trailer['trailer'] ), # id
                                         trailer['label'], # title
                                         trailer['trailer'], # trailer
                                         trailer['thumbnail'], # thumb
                                         trailer['plot'], # plot
                                         '', # runtime
                                         trailer_rating, # mpaa
                                         '', # release date
                                         '', # studio
                                         utils.list_to_string( trailer['genre'] ), # genre
                                         'Trailer', # writer
                                         '', # director 32613
                                        )
                        self.trailers += [ trailer_info ]
                        # add id to watched file TODO: maybe don't add if not user preference
                        self.watched += [ xbmc.getCacheThumbName( trailer['trailer'] ) ]
                        # increment counter
                        count += 1
                        # if we have enough exit
                        if count == self.settings[ "trailer_count" ]:
                           break
            else:
                log( "No Movie Trailers found", xbmc.LOGNOTICE )
            self._save_watched()
            return self.trailers
        else:
            log( "No results found", xbmc.LOGNOTICE )
            return []

    def _get_watched( self ):
        self.watched = utils.load_saved_list( self.watched_path, "Trailer Watched List" )

    def _reset_watched( self ):
        log( "%s - Resetting Watched List" % logmessage, xbmc.LOGNOTICE )
        if xbmcvfs.exists( self.watched_path ):
            xbmcvfs.delete( self.watched_path )
            self.watched = []

    def _save_watched( self ):
        utils.save_list( self.watched_path, self.watched, "Watched Trailers" )

