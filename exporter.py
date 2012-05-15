#!/usr/bin/env python

"""Convert WordPress data from xml into Markdown with YAML frontmatter.

    usage:    exporter.py blog.xml output_dir/ [output_format]
"""
import sys
import os
import re
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
    def __init__(self, markdown_interpreter='misaka'):
        HTMLParser.__init__(self)
        self.buffer = ""
        self.in_pre = False
        self.end_whitespace = re.compile(r'[ \t\n]\Z')
        self.md_interpreter = markdown_interpreter

    def reset(self):
        HTMLParser.reset(self)
        self.buffer = ""
        self.in_pre = False

    def readmd(self):
        return re.sub(r'\n\n\n+', '\n\n', self.buffer)

    def handle_data(self, data):
        """Put all of the processed data into a buffer

        While this class doesn't actually do much processing, this is where
        the result of it goes.
        """
        self.buffer += data

    def append_endtag(self, end):
        """Append a markdown end tag to the buffer.

        Markdown is much more sensitive to whitespace than html is, so we
        have to be careful.
        """
        end_white = self.end_whitespace.search(self.buffer)
        self.buffer = self.buffer.rstrip()

        # only append the end tag if there is something inside of it
        if self.buffer.endswith(end):
            self.buffer = self.buffer.rstrip(end)
        else:
            self.buffer += end

        if end_white:
            self.buffer += end_white.group(0)

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
                    if (self.md_interpreter == 'misaka' or
                        self.md_interpreter is None):
                        self.handle_data("\n~~~ { %s }\n" % language)
                    elif self.md_interpreter == 'markdown':
                        self.handle_data("\n~~~\n:::%s\n" % language)
                    else:
                        raise Exception(
                            "Unknown markdown interpeter: %s" %
                            self.md_interpreter)
                    break
            else:
                self.handle_data("\n~~~\n")
        elif tag == 'p':
            self.handle_data('\n')
        elif tag == 'a':
            self.link = {'title': '', 'href': ''}
            for name, val in attrs:
                if name == 'href':
                    self.link['href'] = val
                elif name == 'title':
                    self.link['title'] = val
            self.handle_data('[')
        elif tag in ('em', 'i'):
            self.handle_data('_')
        elif tag in ('strong', 'b'):
            self.handle_data('**')
        else:
            # pass the data through
            atts = ' '.join('%s="%s"' % (a, v) for a, v in attrs)
            if atts:
                self.handle_data("<%s %s>" % (tag, atts))
            else:
                self.handle_data("<%s>" % tag)

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.in_pre = False
            self.handle_data("\n~~~\n")
        elif tag == 'a':
            if self.link['title']:
                self.handle_data('](%(href)s "%(title)s") ' % self.link)
            else:
                self.handle_data('](%s) ' % self.link['href'])
        elif tag == 'p':
            self.handle_data('\n')
        elif tag in ('em', 'i'):
            self.append_endtag('_')
        elif tag in ('strong', 'b'):
            self.append_endtag('**')
        else:
            self.handle_data("</%s>" % tag)

