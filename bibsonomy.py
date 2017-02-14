# -*- coding: utf-8 -*-
from __future__ import print_function
from functools import partial
import json
from urllib.parse import quote
import requests
from requests.auth import HTTPBasicAuth

"""
from https://bitbucket.org/bibsonomy/bibsonomy-python/src/tip/bibsonomy.py
added support for searching posts

This module contains classes for interacting with the BibSonomy REST API.

The classes Post, Resource, Bookmark, Publication, Document, User,
ExtraUrl constitute the data model of BibSonomy.

The classes HttpError and Error are exceptions.

The class BibSonomy implements BibSonomy's API.

The class REST provides low-level access to the BibSonomy REST API.

The class JSON encodes/decodes the JSON provided by the REST API.
"""


class Post:

    def __init__(self, user, resource, tags, groups, create_date, change_date):
        """
        These are the required fields for each post. A post can
        contain additional fields.
        """
        self.user = user
        self.resource = resource
        self.tags = tags
        self.groups = groups
        self.create_date = create_date
        self.change_date = change_date


class Resource:
    
    def __init__(self, intra_hash, title):
        """
        Every resource has at least a title and an intra_hash.
        Further fields are required by the subclasses.
        """
        self.title = title
        self.intra_hash = intra_hash

class Bookmark(Resource):
    
    def __init__(self, intra_hash, title, url):
        Resource.__init__(self, intra_hash, title)
        self.url = url

    def __str__(self):
        return "[" + self.title + "](" + self.url + ")"

    def __repr__(self):
        return self.__str__()


class Publication(Resource):

    def __init__(self, intra_hash, entry_type, title, year, bibtex_key):
        Resource.__init__(self, intra_hash, title)
        self.entry_type = entry_type
        self.year = year
        self.bibtex_key = bibtex_key

    def __str__(self):
        return self.bibtex_key

    def __repr__(self):
        return self.__str__()


class Document:

    def __init__(self, file_name, md5_hash, href):
        """
        file_name -- the name of the document
        md5_hash -- the hashed content of the document
        href -- the URL to the document
        """
        self.file_name = file_name
        self.md5_hash = md5_hash
        self.href = href

    def __str__(self):
        return "[" + self.file_name + "](" + self.href + ")"

    def __repr__(self):
        return self.__str__()


class ExtraUrl:
    
    def __init__(self, title, date, href):
        self.title = title
        self.date = date
        self.href = href
        
    def __str__(self):
        return "[" + self.title + "](" + self.href + ")"

    def __repr__(self):
        return self.__str__()


class User:
    def __init__(self, name):
        self.name = name

class Group:
    def __init__(self, name):
        self.name = name


