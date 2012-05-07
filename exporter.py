#!/usr/bin/env python

"""Convert MySQL database into Markdown with YAML frontmatter.
"""
import sys
import os
from collections import OrderedDict, defaultdict
try:
    from xml.etree import cElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET


def export_mynt(posts, base_dir):
    """Write blog stuff to mynt-like files

    Expects an iterable of dict-like objects that have the following fields:

        - `title` <string>
        - `tags`  <list>
        - `content` <string>

    All of these should be in a format ready to write.
    """

    template = u"""---
layout: post.html
title: %(title)s
tags: %(tags)s
---

%(content)s
"""
    opj = os.path.join

    for post in posts:
        if post['content'] is None:
            continue
        filename = post['date'] + '-' + post['title'] + '.md'
        filename = filename.replace(' ', '-').replace('/', '+')
        post['title'] = repr(post['title']).replace(
            r"\'", "''").replace("\\", "")
        with open(opj(base_dir, filename), 'w') as fh:
            out = template % post
            fh.write(out.encode('utf-8'))

def get_props_from_wp_xml(root):
    """This is where I reimplement database joins on top of xml

    I try to be nice, and this is what I get? Sheesh. I hope someboyd who
    doesn't have a mysql driver is grateful.
    """
    els = root.findall(".//table[@name='wp_posts']")
    posts = OrderedDict()

    terms = {}
    for term in root.findall(".//table[@name='wp_terms']"):
        key = term.find("./column[@name='term_id']").text
        tag = term.find("./column[@name='slug']").text
        terms[key] = tag

    taxes = {} # term taxonomy is the relationship between terms and parents
    categories  = {}
    for taxonomy in root.findall(".//table[@name='wp_term_taxonomy']"):
        tax = taxonomy.find("./column[@name='taxonomy']").text
        if tax == 'post_tag':
            key = taxonomy.find("./column[@name='term_taxonomy_id']").text
            term_id = taxonomy.find("./column[@name='term_id']").text
            taxes[key] = terms[term_id]

        elif tax == 'category':
            key = taxonomy.find("./column[@name='term_taxonomy_id']").text
            term_id = taxonomy.find("./column[@name='term_id']").text
            categories[key] = terms[term_id]

    all_tags = {}
    all_tags.update(taxes)
    all_tags.update(categories)
    post_tags = defaultdict(list)
    for relation in root.findall(".//table[@name='wp_term_relationships']"):
        try:
            obj_id  = relation.find("./column[@name='object_id']").text
            term_id = relation.find("./column[@name='term_taxonomy_id']").text
            term = all_tags[term_id] # should throw KeyError for links
            post_tags[obj_id].append(term)
        except KeyError:
            pass

    for el in els:
        id = el.find("./column[@name='ID']").text
        post_type = el.find("./column[@name='post_type']").text
        if post_type == 'revision':
            id = el.find("./column[@name='post_parent']").text

        posts[id] = {
            u'date': el.find("./column[@name='post_date']").text,
            u'author': el.find("./column[@name='post_author']").text,
            u'content': el.find("./column[@name='post_content']").text,
            u'title': el.find("./column[@name='post_title']").text,
            u'tags': post_tags[id]
            }

        # this is currently BROKEN
        # content = HTMLParser().unescape(posts[id]['content'])
        # posts[id]['content'] = html2text(content)
    return posts.itervalues()

def main_xml(fname, outdir):
    root = ET.parse(fname).getroot()
    export_mynt(get_props_from_wp_xml(root), outdir)

if __name__ == '__main__':
    thefile = sys.argv[1]
    outdir  = sys.argv[2]
    main_xml(thefile, outdir)