class Exporter(object):
    """A class that wraps up export-logic.

    This class is meant to be used as a function: init it with the source
    file and the destination, and it will do the conversion.

    Why a class? Because that's how people write extensible code nowadays.
    Subclass this and write your own get_posts_from_* and export_to_* methods
    and you'll be golden.

    In more detail: to write an extractor, name it `get_props_from_FORMAT`
    where FORMAT is the name of the format to extract and make sure that it
    returns an iterable of dict-like objects that have at least the following
    keys:

        - u'date'
        - u'author'
        - u'content'
        - u'title'
        - u'status'
        - u'tags'

    To write an exporter, write something that takes that iterable of
    post-like things and puts them in a file. You might consider using the
    HtmlPreProcessor class defined above if you want minimal markdown-iness
    in the generated posts.
    """

    def __init__(self, source, outdir,
                 source_format='pma_xml', dest_format='mynt'):
        # create an html-to-markdown processor md_interpreter is the target
        # md_interpreter. They have different ideas about what to send to
        # pygments
        md_interpreter = 'misaka' if out_format == 'mynt' else 'markdown'
        self.processor = HtmlPreProcessor(md_interpreter)

        # actually do the stuff:
        posts = getattr(self, 'get_posts_from_' + source_format)(source)
        getattr(self, 'export_to_' + dest_format)(posts, outdir)

    def _markdownify(self, content):
        """Convert some pseudo-html into reasonably pleasant text
        """
        self.processor.reset()
        self.processor.feed(content)
        return self.processor.readmd()

    def export_to_nikola(self, posts, base_dir):
        meta_template = u"""%(title)s
%(safe_title)s
%(date)s
%(classifiers)s
"""
        j = os.path.join
        for post in posts:
            if post['content'] is None:
                continue

            t = post['safe_title'] = post['title'].replace(' ', '-').replace('/', '+')

            post['date'] = post['date'].replace('-', '/')[:-3]
            post['content'] = self._markdownify(post['content'])
            post['classifiers'] = ', '.join(post['classifiers'])

            with open(j(base_dir, t + '.meta'), 'w') as metafh:
                metafh.write((meta_template % post).encode('utf-8'))

            with open(j(base_dir, t + '.md'), 'w') as postfh:
                postfh.write(post['content'].encode('utf-8'))

    def export_to_mynt(self, posts, base_dir):
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
tags: %(classifiers)s
---

%(content)s
"""
        opj = os.path.join

        for post in posts:
            if post['content'] is None:
                continue
            filename = post['date'] + '-' + post['title'] + '.md'
            filename = filename.replace(' ', '-').replace('/', '+')

            # wordpress creates drafts with statuses draft or auto-draft
            # mynt ignores files that start with an underscore
            if 'draft' in post['status']:
                filename = '_' + filename

            # yaml has weird ideas about escape chars
            post['title'] = repr(post['title']).replace(
                r"\'", "''").replace("\\", "")

            post['content'] = self._markdownify(post['content'])

            with open(opj(base_dir, filename), 'w') as fh:
                out = template % post
                fh.write(out.encode('utf-8'))

    @staticmethod
    def get_posts_from_pma_xml(source):
        """Convert PHPMyAdmin xml to nice python Dicts

        this is where I implement database joins on top of xml.

        I try to be nice, and this is what I get? Sheesh. I hope somebody who
        doesn't have a mysql driver is grateful.
        """
        root = ET.parse(source).getroot()

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
        post_classifiers = defaultdict(list)
        post_cats = defaultdict(list)
        post_tags = defaultdict(list)
        for relation in root.findall(".//table[@name='wp_term_relationships']"):
            obj_id  = relation.find("./column[@name='object_id']").text
            term_id = relation.find("./column[@name='term_taxonomy_id']").text
            try:
                term = all_tags[term_id] # should throw KeyError for links
                post_classifiers[obj_id].append(term)
            except KeyError:
                pass

            try:
                # throw keyerror if this post doesn't have a category
                cat = categories[term_id]
                post_cats[obj_id].append(cat)
            except KeyError:
                pass

            try:
                # throw keyerror if this post doesn't have this tag
                tag = taxes[term_id]
                post_tags[obj_id].append(tag)
            except KeyError:
                pass

        for el in els:
            id = el.find("./column[@name='ID']").text
            post_type = el.find("./column[@name='post_type']").text
            status = el.find("./column[@name='post_status']").text
            if post_type == 'revision':
                id = el.find("./column[@name='post_parent']").text
                if status == u'inherit':
                    status = posts[id][u'status']

            posts[id] = {
                u'date':    el.find("./column[@name='post_date']").text,
                u'author':  el.find("./column[@name='post_author']").text,
                u'content': el.find("./column[@name='post_content']").text,
                u'title':   el.find("./column[@name='post_title']").text,
                u'status':  status,
                u'classifiers':    post_classifiers[id],
                u'categories': post_cats[id],
                u'tags': post_tags[id],
                }

        return posts.itervalues()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print __doc__
        exit(1)

    thefile = sys.argv[1]
    outdir  = sys.argv[2]
    out_format = 'mynt' if len(sys.argv) < 4 else sys.argv[3]
    source_format = 'pma_xml'
    Exporter(thefile, outdir, source_format, out_format)