class BibSonomy:
    """
    Implements the BibSonomy REST API.
    """

    # maximal number of posts to download
    global _MAX
    _MAX = 10000000

    def __init__(self, rest):
        self.rest = rest
        self.json = JSON()

    def getPostsForUser(self, resource_type, user_name, tags=None, start=0, end=_MAX):
        """
        Returns the requested posts of the user.

        resource_type -- either "bookmark" or "publication"
        user_name -- the name of the user
        tags -- tags the posts should have (optional, default None)
        start -- the first post to get (default 0)
        end -- the last post to get (default 10000000)
        """
        return self._get_all_posts(partial(self.rest.getPostsForUser, resource_type=resource_type, user_name=user_name, tags=tags), start, end)

    def getPostsForTag(self, resource_type, tags, start=0, end=_MAX):
        return self._get_all_posts(partial(self.rest.getPostsForTag, resource_type=resource_type, tags=tags), start, end)

    def searchPosts(self, resource_type, search_str, start=0, end=_MAX):
        return self._get_all_posts(partial(self.rest.searchPosts, resource_type=resource_type, search_str=search_str), start, end)        

    def _get_all_posts(self, func, start, end):
        """
        Iteratively calls func until all posts are collected.
        """
        _MAX_POSTS_PER_REQUEST = self.rest.get_max_posts_per_request()
        tmp = -1
        posts = []
        # we can query at most _MAX_POSTS_PER_REQUEST post at once
        if end > start + _MAX_POSTS_PER_REQUEST:
            query_end = start + _MAX_POSTS_PER_REQUEST
        else:
            query_end = end
        # we query several times with the given end value until we
        # don't get further posts
        while (tmp == -1 or (tmp != None and len(tmp) == _MAX_POSTS_PER_REQUEST and len(posts) < end)):
            # print("start = " + str(start) + ", query_end = " + str(query_end))
            json = func(start=start, end=query_end)
            tmp = self._get_posts(json)

            # check if we got a result
            if tmp != None:
                posts.extend(tmp)
                # set new start and end: get posts in blocks of _MAX_POSTS_PER_REQUEST
                start = start + _MAX_POSTS_PER_REQUEST
                query_end = min(start + _MAX_POSTS_PER_REQUEST, end)
        # print("start = " + str(start) + ", query_end = " + str(query_end) + " (done: " + str(len(posts)) + " posts)")
        return posts
        

    def getPost(self, user_name, intra_hash):
        """
        Get exactly one post, uniquely identified by user_name and intra_hash
        """
        return self._get_posts(self.rest.getPost(user_name, intra_hash))

    def getDocument(self, document):
        """ 
        Downloads the content of a document.
        """
        return self.rest.getDocument(document)

    def getDocumentPreview(self, document, size="SMALL"):
        """
        Downloads the preview image for a document.
        
        size -- the requested preview image size (possible values:
        SMALL, MEDIUM, LARGE; default SMALL)
        
        TODO: make available sizes explicit 
        """

        return self.rest.getDocumentPreview(document, size)

    def getUser(self, user_name):
        return self.json.decode_json(self.rest.getUser(user_name))

    def _get_posts(self, json_string):
        """
        Uses JSON to transform JSON into post objects.
        """
        return self.json.decode_json(json_string)


    def createPost(self, post):
        """
        creates the post
        TODO: handling of attached documents
        """
        js = self.json.encode_json(post)
        response = self.json.decode_response(self.rest.createPost(post.user.name, js))
        return response["resourcehash"]

