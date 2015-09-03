#!/usr/bin/env python

"""Translate Wikipedia edit history XML files to JSON.

This script assumes that the Wikipedia edit history XML files are ordered as
follows:

    <mediawiki>
        ...
        <page>
            <title></title>
            <ns></ns>
            <id></id>
            <redirect title="" /> <!-- Optional -->
            <revision>
                <id>236939</id>
                <timestamp></timestamp>
                <contributor>
                    <username></username>
                    <id></id>
                </contributor>
                <comment></comment>
                <model></model>
                <format></format>
                <text xml:space="preserve"></text>
                <sha1></sha1>
            </revision>
            ...
        </page>
    </mediawiki>

Specifically, it assumes that:

    1) the title, ns, id, redirect tags for a page appear before the revisions
    2) the revisions for a page are order from oldest to newest

This is the format the files are in when they are downloaded from:
https://dumps.wikimedia.org/enwiki/latest/

Example:
    This script is designed to be placed in the middle of a series of piped
    commands. Most often it will read data on stdin from a 7zip program and
    output JSON on stdout, often to a file or compression program, as follows:

        $ 7z e -so input_file.7z | xml_to_json.py | gzip > output_file.json.gz

Attributes:
    NAMESPACE (str): The default namespace of all tags in the Wikipedia edit
        history XML file.

"""

from copy import deepcopy
import sys
import xml.etree.cElementTree as ET
import json


NAMESPACE = "{http://www.mediawiki.org/xml/export-0.10/}"

# JSON revision object
revision = {
        # General article information
        "article_title": None,  # string
        "article_id": None,  # int
        "article_namespace": None,  # int
        "redirect_target": None,  # String
        # Revision specific information
        "revision_id": None,  # int
        "parent_id": None,  # int
        "timestamp": None,  # date and time
        "user_name": None,  # string or ip as string
        "user_id": None,  # int if user, otherwise None
        "comment": None,  # string
        "minor": False,  # bool
        }


def fill_rev(revision, element, in_revision_tree, namespace=''):
    """Fill the fields of a revision dictionary given an element from an XML
    Element Tree.

    Args:
        - revision (dict): A revision dictionary with fields already in place.
        - element (ElementTree Element): An element from ElementTree.
        - in_revision_tree (bool): True if inside a <revision> element,
            otherwise should be set to False.
        - namespace (Optional[str]): The XML name space that the tags exist in.

    Returns:
        None

    """
    if element.tag == namespace + "id":
        if in_revision_tree:
            revision["revision_id"] = int(element.text)
        else:
            revision["article_id"] = int(element.text)
    elif element.tag == namespace + "parentid":
        revision["parent_id"] = int(element.text)
    elif element.tag == namespace + "timestamp":
        revision["timestamp"] = element.text
    elif element.tag == namespace + "minor":
        revision["minor"] = True
    elif element.tag == namespace + "comment":
        revision["comment"] = element.text
    elif element.tag == namespace + "contributor":
        for child in element:
            if child.tag == namespace + "username" or child.tag == namespace + "ip":
                revision["user_name"] = child.text
            elif child.tag == namespace + "id":
                revision["user_id"] = int(child.text)
    elif element.tag == namespace + "title":
        revision["article_title"] = element.text
    elif element.tag == namespace + "ns":
        revision["article_namespace"] = int(element.text)
    elif element.tag == namespace + "redirect":
        revision["redirect_target"] = element.get("title")


# We _assumes_ that the XML tree is ordered in the same way as the dumps from
# en.wikipedia.org, specifically:
#
#    <page>
#      <title>Hermes (mythology)</title>
#      <ns>0</ns>
#      <id>38235488</id>
#      <!-- redirect is optional -->
#      <redirect title="Hermes" />
#      <revision>
#        ...
#      </revision>
#    </page>


in_page = False
in_revision = False
for event, elem in ET.iterparse(sys.stdin, events=("start", "end")):
    # When a page element is started we set up a new revisions dictionary
    # with the article title, id, namespace, and redirection information.
    # This dictionary is then deepcopied for each revision. It is deleted
    # when a page ends.
    if event == "start" and elem.tag == NAMESPACE + "page":
        in_page = True
        page_rev = deepcopy(revision)
    elif event == "end" and elem.tag == NAMESPACE + "page":
        in_page = False
        del page_rev

    # When a revision starts we copy the current page dictionary and fill
    # it. Revisions are sorted last in the XML tree, so the page_rev
    # dictionary will be filled out by the time we reach them.
    if event == "start" and elem.tag == NAMESPACE + "revision":
        in_revision = True
        cur_rev = deepcopy(page_rev)
    elif event == "end" and elem.tag == NAMESPACE + "revision":
        for child in elem:
            fill_rev(cur_rev, child, in_revision, NAMESPACE)
            child.clear()
        in_revision = False
        print json.dumps(cur_rev)
        del cur_rev
        elem.clear()

    # Otherwise if we are not in a revision, but are in a page, then the
    # elements are about the article and we save them into the page_rev
    # dictionary
    if event == "end" and in_page and not in_revision:
        fill_rev(page_rev, elem, in_revision, NAMESPACE)
        elem.clear()
