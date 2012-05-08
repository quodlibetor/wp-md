#!/usr/bin/env python

"""Convert WordPress data from xml into Markdown with YAML frontmatter.

    usage:    exporter.py blog.xml output_dir/
"""
import sys
import os
from collections import OrderedDict, defaultdict
from HTMLParser import HTMLParser
try:
    from xml.etree import cElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET

class HtmlPreProcessor(HTMLParser):
    """Replaces <pre> tags with markdown code blocks

    Pass in the html with `feed`, and read out the markdownified junk with
    `readmd()`.

    This class expects *invalid* HTML: the html fragments stored by WordPress
    in the database, with double-newlines instead of <p> tags, and no actual
    <html> or <body> elements.

    This class takes advantage of the fact that HTML is actually valid
    markdown, and does't do much processing, letting `handle_data` just store
    more or less everything that we get.
    """
    def __init__(self):
        HTMLParser.__init__(self)
        self.buffer = ""
        self.in_pre = False

    def reset(self):
        HTMLParser.reset(self)
        self.buffer = ""
        self.in_pre = False

    def readmd(self):
        return self.buffer

    def handle_data(self, data):
        """Put all of the processed data into a buffer

        While this class doesn't actually do much processing, this is where
        the result of it goes.
        """
        self.buffer += data

    def handle_entityref(self, name):
        entity = "&%s;" % name
        if self.in_pre:
            self.handle_data(entity)
        else:
            self.handle_data(self.unescape(entity))

    def handle_starttag(self, tag, attrs):
        if tag == 'pre':
            self.in_pre = True
            for attr in attrs:
                if attr[0].lower() == 'lang':
                    # pygments keys are always lowercase, this increases the
                    # chances that pre-existing languages will be recognized
                    language = attr[1].lower()
                    self.handle_data("\n~~~ { %s }\n" % language)
                    break
            else:
                self.handle_data("\n~~~\n")
        else:
            # pass the data through
            atts = ' '.join('%s="%s"' % (a, v) for a, v in attrs)
            self.handle_data("<%s %s>" % (tag, atts))

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.in_pre = False
            self.handle_data("\n~~~")
        else:
            self.handle_data("</%s>" % tag)

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

    processor = HtmlPreProcessor()

    for post in posts:
        if post['content'] is None:
            continue
        filename = post['date'] + '-' + post['title'] + '.md'
        filename = filename.replace(' ', '-').replace('/', '+')

        # yaml has weird ideas about escape chars
        post['title'] = repr(post['title']).replace(
            r"\'", "''").replace("\\", "")

        processor.reset()
        processor.feed(post['content'])
        post['content'] = processor.readmd()

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
        status = el.find("./column[@name='post_status']").text,
        if post_type == 'revision':
            id = el.find("./column[@name='post_parent']").text
            if status == u'inherit':
                status = posts[id][u'status']

        posts[id] = {
            u'date': el.find("./column[@name='post_date']").text,
            u'author': el.find("./column[@name='post_author']").text,
            u'content': el.find("./column[@name='post_content']").text,
            u'title': el.find("./column[@name='post_title']").text,
            u'status': status,
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
    if len(sys.argv) < 3:
        print __doc__
        exit(1)

    thefile = sys.argv[1]
    outdir  = sys.argv[2]
    main_xml(thefile, outdir)