class JSON:
    """
    Encodes/decodes the JSON from the REST API from/into objects.
    """

    global _post_field_map, _post_fields, _user_fields
    # maps post attributes to names in JSON for those attributes where
    # the name is different
    _post_field_map = {
        "abstract" : "bibtexAbstract", 
        "inter_hash" : "interhash", 
        "intra_hash" : "intrahash"
        }
    # supported fields of posts (the mandatory fields entry_type,
    # title, year, and bibtex_key are handled separately)
    _post_fields = [
        "abstract", "address", "annote", "author", "booktitle", "chapter",
        "crossref", "doi", "edition", "editor", "howpublished",
        "institution", "journal", "key", "month", "note", "number",
        "organization", "pages", "publisher", "school", "series", "type",
        "volume", "url", "volume", "inter_hash", "intra_hash"
        ]
    # supported attributes of users
    _user_fields = ["homepage", "realname"]

    def decode_json(self, json_string):
        """
        Decode a JSON string.
        """
        return self.decode(json.loads(json_string))
    
    def decode(self, js):
        """
        Decode the JSON object delivered by BibSonomy into objects.
        """
        # check for valid result
        if "stat" in js:
            if js["stat"] == "ok":
                # decode list of posts
                if "posts" in js:
                    if "post" in js["posts"]:
                        return [self._decode_post(p) for p in js["posts"]["post"]]
                    else:
                        return []
                # decode a single post
                if "post" in js:
                    return self._decode_post(js["post"])
                # decode a single user
                if "user" in js:
                    return self._decode_user(js["user"])
                # unknown item item
                print("error: could not identify item type: " + str(js))
                return None
            else:
                # TODO: error handling
                print("error: " + js["stat"])
                return None
        print("error: no known root element found")
        return None

    def _decode_post(self, js):
        # first: decode the resource
        if "bookmark" in js:
            resource = self._decode_bookmark(js["bookmark"])
        else: 
            if "bibtex" in js:
                resource = self._decode_publication(js["bibtex"])
            else:
                resource = None
        # second: get groups (not always specified)
        if "group" in js:
            groups = [self._decode_group(g) for g in js["group"]],
        else:
            groups = ["public"]
        # third: create the post
        post = Post(
            user = self._decode_user(js["user"]),
            resource = resource,
            tags = [self._decode_tag(t) for t in js["tag"]],
            groups = groups,
            create_date = js["postingdate"],
            change_date = js["changedate"]
            )
        # attach documents
        if "documents" in js:
            post.documents = [self._decode_document(d) for d in js["documents"]["document"]]

        # attach description
        if "description" in js:
            post.description = js["description"]

        return post

    def _decode_user(self, js):
        user = User(js["name"])
        # complete user
        for field in _user_fields:
            if field in js:
                setattr(user, field, js[field])
        if "groups" in js:
            user.groups = [self._decode_group(g) for g in js["groups"]["group"]]
        return user

    def _decode_group(self, js):
        return js["name"]

    def _decode_tag(self, js):
        return js["name"]

    def _decode_bookmark(self, js):
        return Bookmark(js["intrahash"], js["title"], js["url"])

    def _decode_publication(self, js):
        # initialize publication with basic fields
        publication = Publication(
            intra_hash = js["intrahash"], 
            entry_type = js["entrytype"], 
            title = js["title"], 
            year = js["year"],
            bibtex_key = js["bibtexKey"]
            )

        # add other possible fields
        for field in _post_fields:
            # do we need to map this field's name to another name?
            if field in _post_field_map.keys():
                key = _post_field_map[field]
            else:
                key = field
            if key in js:
                setattr(publication, field, js[key])

        # TODO: map "misc" field to separate fields
        if "misc" in js:
            publication.misc = js["misc"]

        # check for extra URLs
        if "extraurls" in js:
            publication.extraurls = [self._decode_extra_url(e) for e in js["extraurls"]["url"]]

        return publication

    def _decode_document(self, js):
        return Document(js["filename"], js["md5Hash"], js["href"])

    def _decode_extra_url(self, js):
        return ExtraUrl(js["title"], js["date"], js["href"])


    def encode_json(self, obj):
        """
        Encode the given dictionary into a JSON string.
        """
        return json.dumps(self.encode(obj))

    def encode(self, obj):
        """
        Encode an object structure into a JSON dictionary.
        """
        obj_type = type(obj)
        if obj_type is Post:
            return self._encode_post(obj)
        return None

    def _encode_post(self, post):
        """
        Encode the post into the JSON object expected by BibSonomy.
        """
        # create the resource
        if type(post.resource) is Bookmark:
            resource_type = "bookmark"
            resource_data = self._encode_bookmark(post.resource)
        elif type(post.resource) is Publication:
            resource_type = "bibtex"
            resource_data = self._encode_publication(post.resource)
        # create the post
        js = {
            "post" : {
                "user" : {"name" : post.user.name}, 
                "group" : [ {"name" : group} for group in post.groups ],
                "tag" : [ {"name" : tag} for tag in post.tags ],
                resource_type : resource_data
                }
            }

        if hasattr(post, "description"):
            js["post"]["description"] = post.description

        return js

    def _encode_bookmark(self, resource):
        resource_data = {
            "title" : resource.title, 
            "url"   : resource.url
            }
        return resource_data
    
    def _encode_publication(self, resource):
        resource_data = {
            "title"     : resource.title, 
            "entrytype" : resource.entry_type,
            "year"      : resource.year,
            "bibtexKey" : resource.bibtex_key
            }

        # add all other "simple" fields
        for field in _post_fields:
            if field in _post_field_map.keys():
                key = _post_field_map[field]
            else:
                key = field
            if hasattr(resource, field):
                resource_data[key] = getattr(resource, field)

        # add extra URLs
        if hasattr(resource, "extraurls"):
            resource_data["extraurls"] = {
                "url" : [self._encode_extra_url(e) for e in resource.extraurls]
                }

        return resource_data

    def _encode_extra_url(self, extra_url):
        return {
            "title" : extra_url.title, 
            "date"  : extra_url.date, 
            "href"  : extra_url.href
            }

    def decode_response(self, json_string):
        js = json.loads(json_string)
        if "stat" in js:
            if js["stat"] == "ok":
                return js
            elif js["stat"] == "fail":
                raise HttpError(js["stat"], js["error"])
        raise Error("unknown response")
        

class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class HttpError(Error):
    def __init__(self, status, content):
        self.status = status
        self.content = content
    def __str__(self):
        if self.content != None:
            return repr(self.status) + " (" + str(self.content) + ")"
        return repr(self.status)


class REST:
    """
    Actually calls the BibSonomy REST API and returns the provided JSON.
    This class implements the HTTP query response handling.
    """


    global _MAX_POSTS_PER_REQUEST
    _MAX_POSTS_PER_REQUEST = 1000


    def __init__(self, user_name, api_key, data_format="json", protocol="https", hostname="www.bibsonomy.org", path="/api"):
        """
        Initializes the class.

        data_format -- "xml" or "json" (default "json")
        """
        self.auth = HTTPBasicAuth(user_name, api_key)
        self.format = data_format
        self.protocol = protocol
        self.hostname = hostname
        self.path = path

    def get_max_posts_per_request(self):
        """
        Returns the maximal number of posts which we can be downloaded at once.
        """
        return _MAX_POSTS_PER_REQUEST

    def _get_resource_type(self, resource_type):
        """
        Convenience method to allow sloppy specification of the resource type
        """
        if resource_type.lower() in ('bookmark', 'bookmarks', 'book', 'link', 'links', 'url'):
            return "bookmark"
        elif resource_type.lower() in ('bibtex', 'pub', 'publication', 'publications', 'publ'):
            return "bibtex"
        else:
           raise Error("unknown resource type") 

    def _get(self, path):
        """
        get string content
        """
        if path.find('?') > 0:
            delim = "&"
        else:
            delim = "?"
        
        url = self.protocol + "://" + self.hostname + self.path + path + delim + "format=" + self.format

        response = requests.get(url, auth=self.auth)
        if (response.status_code == 200):
            return response.text
        else:
            raise HttpError(response.status_code, response.text)

    def _post(self, path, payload):
        """
        post payload to path

        :param payload: data in format configured by self.format
        """
        if path.find('?') > 0:
            delim = "&"
        else:
            delim = "?"

        url = self.protocol + "://" + self.hostname + self.path + path + delim + "format=" + self.format
        
        response = requests.post(url, data=payload, auth=self.auth)
        if (response.status_code == 201):
            return response.text
        else:
            raise HttpError(response.status_code, response.text)

    def getPostsForUser(self, resource_type, user_name, tags, start=0, end=_MAX_POSTS_PER_REQUEST):
        """
        get posts of the user
        """
        # check or tags and encode them
        tag_query = ""
        if tags is not None:
            tag_query = "&tags=" + "+".join(map(quote, tags))

        # get the data
        json = self._get("/users/" + quote(user_name, '') + "/posts?resourcetype=" + quote(self._get_resource_type(resource_type)) + tag_query + "&start=" + str(start) + "&end=" + str(end))

        # TODO: error handling
        # TODO: get them all!
        return json


    def getPostsForTag(self, resource_type, tags, start=0, end=_MAX_POSTS_PER_REQUEST):
        """
        get posts for the given tag(s)
        """
        # encode tags
        tag_query = "&tags=" + "+".join(map(quote, tags))
        # get the data
        json = self._get("/posts?resourcetype=" + quote(self._get_resource_type(resource_type)) + tag_query + "&start=" + str(start) + "&end=" + str(end))
        return json

    def searchPosts(self, resource_type, search_str, start=0, end=_MAX_POSTS_PER_REQUEST):
        """
        search posts
        """

        search_query = "&search=" + search_str

        json = self._get("/posts?resourcetype=" + quote(self._get_resource_type(resource_type)) +
                         search_query + "&start=" + str(start) + "&end=" + str(end))

        return json
        
        

    def getPost(self, user_name, intra_hash):
        return self._get("/users/" + quote(user_name, '') + "/posts/" + quote(intra_hash))


    # TODO: use streaming!
    def getDocument(self, document):
        response = requests.get(document.href, auth=self.auth)
        if response.status_code == 200:
            return response.content, response.headers['content-type']
        return None, None
        

    def getDocumentPreview(self, document, size):
        response = requests.get(document.href + "?preview=" + size, auth=self.auth)
        if response.status_code == 200:
            # TODO: content type broken at the moment, returning default instead of response['content-type']
            return response.content, "image/jpeg" 
        return None

    def getUser(self, user_name):
        return self._get("/users/" + quote(user_name, ''))


    def createPost(self, user_name, post):
        """
        creates the given post
        
        :param user_name: for which user this post shall be created 
        :param post: post as a JSON or XML string (must match self.format)
        """
        return self._post("/users/" + quote(user_name, '') + "/posts", post)
